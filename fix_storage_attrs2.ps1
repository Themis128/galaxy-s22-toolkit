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
    
    # Clear the OneDrive offline/reparse attributes using Clear-ItemProperty
    # These are stored as extended attributes
    try {
      # Remove the ReparsePoint attribute
      $file.Attributes = $file.Attributes -band -bnot [System.IO.FileAttributes]::ReparsePoint
      # Remove the Offline attribute  
      $file.Attributes = $file.Attributes -band -bnot [System.IO.FileAttributes]::Offline
      # Remove the RecallOnDataAccess attribute
      $file.Attributes = $file.Attributes -band -bnot [System.IO.FileAttributes]::RecallOnDataAccess
      $file.IsReadOnly = $false
      
      # Force the file to be downloaded by reading it
      $content = Get-Content $path -Raw -ErrorAction SilentlyContinue
      if ($content -ne $null) {
        Write-Host "  Successfully read content (forced download)"
      }
    } catch {
      Write-Host "  Error: $_"
    }
    
    Write-Host ("  -> {0}" -f $file.Attributes)
  }
}