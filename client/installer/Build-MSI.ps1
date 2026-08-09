param(
    [switch]$NoPause,
    [switch]$NoElevation
)

$ErrorActionPreference = "Stop"
$Version = "0.2.0"
$Root = Split-Path $PSScriptRoot -Parent
$Project = Join-Path $Root "src\ATRoomComms.Client\ATRoomComms.Client.csproj"
$Publish = Join-Path $PSScriptRoot "Publish"
$Output = Join-Path $PSScriptRoot "Output"
$Tools = Join-Path $PSScriptRoot ".tools"
$LogDir = Join-Path $PSScriptRoot "Logs"
$LogFile = Join-Path $LogDir ("MSI-Build-{0}.log" -f (Get-Date -Format "yyyy-MM-dd_HH-mm-ss"))
$NuGetConfig = Join-Path $PSScriptRoot "NuGet.Config"
$NuGetSource = "https://api.nuget.org/v3/index.json"
$GeneratedWxs = Join-Path $PSScriptRoot "PublishedFiles.wxs"
$IconPath = Join-Path $PSScriptRoot "Assets\ATRoomComms.ico"

function Test-IsAdmin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Save-Log {
    param([System.Collections.Generic.List[string]]$Lines)
    try {
        [System.IO.File]::WriteAllLines($LogFile, $Lines, [System.Text.UTF8Encoding]::new($false))
    }
    catch {
        Write-Host "Warning: Could not write log file: $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

$LogLines = New-Object 'System.Collections.Generic.List[string]'

function Add-LogLine {
    param([string]$Message = "")
    $script:LogLines.Add($Message)
}

function Invoke-LoggedCommand {
    param(
        [Parameter(Mandatory=$true)][string]$Name,
        [Parameter(Mandatory=$true)][string]$FilePath,
        [Parameter(Mandatory=$false)][string[]]$Arguments = @()
    )

    Write-Host ""
    Write-Host $Name -ForegroundColor Cyan
    $commandLine = "> {0} {1}" -f $FilePath, ($Arguments -join " ")
    Write-Host $commandLine -ForegroundColor DarkGray
    Add-LogLine ""
    Add-LogLine $Name
    Add-LogLine $commandLine

    $commandOutput = @()
    try {
        $commandOutput = & $FilePath @Arguments 2>&1
        $code = $LASTEXITCODE
    }
    catch {
        $commandOutput += ($_ | Out-String)
        $code = 1
    }

    foreach ($item in $commandOutput) {
        $line = $item.ToString()
        Write-Host $line
        Add-LogLine $line
    }

    $exitText = "Exit code: $code"
    if ($code -eq 0) {
        Write-Host $exitText -ForegroundColor Green
    } else {
        Write-Host $exitText -ForegroundColor Red
    }
    Add-LogLine $exitText
    Save-Log $LogLines

    if ($code -ne 0) {
        throw "$Name failed with exit code $code."
    }
}


function Convert-ToWixId {
    param(
        [Parameter(Mandatory=$true)][string]$Prefix,
        [Parameter(Mandatory=$true)][string]$Value
    )

    $bytes = [System.Text.Encoding]::UTF8.GetBytes($Value.ToLowerInvariant())
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $hash = $sha.ComputeHash($bytes)
    }
    finally {
        $sha.Dispose()
    }

    $hex = -join ($hash[0..9] | ForEach-Object { $_.ToString("x2") })
    return "${Prefix}_${hex}"
}

function Escape-XmlAttribute {
    param([Parameter(Mandatory=$true)][string]$Value)
    return [System.Security.SecurityElement]::Escape($Value)
}

function New-PublishedFilesWxs {
    param(
        [Parameter(Mandatory=$true)][string]$PublishDirectory,
        [Parameter(Mandatory=$true)][string]$OutputPath
    )

    Write-Host "Generating WiX components from published files..." -ForegroundColor Cyan

    $files = Get-ChildItem -Path $PublishDirectory -File -Recurse | Sort-Object FullName
    if (-not $files) {
        throw "No published files were found in $PublishDirectory"
    }

    # Collect every directory used by a file, including every parent directory.
    # Example: runtimes\\win-x64\\native must also declare runtimes and runtimes\\win-x64.
    $directorySet = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::OrdinalIgnoreCase)

    foreach ($file in $files) {
        $relative = $file.FullName.Substring($PublishDirectory.Length).TrimStart('\\')
        $dir = Split-Path $relative -Parent

        while ($dir -and $dir -ne '.') {
            [void]$directorySet.Add($dir)
            $parent = Split-Path $dir -Parent
            if ($parent -eq '.' -or $parent -eq $dir) {
                break
            }
            $dir = $parent
        }
    }

    $relativeDirectories = @($directorySet) | Sort-Object {
        # Parents first, then alphabetical, so generated XML is deterministic.
        ($_.Split('\\').Count)
    }, { $_ }

    $directoryIds = @{}
    foreach ($relativeDir in $relativeDirectories) {
        $directoryIds[$relativeDir] = Convert-ToWixId -Prefix 'DIR' -Value $relativeDir
    }

    $lines = New-Object 'System.Collections.Generic.List[string]'
    $lines.Add('<Wix xmlns="http://wixtoolset.org/schemas/v4/wxs">')
    $lines.Add('  <Fragment>')
    $lines.Add('    <DirectoryRef Id="INSTALLFOLDER">')

    # Create a nested directory tree using explicit Directory elements.
    $children = @{}
    foreach ($relativeDir in $relativeDirectories) {
        $parent = Split-Path $relativeDir -Parent
        if ($parent -eq '.') { $parent = '' }
        if (-not $children.ContainsKey($parent)) {
            $children[$parent] = New-Object 'System.Collections.Generic.List[string]'
        }
        $children[$parent].Add($relativeDir)
    }

    function Add-DirectoryTree {
        param([string]$ParentRelative, [int]$Indent)
        if (-not $children.ContainsKey($ParentRelative)) { return }
        foreach ($relativeDir in ($children[$ParentRelative] | Sort-Object)) {
            $name = Split-Path $relativeDir -Leaf
            $id = $directoryIds[$relativeDir]
            $spaces = ' ' * $Indent
            $lines.Add(('{0}<Directory Id="{1}" Name="{2}">' -f $spaces, $id, (Escape-XmlAttribute $name)))
            Add-DirectoryTree -ParentRelative $relativeDir -Indent ($Indent + 2)
            $lines.Add("${spaces}</Directory>")
        }
    }

    Add-DirectoryTree -ParentRelative '' -Indent 6
    $lines.Add('    </DirectoryRef>')
    $lines.Add('  </Fragment>')
    $lines.Add('  <Fragment>')
    $lines.Add('    <ComponentGroup Id="PublishedFiles">')

    foreach ($file in $files) {
        $relative = $file.FullName.Substring($PublishDirectory.Length).TrimStart('\\')
        $relativeDir = Split-Path $relative -Parent
        if ($relativeDir -eq '.') { $relativeDir = '' }
        $directoryId = if ($relativeDir) { $directoryIds[$relativeDir] } else { 'INSTALLFOLDER' }
        $componentId = Convert-ToWixId -Prefix 'CMP' -Value $relative
        $fileId = Convert-ToWixId -Prefix 'FIL' -Value $relative
        $source = Escape-XmlAttribute $file.FullName
        $lines.Add(('      <Component Id="{0}" Directory="{1}" Guid="*">' -f $componentId, $directoryId))
        $lines.Add(('        <File Id="{0}" Source="{1}" KeyPath="yes" />' -f $fileId, $source))
        $lines.Add('      </Component>')
    }

    $lines.Add('    </ComponentGroup>')
    $lines.Add('  </Fragment>')
    $lines.Add('</Wix>')

    [System.IO.File]::WriteAllLines($OutputPath, $lines, [System.Text.UTF8Encoding]::new($false))
    Write-Host "Generated: $OutputPath" -ForegroundColor Green
    Add-LogLine "Generated WiX component file: $OutputPath"
    Add-LogLine "Published file count: $($files.Count)"
    Save-Log $LogLines
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

if ((-not $NoElevation) -and (-not (Test-IsAdmin))) {
    Write-Host "Requesting Administrator access..." -ForegroundColor Yellow
    $args = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", "`"$PSCommandPath`"",
        "-NoElevation"
    )
    if ($NoPause) { $args += "-NoPause" }
    $process = Start-Process powershell.exe -Verb RunAs -ArgumentList $args -PassThru
    $process.WaitForExit()
    exit $process.ExitCode
}

