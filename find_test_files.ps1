$storagePath = 'C:\Users\tbaltzakis\CrossDevice\Galaxy S22+ (2)\storage'
$testFiles = Get-ChildItem -Recurse $storagePath -File | Where-Object { $_.Name -match 'test_' }
foreach ($f in $testFiles) {
  Write-Host "$($f.FullName) : $($f.Attributes)"
}