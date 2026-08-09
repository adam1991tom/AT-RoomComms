# AT RoomComms v1.0.0

AT RoomComms is a self-hosted live-event operations and room communications platform.

## V1 production baseline

Version 1.0.0 promotes the current RoomComms feature set to the first stable release and adds a compatibility/migration layer for older RoomComms databases.

V1 includes:

- First-run setup wizard for Administrator and Speaker Preview accounts
- Administrator-only system settings and privileged login management
- Speaker Preview operational management permissions
- Events that can be created, edited and removed
- Rooms that can be created, edited, removed and assigned to events
- Simple room operator names that do not require logins
- Room status management
- Venue, event and room Operations Feeds
- File and photo attachments
- Help requests with acknowledge and resolve workflow
- Device registration and heartbeat API for the Windows client
- Persistent SQLite database and uploads in the `roomcomms-data` Docker volume
- Automatic database compatibility repairs for pre-V1 installations

## Database upgrade protection

V1 checks the existing SQLite schema before RoomComms starts. It repairs known legacy differences including the old `sessions` table and missing columns such as `events.archived`, while keeping operational data intact.

The `sessions` table contains temporary login sessions only, so V1 may rebuild that table when an incompatible legacy layout is detected. Event, room, operator, message, attachment and help-request data is not intentionally removed by the migration.

## Install / upgrade

From a clone of this repository:

```bash
cd AT-RoomComms-v1.0.0
sudo chmod +x install.sh
sudo ./install.sh
```

Then open:

```text
http://SERVER-IP:5070
```

## Existing installations

The permanent Docker volume is:

```text
roomcomms-data
```

Do not delete this volume if you want to keep RoomComms data.

The V1 installer creates a timestamped database backup inside the Docker volume before starting the new V1 container when an existing database is present.

## Health check

```bash
curl http://localhost:5070/api/health
```

Expected version:

```json
{"status":"ok","version":"1.0.0"}
```

## Permissions

**Administrator** has full control, including system settings and privileged login accounts.

**Speaker Preview** can manage events, rooms, operators, assignments, statuses, Operations Feeds and help requests, but cannot change administrator-only system/security settings.

**Room operators** are just names. They do not require a username, password or login account.

## Upgrade source

V1 uses the proven v0.3.3 application as its functional baseline and applies V1 migration, versioning and frontend reliability fixes during the Docker build/startup process.

Current release: **AT RoomComms v1.0.0**