$success = $false
try {
    Add-LogLine "AT RoomComms Client MSI build log"
    Add-LogLine "Started: $(Get-Date -Format o)"
    Save-Log $LogLines

    Write-Host "============================================================" -ForegroundColor Magenta
    Write-Host " AT RoomComms Client v$Version - MSI Diagnostic Builder" -ForegroundColor Magenta
    Write-Host "============================================================" -ForegroundColor Magenta
    Write-Host "Build log: $LogFile"
    Write-Host "PowerShell: $($PSVersionTable.PSVersion)"
    Write-Host "Windows: $([Environment]::OSVersion.VersionString)"

    $dotnet = Get-Command dotnet.exe -ErrorAction SilentlyContinue
    if ($null -eq $dotnet) {
        throw ".NET 8 SDK is not installed or dotnet.exe is not in PATH. Install the .NET 8 SDK, not only the runtime."
    }

    Invoke-LoggedCommand -Name "Checking .NET SDK" -FilePath $dotnet.Source -Arguments @("--info")

    if (-not (Test-Path $Project)) {
        throw "Project file not found: $Project"
    }

    Remove-Item $Publish, $Output -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force -Path $Publish, $Output, $Tools | Out-Null

    if (-not (Test-Path $NuGetConfig)) {
        throw "NuGet configuration file not found: $NuGetConfig"
    }

    Write-Host "Checking access to NuGet.org..." -ForegroundColor Cyan
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $NuGetSource -Method Get -TimeoutSec 20
        Write-Host "NuGet.org reachable: HTTP $($response.StatusCode)" -ForegroundColor Green
        Add-LogLine "NuGet.org reachable: HTTP $($response.StatusCode)"
    }
    catch {
        throw "Cannot reach NuGet.org at $NuGetSource. Check internet, proxy, firewall, or TLS inspection. $($_.Exception.Message)"
    }

    Invoke-LoggedCommand -Name "[1/5] Restoring client packages from NuGet.org" -FilePath $dotnet.Source -Arguments @(
        "restore", $Project,
        "--configfile", $NuGetConfig,
        "--runtime", "win-x64",
        "--force",
        "--no-cache"
    )

    Invoke-LoggedCommand -Name "[2/5] Publishing self-contained Windows client" -FilePath $dotnet.Source -Arguments @(
        "publish", $Project,
        "-c", "Release",
        "-r", "win-x64",
        "--self-contained", "true",
        "--no-restore",
        "-p:PublishSingleFile=false",
        "-o", $Publish
    )

    $exe = Join-Path $Publish "ATRoomComms.Client.exe"
    if (-not (Test-Path $exe)) {
        throw "Publish completed but the expected EXE was not created: $exe"
    }

    New-PublishedFilesWxs -PublishDirectory $Publish -OutputPath $GeneratedWxs

    $wix = Join-Path $Tools "wix.exe"
    if (-not (Test-Path $wix)) {
        Invoke-LoggedCommand -Name "[3/5] Installing WiX 4 locally" -FilePath $dotnet.Source -Arguments @(
            "tool", "install", "wix",
            "--tool-path", $Tools,
            "--version", "4.0.5",
            "--add-source", $NuGetSource,
            "--ignore-failed-sources"
        )
    } else {
        Write-Host "[2/4] Existing WiX found: $wix" -ForegroundColor Green
    }

    if (-not (Test-Path $wix)) {
        throw "WiX installation reported success but wix.exe was not found at: $wix"
    }

    Invoke-LoggedCommand -Name "Checking WiX version" -FilePath $wix -Arguments @("--version")

    $msi = Join-Path $Output "AT-RoomComms-Client-v$Version-x64.msi"
    $wxs = Join-Path $PSScriptRoot "Package.wxs"

    if (-not (Test-Path $IconPath)) {
        throw "Installer icon was not found: $IconPath"
    }
    Write-Host "Installer icon: $IconPath" -ForegroundColor DarkGray
    Add-LogLine "Installer icon: $IconPath"

    Invoke-LoggedCommand -Name "[4/5] Building genuine MSI" -FilePath $wix -Arguments @(
        "build", $wxs, $GeneratedWxs,
        "-arch", "x64",
        "-d", "PublishDir=$Publish",
        "-d", "IconPath=$IconPath",
        "-out", $msi
    )

    if (-not (Test-Path $msi)) {
        throw "WiX returned success but the MSI was not created: $msi"
    }

    Write-Host "[5/5] Calculating SHA-256..." -ForegroundColor Cyan
    $hash = Get-FileHash $msi -Algorithm SHA256
    $hash.Hash | Set-Content "$msi.sha256" -Encoding ASCII

    Write-Host ""
    Write-Host "BUILD SUCCESSFUL" -ForegroundColor Green
    Write-Host "MSI: $msi"
    Write-Host "SHA-256: $($hash.Hash)"
    Write-Host "Log: $LogFile"
    $success = $true
}
catch {
    Write-Host ""
    Write-Host "BUILD FAILED" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host ""
    Write-Host "Full error:" -ForegroundColor Yellow
    Write-Host ($_ | Out-String)
    Write-Host "Build log: $LogFile" -ForegroundColor Yellow
    Add-LogLine ""
    Add-LogLine "BUILD FAILED"
    Add-LogLine $_.Exception.Message
    Add-LogLine ($_ | Out-String)
    Save-Log $LogLines
    $host.SetShouldExit(1)
}
finally {
    Write-Host ""
    if (-not $NoPause) {
        Write-Host "The builder will stay open. Press Enter to close." -ForegroundColor Cyan
        [void](Read-Host)
    }
}

if (-not $success) { exit 1 }
exit 0
