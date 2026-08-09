param(
    [Parameter(Mandatory=$true)][string]$MsiPath,
    [string]$ServerUrl = ""
)

$ErrorActionPreference = "Stop"
$MsiPath = (Resolve-Path $MsiPath).Path
$arguments = @("/i", "`"$MsiPath`"", "/qn", "/norestart")
if ($ServerUrl) {
    if ($ServerUrl -notmatch '^https?://') { $ServerUrl = "http://$ServerUrl" }
    $arguments += "SERVERURL=`"$($ServerUrl.TrimEnd('/'))`""
}
$process = Start-Process msiexec.exe -ArgumentList $arguments -Wait -PassThru
exit $process.ExitCode
