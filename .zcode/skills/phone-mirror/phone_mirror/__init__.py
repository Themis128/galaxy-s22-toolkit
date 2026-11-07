"""Console-script shim: delegates to tools/mirror.py in the repo.

The skill is installed editable from .zcode/skills/, so the repo root is
always four parents up from this file.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[4]
_TOOL = _REPO_ROOT / "tools" / "mirror.py"


def main() -> int:
    sys.path.insert(0, str(_REPO_ROOT))
    spec = importlib.util.spec_from_file_location("_tool", _TOOL)
    if spec is None or spec.loader is None:
        print(f"Tool not found: {_TOOL}", file=sys.stderr)
        return 2
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return int(mod.main() or 0)


if __name__ == "__main__":
    sys.exit(main())
