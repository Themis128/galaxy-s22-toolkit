#!/usr/bin/env python3
"""Data Eraser — prepare the phone for sale or hand-over.

The open-source equivalent of Wondershare Data Eraser. Three steps, each
individually gated:

    status        — read-only inventory: identity, encryption, FRP/locks,
                    storage, apps, media, WhatsApp; "what will be lost"
    free-space    — overwrite remnants of deleted files in shared storage
                    (requires --yes; fills storage temporarily)
    reset         — guided factory reset; --execute + typed ERASE-PHONE
    certificate   — erase certificate JSON from the recorded action log

Honesty note: "Free-space overwrite is best-effort on encrypted flash;
per-file FBE keys already protect deleted content — this pass covers
remnants in shared storage trees, thumbnails, and database freelists."
A factory reset (with FBE) is the step that actually re-keys the data
partition; this tool never claims more than that.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

try:
    from phone import create_client
except ImportError:  # pragma: no cover
    create_client = None  # type: ignore[assignment]

HONESTY_NOTE = (
    "Free-space overwrite is best-effort on encrypted flash; per-file FBE keys "
    "already protect deleted content - this pass covers remnants in shared "
    "storage trees, thumbnails, and database freelists."
)
CERT_DIR = REPO / "data" / "erase-certificates"
FILL_DIR = "/sdcard/erase-fill-{ts}"
FREE_FLOOR_MB = 64
MAX_FILL_FILES = 5
CONFIRM_PHRASE = "ERASE-PHONE"
RESET_GUIDANCE = (
    "Factory reset (the step that re-keys the data partition):\n"
    "  Settings > General management > Reset > Factory data reset\n"
    "  (or re-run with --execute to trigger it over ADB after typing " + CONFIRM_PHRASE + ")"
)
MEDIA_DIRS = ("/sdcard/DCIM", "/sdcard/Pictures", "/sdcard/Download")


_SIZE_TOKEN = re.compile(r"^\d+(\.\d+)?[KMGT]?$")


def parse_df(out: str) -> tuple[float, float] | None:
    """(used_gb, free_gb) from a df -h /sdcard or dumpsys df fragment.

    Accepts df -h style rows (fs size used avail use% mount) for the
    /storage/emulated or /data mount; returns None on empty or garbage.
    """
    for line in out.splitlines():
        if "/storage/emulated" not in line and not line.rstrip().endswith("/data"):
            continue
        cols = line.split()
        numbers = [c for c in cols if _SIZE_TOKEN.match(c) and not c.endswith("%")]
        # df -h: [size, used, avail] -> used = -2, avail = -1.
        if len(numbers) >= 3:
            used = _to_gb(numbers[-2])
            free = _to_gb(numbers[-1])
            if used is not None and free is not None:
                return used, free
    return None


def _to_gb(token: str) -> float | None:
    """df -h size token -> GB. G = as-is; bare numbers are GB too."""
    m = re.match(r"^(\d+(?:\.\d+)?)([KMGT]?)$", token, re.IGNORECASE)
    if not m:
        return None
    val = float(m.group(1))
    suffix = m.group(2).upper()
    if suffix == "K":
        val /= 1024 * 1024
    elif suffix == "M":
        val /= 1024
    elif suffix == "T":
        val *= 1024
    return val


def parse_app_count(out: str) -> int | None:
    """Count of installed packages from `pm list packages` output."""
    if not out or not out.strip():
        return None
    count = sum(1 for line in out.splitlines() if line.startswith("package:"))
    return count or None


def build_certificate(device: dict[str, Any], actions: list[dict[str, Any]]) -> dict[str, Any]:
    """Erase certificate dict; actions carry action/timestamp/outcome."""
    return {
        "device": device,
        "actions": actions,
        "honesty_note": HONESTY_NOTE,
        "generated": datetime.now().isoformat(),
    }


def confirm_typed(prompt: str, expected: str, input_fn: Callable[[str], str] = input) -> bool:
    """Typed confirm gate: exact phrase required.

    Wrong text re-prompts once; EOF or empty input returns False without
    raising, so a piped/automated run can never confirm by accident.
    """
    for attempt in range(2):
        try:
            answer = input_fn(prompt)
        except (EOFError, OSError):
            return False
        if answer.strip() == expected:
            return True
        if answer.strip() == "" or attempt == 1:
            return False
        print("  (type the phrase exactly, or press Enter to abort)")
    return False


def _probe(client: Any, *args: str) -> str:
    """One shell probe; empty string on any error (N/A degradation)."""
    try:
        out = client.execute(*args)
        return str(out).strip()
    except Exception:  # noqa: BLE001 - inventory must never raise
        return ""


def _getprop(client: Any, prop: str) -> str:
    out = _probe(client, "shell", "getprop", prop)
    return out if out else "N/A"


def _dir_count(client: Any, path: str) -> str:
    out = _probe(client, "shell", "ls", "-A1", path)
    if not out:
        return "N/A"
    return str(sum(1 for line in out.splitlines() if line.strip()))


def _wa_databases(client: Any) -> str:
    for base in (
        "/sdcard/Android/media/com.whatsapp/WhatsApp/Databases",
        "/sdcard/WhatsApp/Databases",
    ):
        out = _probe(client, "shell", "ls", "-A1", base)
        if out:
            dbs = [ln for ln in out.splitlines() if ln.endswith(".crypt15")]
            return f"{len(dbs)} backup file(s)"
    return "N/A"


def append_action(serial: str, action: str, outcome: str, **extra: Any) -> None:
    """Append one action line to the certificate JSONL for this serial."""
    CERT_DIR.mkdir(parents=True, exist_ok=True)
    entry: dict[str, Any] = {
        "action": action,
        "timestamp": datetime.now().isoformat(),
        "outcome": outcome,
    }
    entry.update(extra)
    with open(CERT_DIR / f"{serial}.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def read_actions(serial: str) -> list[dict[str, Any]]:
    """All recorded actions for this serial (empty when none)."""
    path = CERT_DIR / f"{serial}.jsonl"
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _identity(client: Any) -> dict[str, Any]:
    return {
        "model": _getprop(client, "ro.product.model"),
        "serial": str(getattr(client, "serial", "N/A") or "N/A"),
        "android": _getprop(client, "ro.build.version.release"),
        "crypto_state": _getprop(client, "ro.crypto.state"),
        "frp_partition": _getprop(client, "ro.frp.pst"),
    }


def cmd_status(client: Any) -> int:
    """Read-only pre-erase inventory."""
    ident = _identity(client)
    df_out = _probe(client, "shell", "df", "-h", "/sdcard")
    df = parse_df(df_out)
    apps = parse_app_count(_probe(client, "shell", "pm", "list", "packages"))
    print("== Data Eraser: pre-erase inventory ==")
    print(f"model={ident['model']}  serial={ident['serial']}  android={ident['android']}")
    print(f"encryption={ident['crypto_state']}  FRP partition={ident['frp_partition']}")
    if df:
        print(f"storage: used {df[0]:.1f} GB, free {df[1]:.1f} GB")
    else:
        print("storage: N/A (df output unreadable)")
    print(f"installed apps: {apps if apps is not None else 'N/A'}")
    for d in MEDIA_DIRS:
        print(f"{d}: {_dir_count(client, d)} items")
    print(f"WhatsApp local backups: {_wa_databases(client)}")
    print("\nWhat will be lost on erase/reset:")
    print("  - all apps + app data, accounts, and system settings")
    print("  - photos/videos/music/downloads in shared storage")
    print("  - WhatsApp message history (unless backed up to Google Drive)")
    print("  - 2FA/authenticator app seeds (export them FIRST)")
    print(f"\n{HONESTY_NOTE}")
    return 0


def _free_mb(client: Any) -> float | None:
    df = parse_df(_probe(client, "shell", "df", "-h", "/sdcard"))
    if df is None:
        return None
    return df[1] * 1024


def cmd_free_space(client: Any, serial: str) -> int:
    """One best-effort overwrite pass over /sdcard free space."""
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    fill_dir = FILL_DIR.format(ts=ts)
    written_mb = 0.0
    files_created = 0
    before = _free_mb(client)
    if before is None:
        print("Cannot read free space on /sdcard - aborting without writing.")
        return 1
    for i in range(MAX_FILL_FILES):
        free = _free_mb(client)
        if free is None or free <= FREE_FLOOR_MB + 16:
            break
        size_mb = min(int(free - FREE_FLOOR_MB - 8), 4096)
        if size_mb <= 0:
            break
        rc, out = _shell_rc(
            client,
            "dd",
            "if=/dev/urandom",
            f"of={fill_dir}/fill-{i}.bin",
            "bs=1M",
            f"count={size_mb}",
        )
        if rc != 0:
            break
        files_created += 1
        written_mb += size_mb
    _probe(client, "shell", "sync")
    _probe(client, "shell", "rm", "-rf", fill_dir)
    after = _free_mb(client)
    print(
        f"Free-space pass: {files_created} file(s), {written_mb / 1024:.1f} GB written "
        f"and deleted (free {before if before else 0:.0f} -> "
        f"{after if after else 0:.0f} MB)"
    )
    outcome = "ok" if files_created > 0 else "no-space-or-dd-failed"
    append_action(serial, "free-space", outcome, bytes_written_mb=int(written_mb))
    print(f"Honesty note: {HONESTY_NOTE}")
    return 0 if files_created > 0 else 1


def _shell_rc(client: Any, *args: str) -> tuple[int, str]:
    """Run one shell command capturing a failure (dd returns non-zero on ENOSPC)."""
    try:
        out = client.execute(*args)
        return 0, str(out)
    except Exception as exc:  # noqa: BLE001 - dd ENOSPC surfaces as CommandFailedError
        return 1, str(exc)


def cmd_reset(
    client: Any, serial: str, execute: bool, input_fn: Callable[[str], str] = input
) -> int:
    """Guided factory reset; --execute + typed confirm triggers MASTER_CLEAR."""
    if not execute:
        print(RESET_GUIDANCE)
        print("\nNo reset performed (pass --execute to trigger it over ADB).")
        return 0
    print("This will FACTORY RESET the phone. Everything on it is lost.")
    print(f"{HONESTY_NOTE}")
    if not confirm_typed(f"Type {CONFIRM_PHRASE} to proceed: ", CONFIRM_PHRASE, input_fn):
        print("Not confirmed - nothing was done.")
        append_action(serial, "reset", "refused-confirm")
        return 1
    try:
        client.execute("shell", "am", "broadcast", "-a", "android.intent.action.MASTER_CLEAR")
    except Exception as exc:  # noqa: BLE001 - degrade honestly
        print(f"Reset broadcast failed: {exc}")
        append_action(serial, "reset", "failed", error=str(exc))
        return 1
    print("Reset broadcast sent - the phone will wipe itself and reboot.")
    append_action(
        serial, "reset", "sent", note="MASTER_CLEAR broadcast; wipe completes after reboot"
    )
    return 0


def cmd_certificate(serial: str, show: bool) -> int:
    """Render the erase certificate from the recorded action JSONL."""
    actions = read_actions(serial)
    if not actions:
        print(f"No erase actions recorded for {serial} ({CERT_DIR / f'{serial}.jsonl'}).")
        return 1
    device = next((a.get("device") for a in reversed(actions) if a.get("device")), None) or {}
    cert = build_certificate(device, actions)
    rendered = json.dumps(cert, indent=1)
    if show:
        print(rendered)
        return 0
    out_path = CERT_DIR / f"{serial}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    out_path.write_text(rendered + "\n", encoding="utf-8")
    print(f"Erase certificate written: {out_path}")
    return 0


def _client(serial: str | None) -> Any:
    import yaml

    with open(REPO / "diagnostics" / "config.yaml", encoding="utf-8") as f:
        device_cfg = (yaml.safe_load(f) or {}).get("device", {})
    wireless = device_cfg.get("wireless_adb") or None
    if wireless:
        wireless = {**wireless, "preferred_serial": device_cfg.get("serial")}
    return create_client(serial, wireless=wireless)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("status", "free-space", "reset", "certificate"):
        p = sub.add_parser(name)
        p.add_argument("--serial")
    sub.choices["free-space"].add_argument("--yes", action="store_true")
    sub.choices["reset"].add_argument("--execute", action="store_true")
    sub.choices["certificate"].add_argument("--show", action="store_true")
    args = ap.parse_args(argv)

    serial = args.serial
    if not serial:
        # certificate runs offline; fall back to the configured device serial
        try:
            import yaml

            with open(REPO / "diagnostics" / "config.yaml", encoding="utf-8") as f:
                serial = str((yaml.safe_load(f) or {}).get("device", {}).get("serial") or "")
        except Exception:  # noqa: BLE001 - cosmetic fallback only
            serial = ""
    client: Any = None
    if args.cmd != "certificate":
        if create_client is None:
            print("phone-lib not importable")
            return 1
        client = _client(serial or None)
        serial = str(getattr(client, "serial", "") or serial or "unknown")

    if args.cmd == "status":
        return cmd_status(client)
    if args.cmd == "free-space":
        if not args.yes:
            print(
                "free-space temporarily fills /sdcard to under 64 MB free. "
                "Re-run with --yes to allow it."
            )
            return 1
        return cmd_free_space(client, serial)
    if args.cmd == "reset":
        return cmd_reset(client, serial, args.execute)
    return cmd_certificate(serial, args.show)


if __name__ == "__main__":
    raise SystemExit(main())
