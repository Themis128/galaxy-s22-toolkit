@echo off
REM Wrapper for phone-file-transfer to prevent MSYS path conversion on Windows Git Bash
set MSYS_NO_PATHCONV=1
python -c "from phone_file_transfer import main; main()" %*