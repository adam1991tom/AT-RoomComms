# AT RoomComms Client v0.4.0 — Genuine MSI

This is the separate Windows client for the **AT RoomComms Server** (self-hosted event operations platform). It is a thin native shell around the server's own web app — most features live server-side and just need the current server version, not a specific client build.

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
installer\Output\AT-RoomComms-Client-v0.4.0-x64.msi
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
msiexec.exe /i "AT-RoomComms-Client-v0.4.0-x64.msi" /qn /norestart
```

With the server preconfigured:

```cmd
msiexec.exe /i "AT-RoomComms-Client-v0.4.0-x64.msi" /qn /norestart SERVERURL="http://10.100.70.101:5070"
```

## Action1

Upload the MSI as a custom package and use:

```cmd
msiexec.exe /i "AT-RoomComms-Client-v0.4.0-x64.msi" /qn /norestart SERVERURL="http://10.100.70.101:5070"
```

Alternatively upload `Deployment\Install-Action1.ps1` with the MSI and run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Install-Action1.ps1 -MsiPath .\AT-RoomComms-Client-v0.4.0-x64.msi -ServerUrl "http://10.100.70.101:5070"
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

## v0.3.0 — the notification bridge actually works now
The client has always listened for `window.chrome.webview.postMessage({type:'notification',...})`
from the page, but the web app never sent it — so v0.2.0's balloon-tip feature was dead on
arrival regardless of client version. The server's web app now posts a notification for every
DM, help request, emergency alert, venue broadcast, room message (on Backup PC), and reported
issue, and correctly stays silent on Main PC per the existing device-role rule.

The web app also now reads the `device` and `clientVersion` query parameters this client already
sent and registers the machine with `/api/devices/register` (with a heartbeat every 5 minutes),
so devices actually show up server-side instead of that endpoint going unused.

This client works against any current AT RoomComms server — there is no longer a pinned minimum
server version; it degrades gracefully (no native notifications, no device registration) against
an older server that lacks these endpoints.

## v0.4.0 — a real background app, not a browser window

- **Tray icon.** Closing the window minimizes to the tray instead of quitting (one-time
  balloon explains this the first time). Right-click the tray icon for Open, Speaker
  Preview, Settings, Check for Updates, and Quit. Both minimize-to-tray and desktop
  notifications can be turned off from Settings.
- **Settings window.** Replaces the old `--change-server` relaunch hack: server address +
  test connection, minimize-to-tray, launch-at-startup, notifications, and a manual
  "Check for updates" button, all in one place (Start menu or the tray menu).
- **Real branding.** The app/taskbar/tray icon is now the actual AT RoomComms gear+bubble
  mark instead of a generic placeholder, and every window shares one blue brand palette
  (`Branding.cs`) instead of ad-hoc colors per form.
- **Telemetry.** Every 20 seconds the client checks (via a lightweight process/window
  check, not COM automation) whether PowerPoint is running a slideshow, and tracks its
  own uptime, pushing both to the page for the server's Devices admin page to show. This
  needs server v0.7.0 or later — it degrades harmlessly (data just isn't sent) against
  an older server.
- **Self-updating.** On launch, and on demand from Settings or the tray menu, the client
  checks this repo's GitHub Releases for the newest `client-v*` tag. If it's newer, it
  downloads the MSI and runs a machine-wide silent upgrade (`msiexec /qn`). If the running
  process isn't already elevated, Windows will still show a UAC prompt for that install —
  there's no way around that without a separate always-elevated updater service, which is
  more machinery than this warrants right now.
- **Startup registration moved per-user.** The old machine-wide `HKLM` Run key (couldn't
  be overridden by an individual user) is replaced by a per-user `HKCU` key the app
  manages itself, defaulting to on so a fresh install still starts automatically. It
  re-applies this on every launch, so it self-heals if something else clears the key.
