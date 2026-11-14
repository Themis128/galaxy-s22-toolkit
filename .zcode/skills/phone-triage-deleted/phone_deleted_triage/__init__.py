"""Console-script shim: delegates to tools/deleted_file_triage.py in the repo."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[4]
_TOOL = _REPO_ROOT / "tools" / "deleted_file_triage.py"


def main() -> int:
    sys.path.insert(0, str(_REPO_ROOT))
    spec = importlib.util.spec_from_file_location("_tool", _TOOL)
    if spec is None or spec.loader is None:
        print(f"Tool not found: {_TOOL}", file=sys.stderr)
        return 2
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_tool"] = mod  # dataclass resolution needs the module registered
    spec.loader.exec_module(mod)
    return int(mod.main() or 0)


if __name__ == "__main__":
    sys.exit(main())
