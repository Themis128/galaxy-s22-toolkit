$paths = @(
  'C:\Users\tbaltzakis\CrossDevice\Galaxy S22+ (2)\storage\test_insights.py',
  'C:\Users\tbaltzakis\CrossDevice\Galaxy S22+ (2)\storage\test_tools.py',
  'C:\Users\tbaltzakis\CrossDevice\Galaxy S22+ (2)\storage\tests\test_app.py',
  'C:\Users\tbaltzakis\CrossDevice\Galaxy S22+ (2)\storage\tests\test_device_integration.py',
  'C:\Users\tbaltzakis\CrossDevice\Galaxy S22+ (2)\storage\tests\test_metrics_db.py'
)

foreach ($path in $paths) {
  if (Test-Path $path) {
    Write-Host "Processing: $path"
    
    # Try using attrib command which works better for OneDrive
    attrib -r -h -s -a -o -p "$path" 2>&1 | Write-Host
    
    # Try to force download by reading
    try {
      $content = [IO.File]::ReadAllText($path)
      Write-Host "  Read $($content.Length) chars - forced download"
    } catch {
      Write-Host "  Read error: $($_.Exception.Message)"
    }
    
    # Check attributes after
    $file = Get-Item $path
    Write-Host "  Attributes: $($file.Attributes)"
  }
}