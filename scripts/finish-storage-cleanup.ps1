# Finishes the storage/ cleanup once OneDrive is running again.
# storage/ files are OneDrive cloud placeholders that need a live cloud provider
# before they can be renamed or read. Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts/finish-storage-cleanup.ps1
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
$src = Join-Path $root 'storage'
$dst = Join-Path $root 'data\artifacts'

if (-not (Test-Path $src)) {
    Write-Output "storage/ does not exist - nothing to do."
    exit 0
}

# 1. Verify the cloud provider is available by hydrating one probe file
$probe = Get-ChildItem $src -File | Where-Object { $_.Extension -in '.png', '.xml' } | Select-Object -First 1
if (-not $probe) {
    Write-Output "No placeholder files left in storage/."
    exit 0
}
try {
    $null = [System.IO.File]::ReadAllBytes($probe.FullName)
    Write-Output "Cloud provider available (probe hydrated)."
} catch {
    Write-Output "OneDrive cloud provider still unavailable - run this later."
    exit 1
}

# 2. Move remaining artifacts (png/xml) to data/artifacts
New-Item -ItemType Directory -Force -Path $dst | Out-Null
Get-ChildItem $src -File -Filter *.png | Move-Item -Destination $dst -Force -ErrorAction Continue
Get-ChildItem $src -File -Filter *.xml | Move-Item -Destination $dst -Force -ErrorAction Continue

# 3. Session scripts from past work
foreach ($s in @('d2.sh','d3.sh','d4.sh','d5.sh','d7.sh','full.sh','g.sh','vf.sh','drive_tt.sh','tiktok_verify_upload.sh')) {
    $p = Join-Path $src $s
    if (Test-Path -LiteralPath $p) {
        Move-Item -LiteralPath $p -Destination (Join-Path $dst $s) -Force -ErrorAction Continue
    }
}

# 4. Move the legacy toolkit duplicates to an archive for diffing
$arch = Join-Path $root 'data\archive-storage-2026-11-03'
New-Item -ItemType Directory -Force -Path $arch | Out-Null
foreach ($d in @('src','tests','skills','lib','v','phone','dashboard','diagnostics','scripts','galaxy-s22-toolkit-skills','phone-lib')) {
    $p = Join-Path $src $d
    if (Test-Path -LiteralPath $p) {
        Move-Item -LiteralPath $p -Destination (Join-Path $arch $d) -Force -ErrorAction Continue
    }
}

# 5. Delete pure junk (build artifacts, caches, session state)
foreach ($j in @('*.egg-info','build','bdist.win-amd64','cache','hook-state','hook-status','__pycache__','0.15.15','CACHEDIR.TAG','*.lock','*.baseline')) {
    Get-ChildItem $src -Recurse -Force -Filter $j -Directory -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction Continue
    Get-ChildItem $src -File -Filter $j -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction Continue
}

# 6. Single-file toolkit duplicates: diff against real counterparts
$dupMap = @{
    'config.yaml'            = 'diagnostics\config.yaml'
    'app.py'                 = 'dashboard\app.py'
    'run_diagnostics.py'     = 'diagnostics\run_diagnostics.py'
    'pyproject.toml'         = 'phone-lib\pyproject.toml'
    'requirements.txt'       = 'galaxy-s22-toolkit-skills\requirements.txt'
    'install.sh'             = 'galaxy-s22-toolkit-skills\install.sh'
    'install_task.ps1'       = 'diagnostics\install_task.ps1'
    'task_scheduler.xml'     = 'diagnostics\task_scheduler.xml'
    'adb_wireless_setup.ps1' = 'scripts\adb_wireless_setup.ps1'
    'setup_termux.sh'        = 'scripts\setup_termux.sh'
    'termux_bootstrap.sh'    = 'scripts\termux_bootstrap.sh'
    'README.md'              = $null   # unreadable placeholder; archive
}
foreach ($name in $dupMap.Keys) {
    $p = Join-Path $src $name
    if (Test-Path -LiteralPath $p) {
        $real = $dupMap[$name]
        if ($real -and (Test-Path (Join-Path $root $real))) {
            $h1 = (Get-FileHash (Join-Path $root $real)).Hash
            $h2 = (Get-FileHash $p).Hash
            if ($h1 -eq $h2) {
                Remove-Item -LiteralPath $p -Force
                Write-Output "DELETED duplicate: $name"
                continue
            }
        }
        Move-Item -LiteralPath $p -Destination (Join-Path $arch $name) -Force -ErrorAction Continue
        Write-Output "ARCHIVED: $name"
    }
}

# 7. Report what remains
$left = Get-ChildItem $src -Recurse -File -ErrorAction SilentlyContinue
Write-Output ("storage/ now holds {0} file(s)." -f $left.Count)
Get-ChildItem $src -Recurse -File -ErrorAction SilentlyContinue | Select-Object -First 10 -ExpandProperty FullName
exit 0
