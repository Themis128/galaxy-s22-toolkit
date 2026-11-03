"""Entry point for phone-file-transfer with MSYS path conversion fix."""

from __future__ import annotations

import os

# Set MSYS_NO_PATHCONV=1 BEFORE any imports that might trigger path conversion
# This prevents Git Bash from converting /sdcard/... to C:/Program Files/Git/sdcard/...
os.environ["MSYS_NO_PATHCONV"] = "1"

from phone_file_transfer import main

if __name__ == "__main__":
    main()
