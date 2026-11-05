$paths = @(
  'C:\Users\tbaltzakis\CrossDevice\Galaxy S22+ (2)\storage\test_insights.py',
  'C:\Users\tbaltzakis\CrossDevice\Galaxy S22+ (2)\storage\test_tools.py',
  'C:\Users\tbaltzakis\CrossDevice\Galaxy S22+ (2)\storage\tests\test_app.py',
  'C:\Users\tbaltzakis\CrossDevice\Galaxy S22+ (2)\storage\tests\test_device_integration.py',
  'C:\Users\tbaltzakis\CrossDevice\Galaxy S22+ (2)\storage\tests\test_metrics_db.py'
)

foreach ($path in $paths) {
  if (Test-Path $path) {
    $file = Get-Item $path
    Write-Host ("{0}: {1}" -f $path, $file.Attributes)
    $file.Attributes = [System.IO.FileAttributes]::Normal
    $file.IsReadOnly = $false
    Write-Host ("  -> {0}" -f $file.Attributes)
  }
}