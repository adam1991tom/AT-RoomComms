# AT RoomComms v0.3.2

Management and authentication release.

## Login accounts

Administrator:
- Username: `adam`
- Initial password: `changeme`
- Full access to events, rooms, operators, login accounts and system settings.

Speaker Preview:
- Username: `speakerpreview`
- Initial password: `changeme`
- Can manage events, room assignments and operator names.
- Cannot access administrator-only system settings or privileged login account management.

Change the initial passwords after first sign-in.

## Operators

Room operators are intentionally not login accounts. They are simple names such as Adam, James or Sarah and can be created from the Operators page and assigned independently to each room inside an event.

## Event management

v0.3.2 adds:
- Create events
- Edit events
- Delete events
- Assign and remove rooms inside each event
- Assign an operator name to each event/room combination
- Create, edit and disable rooms
- Create and remove operator names
- Persistent assignments in SQLite

## Upgrading

The existing Docker volume `roomcomms-data` is reused. On startup the server migrates the existing `event_rooms` table by adding `operator_name` when required, so existing RoomComms data is retained.

## Install

From the repository root:

```bash
cd AT-RoomComms-v0.3.2
chmod +x install.sh
./install.sh
```

Open `http://SERVER-IP:5070`.
