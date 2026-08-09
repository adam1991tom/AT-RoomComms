$ErrorActionPreference = "Stop"
$product = Get-CimInstance Win32_Product | Where-Object { $_.Name -eq "AT RoomComms Client" } | Select-Object -First 1
if (-not $product) { exit 0 }
$process = Start-Process msiexec.exe -ArgumentList @('/x', $product.IdentifyingNumber, '/qn', '/norestart') -Wait -PassThru
exit $process.ExitCode
