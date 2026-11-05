"""Device capability profiles for Samsung Galaxy phones (S/Note/A lines).

Probe-first, model-hints-second: nothing here hard-fails on an unknown
model. The profile is derived from what the device actually reports
(getprop), with a small marketing-name map for known models; every
capability decision remains runtime-probed by the modules themselves.

Applies to the Galaxy S/Note/A families on Android 10 (API 29) and
newer; anything outside that range still works but reports raw codes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# Known model-number cores -> (marketing name, release year). Suffix letters
# vary by region (B/N/U/W/E/M); keys are the numeric core between the series
# letter and the region code, so SM-S906B/N/U all resolve to S22+.
_MODEL_CORES: dict[str, tuple[str, int]] = {
    # Galaxy S (SM-G*, SM-S*)
    "G950": ("S8", 2017),
    "G955": ("S8+", 2017),
    "G960": ("S9", 2018),
    "G965": ("S9+", 2018),
    "G970": ("S10e", 2019),
    "G973": ("S10", 2019),
    "G975": ("S10+", 2019),
    "G977": ("S10 5G", 2019),
    "G980": ("S20", 2020),
    "G985": ("S20+", 2020),
    "G981": ("S20 5G", 2020),
    "G988": ("S20 Ultra", 2020),
    "G991": ("S21", 2021),
    "G996": ("S21+", 2021),
    "G998": ("S21 Ultra", 2021),
    "S901": ("S22", 2022),
    "S906": ("S22+", 2022),
    "S908": ("S22 Ultra", 2022),
    "S911": ("S23", 2023),
    "S916": ("S23+", 2023),
    "S918": ("S23 Ultra", 2023),
    "S921": ("S24", 2024),
    "S926": ("S24+", 2024),
    "S928": ("S24 Ultra", 2024),
    # Galaxy Note (SM-N*)
    "N950": ("Note8", 2017),
    "N960": ("Note9", 2018),
    "N970": ("Note10", 2019),
    "N975": ("Note10+", 2019),
    "N980": ("Note20", 2020),
    "N981": ("Note20 5G", 2020),
    "N985": ("Note20 Ultra", 2020),
    "N986": ("Note20 Ultra 5G", 2020),
    # Common Galaxy A cores (rule-based fallback covers the rest:
    # SM-A546B -> A54, SM-A346B -> A34, SM-A155F -> A15, ...)
    "A546": ("A54", 2023),
    "A536": ("A53", 2022),
    "A526": ("A52", 2021),
    "A525": ("A52", 2021),
    "A515": ("A51", 2020),
    "A346": ("A34", 2023),
    "A336": ("A33", 2022),
    "A325": ("A32", 2021),
    "A146": ("A14", 2023),
}

# Internal Samsung/Qualcomm platform codes -> friendly chipset names.
# Unknown codes stay raw (honest) rather than guessed.
_PLATFORM_NAMES: dict[str, str] = {
    "s5e9925": "Exynos 2200",  # S22 series (verified live on SM-S906B)
    "universal9925": "Exynos 2200",
    "universal9825": "Exynos 9825",
    "universal990": "Exynos 990",
    "universal9820": "Exynos 9820",
    "universal9810": "Exynos 9810",
    "lahaina": "Snapdragon 888",
    "taro": "Snapdragon 8 Gen 1",
    "kalama": "Snapdragon 8 Gen 2",
    "pineapple": "Snapdragon 8 Gen 3",
    "yupik": "Snapdragon 7 Gen 1",
    "holi": "Snapdragon 4 Gen 1",
    "lito": "Snapdragon 460-class",
    "bengal": "Snapdragon 460-class",
    "parrot": "Snapdragon 7 Gen 1",
}


@dataclass
class DeviceProfile:
    """What the toolkit knows about the attached Galaxy device."""

    model: str = "unknown"
    marketing_name: str = "unknown"
    series: str = "unknown"  # S / Note / A / other
    year_class: int | None = None
    chipset: str = "unknown"
    api_level: int = 0
    one_ui: str = "unknown"
    is_samsung: bool = False
    flags: set[str] = field(default_factory=set)

    def display_name(self) -> str:
        """Branding string: 'Galaxy S22+ (SM-S906B)', degrades to raw model."""
        if self.marketing_name in ("unknown", "") or self.marketing_name == self.model:
            return f"Galaxy ({self.model})" if self.model != "unknown" else "Galaxy"
        return f"Galaxy {self.marketing_name} ({self.model})"


def _resolve_marketing_name(model: str) -> tuple[str, str, int | None]:
    """Return (marketing_name, series, year_class) for a model code.

    The core key keeps the series letter (SM-S906B -> 'S906') because the
    known-model table is keyed that way; the A-series naming rule works on
    the digits alone (SM-A546B -> A54).
    """
    m = re.match(r"SM-?([SGNAFME])?(\d{3,4})", model.upper())
    if not m:
        return model, "unknown", None
    letter, digits = m.group(1) or "", m.group(2)
    series = {
        "S": "S",
        "G": "S",
        "N": "Note",
        "A": "A",
        "F": "other",
        "M": "other",
        "E": "other",
    }.get(letter, "other")
    core = letter + digits
    if core in _MODEL_CORES:
        name, year = _MODEL_CORES[core]
        return name, series, year
    # Rule-based A-series naming: A546 -> A54, A346 -> A34, A155 -> A15
    if letter == "A" and len(digits) == 3:
        return f"A{digits[:2]}", series, None
    return model, series, None


def _resolve_chipset(device: Any) -> str:
    """Best-effort chipset name from Samsung/Qualcomm platform properties."""
    props = device.get_all_props()
    candidates = (
        props.get("ro.board.platform", ""),
        props.get("ro.soc.model", ""),
        props.get("ro.hardware", ""),
        props.get("ro.boot.hardware", ""),
    )
    for raw in candidates:
        code = raw.strip().lower()
        if not code:
            continue
        if code in _PLATFORM_NAMES:
            return _PLATFORM_NAMES[code]
        # Exynos family codes: universal9825 / exynos9825 / exynos990
        m = re.match(r"(?:universal|exynos)(\d{3,4})", code)
        if m:
            return f"Exynos {m.group(1)}"
        if re.match(r"s5e\d{4}", code):
            # s5e-codes without a table entry stay raw (no guessing)
            if props.get("ro.board.platform", "").strip().lower() == code:
                return f"Exynos {code}"
        m = re.match(r"(?:sm|sdm)\d{4}", code)
        if m:
            return f"Snapdragon {code.upper()}"
        if code in ("qcom",):
            continue  # too generic - try the next candidate
    return "unknown"


def _resolve_one_ui(device: Any) -> str:
    """Decode Samsung's One UI version property (e.g. 80000 -> 8.0)."""
    raw = device.get_prop("ro.build.version.oneui")
    if raw and raw.strip().isdigit():
        v = int(raw)
        major, minor = v // 10000, (v % 10000) // 100
        return f"{major}.{minor}"
    return "unknown"


