# Check OneDrive status and try to sync the storage folder
$onedrive = Get-Process -Name 'OneDrive' -ErrorAction SilentlyContinue
if ($onedrive) {
  Write-Host 'OneDrive is running'
} else {
  Write-Host 'OneDrive NOT running - starting...'
  Start-Process 'C:\Users\tbaltzakis\AppData\Local\Microsoft\OneDrive\OneDrive.exe'
  Start-Sleep 5
}

# Try to make files available offline using OneDrive API
$storagePath = 'C:\Users\tbaltzakis\CrossDevice\Galaxy S22+ (2)\storage'
if (Test-Path $storagePath) {
  Write-Host "Storage path exists: $storagePath"
  Get-ChildItem -Recurse $storagePath | ForEach-Object {
    Write-Host "  $_ : $($_.Attributes)"
  }
}