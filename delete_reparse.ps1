$testFiles = @(
  'C:\Users\tbaltzakis\CrossDevice\Galaxy S22+ (2)\storage\test_insights.py',
  'C:\Users\tbaltzakis\CrossDevice\Galaxy S22+ (2)\storage\test_tools.py',
  'C:\Users\tbaltzakis\CrossDevice\Galaxy S22+ (2)\storage\tests\test_app.py',
  'C:\Users\tbaltzakis\CrossDevice\Galaxy S22+ (2)\storage\tests\test_device_integration.py',
  'C:\Users\tbaltzakis\CrossDevice\Galaxy S22+ (2)\storage\tests\test_metrics_db.py'
)

foreach ($path in $testFiles) {
  if (Test-Path $path) {
    Write-Host "Processing: $path"
    
    # Try to delete the reparse point (this removes the OneDrive placeholder)
    $result = fsutil.exe reparsepoint delete "$path" 2>&1
    Write-Host "  Delete reparse point: $result"
    
    # Wait a moment for OneDrive to download the file
    Start-Sleep 2
    
    # Try to read the file
    try {
      $content = Get-Content $path -Raw -ErrorAction Stop
      Write-Host "  Successfully read $($content.Length) chars"
    } catch {
      Write-Host "  Read failed: $($_.Exception.Message)"
    }
    
    # Check attributes
    $file = Get-Item $path
    Write-Host "  Attributes: $($file.Attributes)"
  }
}