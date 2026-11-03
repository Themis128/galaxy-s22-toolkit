#!/usr/bin/env bash
# Wrapper for phone-file-transfer to prevent MSYS path conversion on Windows Git Bash
export MSYS_NO_PATHCONV=1
exec python -c "from phone_file_transfer import main; main()" "$@"