def describe_model(model: str) -> str:
    """Branding helper from a bare model code: SM-S906B -> 'Galaxy S22+ (SM-S906B)'.

    Unknown models degrade to 'Galaxy (<code>)'; empty to 'Galaxy'.
    """
    name, _series, _year = _resolve_marketing_name(model)
    if not model or name in ("unknown", "") or name == model:
        return f"Galaxy ({model})" if model else "Galaxy"
    return f"Galaxy {name} ({model})"


def detect_profile(device: Any) -> DeviceProfile:
    """Build a DeviceProfile from what the attached device reports.

    Never raises: any missing property degrades to 'unknown' defaults.
    """
    try:
        props = device.get_all_props()
    except Exception:
        props = {}

    model = props.get("ro.product.model", "") or "unknown"
    manufacturer = props.get("ro.product.manufacturer", "") or ""
    name, series, year = _resolve_marketing_name(model)
    api_level = 0
    try:
        api_level = int(props.get("ro.build.version.sdk", "0"))
    except ValueError:
        pass

    profile = DeviceProfile(
        model=model,
        marketing_name=name,
        series=series,
        year_class=year,
        chipset=_resolve_chipset(device),
        api_level=api_level,
        one_ui=_resolve_one_ui(device),
        is_samsung=manufacturer.lower() == "samsung",
        flags=set(),
    )
    if profile.api_level >= 29:
        profile.flags.add("android_10_plus")
    if profile.api_level >= 33:
        profile.flags.add("android_13_plus")
    return profile
