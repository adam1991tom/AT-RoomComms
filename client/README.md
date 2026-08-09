# AT RoomComms Client v0.2.0 — Genuine MSI

This is the separate Windows client for **AT RoomComms Server v0.2.0**.

## Client features

- Native Windows desktop application
- Embedded Microsoft Edge WebView2 interface
- Automatically sends the Windows computer name to the server
- First-run local server setup
- Tests `/api/health` before saving the server address
- Server address can be changed from the Start menu
- Starts automatically for every Windows user
- Modern dark-purple shell matching the RoomComms design
- Main, Backup and Speaker Preview behaviour remains controlled by the RoomComms server/web interface
- Self-contained .NET 8 application; the laptop does not need the .NET runtime installed
- Genuine machine-wide WiX MSI
- Silent Action1 deployment support
- In-place MSI upgrades using a stable UpgradeCode

## Build the MSI

Use a Windows 10/11 x64 build computer with the **.NET 8 SDK** and internet access.

Double-click:

```text
installer\BUILD-MSI.cmd
```

The builder requests Administrator permission, publishes the client, downloads WiX locally, and creates:

```text
installer\Output\AT-RoomComms-Client-v0.2.0-x64.msi
```

## Normal installation

Double-click the MSI. On first launch, enter the Docker server address, for example:

```text
10.100.70.101:5070
```

The client checks:

```text
http://SERVER:5070/api/health
```

before saving it.

## Silent MSI installation

Without a preconfigured server:

```cmd
msiexec.exe /i "AT-RoomComms-Client-v0.2.0-x64.msi" /qn /norestart
```

With the server preconfigured:

```cmd
msiexec.exe /i "AT-RoomComms-Client-v0.2.0-x64.msi" /qn /norestart SERVERURL="http://10.100.70.101:5070"
```

## Action1

Upload the MSI as a custom package and use:

```cmd
msiexec.exe /i "AT-RoomComms-Client-v0.2.0-x64.msi" /qn /norestart SERVERURL="http://10.100.70.101:5070"
```

Alternatively upload `Deployment\Install-Action1.ps1` with the MSI and run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Install-Action1.ps1 -MsiPath .\AT-RoomComms-Client-v0.2.0-x64.msi -ServerUrl "http://10.100.70.101:5070"
```

## Installed locations

Application:

```text
C:\Program Files\AT RoomComms Client
```

Machine configuration:

```text
HKLM\SOFTWARE\AT Software\AT RoomComms Client
```

A user changing the server creates a per-user override at:

```text
HKCU\SOFTWARE\AT Software\AT RoomComms Client
```

## WebView2

Windows 11 normally includes the Evergreen WebView2 Runtime. The client detects when it is missing and shows a clear message rather than silently failing.

## Important build note

The project is complete, but the MSI binary must be compiled on Windows because this workspace does not have the Windows .NET SDK or Windows Installer build environment.


## Diagnostic builder

Run `installer\BUILD-MSI.cmd`. The window always remains open and the complete output is saved under `installer\Logs`.


## v0.2.0 logging fix

The builder no longer uses `Start-Transcript` and `Tee-Object` on the same log file. Native command output is captured to a temporary file, displayed, then safely appended to the permanent log.


## v0.2.0 build fix

This builder includes its own `installer\NuGet.Config`, explicitly restores WebView2 from `https://api.nuget.org/v3/index.json`, checks internet access first, and then publishes with `--no-restore`. It also installs WiX using the same explicit NuGet source.


## WiX licensing/build fix

This revision pins the local MSI builder to WiX Toolset 4.0.5. WiX 7 requires explicit OSMF EULA acceptance and caused WIX7015. WiX 4 builds the same v4-schema Package.wxs without that v7 acceptance gate.


## v0.2.0 build fix

The builder now generates a valid WiX 4 component for every published application file. It no longer uses the unsupported `<Files>` element.


## v0.2.0 packaging fix

The WiX file generator now declares every parent directory before components reference nested runtime directories. This fixes WIX0094 missing Directory identifiers.


## v0.2.0 packaging fix

The WiX icon now uses an absolute build variable rather than a working-directory-relative path. The builder verifies the icon exists before invoking WiX and records the resolved path in the build log.

## v0.2.0 additions
- Native Windows notification-area pop-ups from live RoomComms messages.
- Main PC mode remains fully notification-free.
- Backup PC and Speaker Preview modes receive visual notifications.
- A dedicated **Speaker Preview** button is available in the client top bar.
- Speaker Preview displays every active event with all its rooms beneath it.
- Photos and file attachments are displayed and downloadable inside the client.

This client requires **AT RoomComms Server v0.2.0 or later** for attachments and native notification events.
