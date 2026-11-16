"""UI automation: uiautomator dump parsing, node finding, focus/blocker checks."""

from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .adb import AdbClient


@dataclass(frozen=True)
class Bounds:
    """Screen bounds [left,top][right,bottom]."""

    left: int
    top: int
    right: int
    bottom: int

    @property
    def center(self) -> tuple[int, int]:
        return ((self.left + self.right) // 2, (self.top + self.bottom) // 2)


_BOUNDS_RE = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")


def parse_bounds(raw: str | None) -> Bounds | None:
    """Parse '[l,t][r,b]' into Bounds, or None."""
    if not raw:
        return None
    m = _BOUNDS_RE.match(raw.strip())
    if not m:
        return None
    return Bounds(*(int(g) for g in m.groups()))


@dataclass
class UiNode:
    """A single node from the uiautomator hierarchy."""

    text: str = ""
    desc: str = ""
    resource_id: str = ""
    class_name: str = ""
    package: str = ""
    bounds: Bounds | None = None
    clickable: bool = False
    enabled: bool = True
    focused: bool = False
    children: list[UiNode] = field(default_factory=list)

    @property
    def center(self) -> tuple[int, int] | None:
        return self.bounds.center if self.bounds else None

    def matches(
        self,
        text: str | None = None,
        desc: str | None = None,
        resource_id: str | None = None,
        class_name: str | None = None,
        contains: bool = True,
    ) -> bool:
        def eq(field_val: str, want: str | None) -> bool:
            if want is None:
                return True
            return want in field_val if contains else field_val == want

        return (
            eq(self.text, text)
            and eq(self.desc, desc)
            and eq(self.resource_id, resource_id)
            and eq(self.class_name, class_name)
        )


def parse_ui_xml(xml_text: str) -> list[UiNode]:
    """Parse uiautomator dump XML into a flat list of nodes (document order)."""
    root = ET.fromstring(xml_text)
    nodes: list[UiNode] = []

    def walk(el: ET.Element, parent: UiNode | None) -> None:
        if el.tag != "node":
            for child in el:
                walk(child, parent)
            return
        node = UiNode(
            text=el.get("text", ""),
            desc=el.get("content-desc", ""),
            resource_id=el.get("resource-id", ""),
            class_name=el.get("class", ""),
            package=el.get("package", ""),
            bounds=parse_bounds(el.get("bounds")),
            clickable=el.get("clickable") == "true",
            enabled=el.get("enabled", "true") == "true",
            focused=el.get("focused") == "true",
        )
        if parent is not None:
            parent.children.append(node)
        nodes.append(node)
        for child in el:
            walk(child, node)

    walk(root, None)
    return nodes


class UiModule:
    """UI automation helpers on top of uiautomator dumps."""

    # Activity names that mean the main display is unreachable
    COVER_ACTIVITIES = ("CoverHomeActivity",)
    LOCKSCREEN_MARKERS = (
        "KeyguardServiceDelegate",
        "NotificationShade",
        "com.android.systemui.keyguard",
        "com.samsung.android.biometrics.app.setting",
    )

    def __init__(self, client: AdbClient) -> None:
        self.client = client

    # -- dumps ---------------------------------------------------------

    def dump(self) -> list[UiNode]:
        """Dump UI hierarchy and return parsed nodes (empty on failure)."""
        try:
            out = self.client.shell("uiautomator dump /sdcard/_ui.xml >/dev/null 2>&1")
            _ = out
            xml_text = self.client.shell("cat /sdcard/_ui.xml")
        except Exception:
            return []
        if "<?xml" not in xml_text:
            return []
        try:
            return parse_ui_xml(xml_text)
        except ET.ParseError:
            return []

    def dump_pull(self, local_path: str = "/tmp/ui.xml") -> str:
        """Dump UI hierarchy to a local file; returns the local path."""
        self.client.shell("uiautomator dump /sdcard/_ui.xml >/dev/null 2>&1")
        self.client.pull("/sdcard/_ui.xml", local_path)
        return local_path

    # -- finding --------------------------------------------------------

    def find(
        self,
        nodes: list[UiNode] | None = None,
        *,
        text: str | None = None,
        desc: str | None = None,
        resource_id: str | None = None,
        class_name: str | None = None,
        clickable: bool | None = None,
        contains: bool = True,
        exact: bool = False,
    ) -> list[UiNode]:
        """Find nodes matching the given criteria."""
        pool = nodes if nodes is not None else self.dump()
        out = [
            n
            for n in pool
            if n.matches(
                text=text,
                desc=desc,
                resource_id=resource_id,
                class_name=class_name,
                contains=not exact,
            )
            and (clickable is None or n.clickable == clickable)
        ]
        return out

    def wait_for(
        self,
        text: str | None = None,
        *,
        desc: str | None = None,
        resource_id: str | None = None,
        timeout: float = 10.0,
        interval: float = 0.7,
        **kwargs: object,
    ) -> UiNode | None:
        """Poll dumps until a matching node appears; returns it or None."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            found = self.find(text=text, desc=desc, resource_id=resource_id, **kwargs)  # type: ignore[arg-type]
            if found:
                return found[0]
            time.sleep(interval)
        return None

    # -- interaction -----------------------------------------------------

    def tap_node(self, node: UiNode) -> bool:
        """Tap the center of a node's bounds. False if no bounds."""
        if node.center is None:
            return False
        x, y = node.center
        self.client.tap(x, y)
        return True

    def tap_text(
        self,
        text: str,
        *,
        desc: str | None = None,
        exact: bool = False,
        timeout: float = 0.0,
    ) -> bool:
        """Find a node by text/desc and tap its center."""
        node = (
            self.wait_for(text=text, desc=desc, exact=exact, timeout=timeout) if timeout else None
        )
        if node is None:
            node = self.find(text=text, desc=desc, exact=exact)
            node = node[0] if node else None
        if node is None:
            return False
        return self.tap_node(node)

    def type_text(self, text: str, clear_first: bool = False) -> None:
        """Type text into the focused field. clear_first sends 40 backspaces."""
        if clear_first:
            for _ in range(40):
                self.client.keyevent(67)  # KEYCODE_DEL
        self.client.text(text)

    # -- state / blockers -------------------------------------------------

    def focus(self) -> str:
        """Return the focused window/activity from dumpsys window."""
        try:
            out = self.client.shell("dumpsys window | grep -E 'mCurrentFocus|mFocusedApp'")
        except Exception:
            return ""
        return out.strip()

    def foreground_activity(self) -> str:
        """Best-effort current activity name from focus output."""
        focus = self.focus()
        m = re.search(r"([\w.]+/[\w.$]+)", focus)
        return m.group(1) if m else ""

    def is_covered(self) -> bool:
        """True if the flip cover or a cover-style activity has focus."""
        return any(a in self.focus() for a in self.COVER_ACTIVITIES)

    def is_locked(self) -> bool:
        """True if the keyguard/lockscreen appears to be showing."""
        focus = self.focus()
        return any(m in focus for m in self.LOCKSCREEN_MARKERS)

    def status(self) -> dict[str, object]:
        """One-shot state snapshot for pre-flight checks."""
        focus = self.focus()
        nodes = self.dump()
        return {
            "focus": focus,
            "activity": self.foreground_activity(),
            "covered": self.is_covered(),
            "locked": self.is_locked(),
            "ui_nodes": len(nodes),
            "ui_ok": len(nodes) > 0,
        }
