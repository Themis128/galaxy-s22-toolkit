# Removes Windows reserved-name files that block git add (nul, con, aux, ...).
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File scripts/remove-nul.ps1
$root = Split-Path -Parent $PSScriptRoot
$targets = @(
    Join-Path $root 'phone-lib\nul'
    Join-Path $root 'nul'
)
$removed = 0
foreach ($t in $targets) {
    $extPath = '\\?\' + $t   # $t is absolute: C:\Users\...\nul -> \\?\C:\Users\...\nul
    try {
        # .NET File API handles the \\?\ namespace literally (no NUL device mapping)
        [System.IO.File]::Delete($extPath)
        Write-Output "DELETED: $t"
        $removed++
    } catch {
        Write-Output "FAILED: $t ($($_.Exception.Message))"
    }
}
exit 0
