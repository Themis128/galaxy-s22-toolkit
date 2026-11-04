#!/usr/bin/env python3
"""Install repo git hooks: OneDrive attr fix + junk-file guard.

Writes .git/hooks/pre-commit that:
1. clears the read-only flag OneDrive re-applies to .git/COMMIT_EDITMSG
   (the cause of 'could not open COMMIT_EDITMSG: Permission denied')
2. rejects any staged path containing the U+F03A artifact char

Usage: python tools/install_git_hooks.py
"""

from pathlib import Path

HOOK = """#!/bin/sh
# Installed by tools/install_git_hooks.py - Galaxy S22+ toolkit
attrib -r "$(git rev-parse --git-dir)/HOOK_MSG_MARKER" 2>/dev/null || true
if git -c core.quotePath=false diff --cached --name-only | grep -q "$(printf '\\357\\200\\272')"; then
  echo "ERROR: mangled path artifact staged - unstage it" >&2
  exit 1
fi
exit 0
"""


def main() -> int:
    import os
    import stat

    hooks_dir = Path(__file__).resolve().parents[1] / ".git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook = hooks_dir / "pre-commit"
    # OneDrive re-flags the old hook read-only; clear before overwriting
    try:
        os.chmod(hook, stat.S_IWRITE)
    except OSError:
        pass
    hook.write_text(HOOK.replace("HOOK_MSG_MARKER", "COMMIT_EDITMSG"), encoding="utf-8")
    print("installed", hook)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
