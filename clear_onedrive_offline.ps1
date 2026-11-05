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
    
    # Use the fsutil command to clear the offline attribute
    # This is more reliable for OneDrive files
    $result = fsutil.exe reparsepoint query "$path" 2>&1
    Write-Host "  Reparse point: $result"
    
    # Try to clear the offline attribute using attrib
    attrib -o "$path" 2>&1 | Write-Host
    
    # Try using Windows.Storage.FileProperties to pin the file
    try {
      Add-Type -AssemblyName System.Runtime.WindowsRuntime
      $file = [Windows.Storage.StorageFile]::GetFileFromPathAsync($path).GetAwaiter().GetResult()
      # This won't work from PowerShell directly...
    } catch {
      Write-Host "  Windows Runtime not available: $($_.Exception.Message)"
    }
    
    # Check if we can at least read it by using Get-Content with -Raw
    try {
      $content = Get-Content $path -Raw -ErrorAction Stop
      Write-Host "  Successfully read $($content.Length) chars"
    } catch {
      Write-Host "  Read failed: $($_.Exception.Message)"
    }
  }
}