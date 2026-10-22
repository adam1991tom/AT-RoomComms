# AT RoomComms v0.4.0

AT RoomComms is a self-hosted live-event operations and room communications platform for managing events, rooms, operators, messages, help requests, and privileged Control Centre logins from a web interface.

## What changed in v0.4.0

Room laptops can now sign themselves in as the actual room, instead of everyone sharing the Control Centre login:

- **Operator room sign-in.** A room laptop picks its operator name from the list Control Centre has already set up (no password), plus the event, the room, and whether it's the Main or Backup PC for that session. That session only sees its own room's Operations Feed — not other rooms, not the venue or event feeds, not the Control Centre navigation. Admin and Speaker Preview logins are unchanged and still see everything.
- **Emergency reply threads.** Replying to an emergency-priority room message opens a private thread visible only to Control Centre and whoever raised the alert — not the rest of the room, even other operators sharing that room's Main/Backup PCs.
- **Direct messages.** Simple person-to-person messaging (`/api/dm`) between any two logged-in people; a room operator can only message Control Centre accounts, not other operators.
- **Daily sign-out.** A configurable UTC cutoff (System Settings, default `03:00`) logs *everyone* out — Admin, Speaker Preview, and every room operator session — enforced on every request rather than a timer alone, so it can't be skipped by a container restart landing near the cutoff.

Known gaps, deliberately left for a later pass: room status changes are still Control-Centre-only (an operator sees their room's status but can't change it), and Main/Backup notification suppression needs real Windows notification logic in the dedicated client — the current client is a plain embedded browser window, so it can't yet distinguish "silent, no popups" (Main) from "quiet visual alert" (Backup).

This adds `operator_sessions` and a few `messages` columns (`sender_kind`, `to_kind`, `to_id`), applied automatically on boot like every other schema change in this app — no manual DB work on upgrade.

## What changed in v0.3.4

The venue/event/room operations feeds ("chat") were overhauled:

- **Live updates.** A WebSocket connection (`/ws`, token-authenticated) pushes new messages, edits, and deletions to every open feed instantly — no more reopening a room to see new messages. A connection indicator in the sidebar shows Live / Connecting / Reconnecting, and the client auto-reconnects with backoff if the socket drops.
- **Chat-style layout.** Messages now render as bubbles, your own messages align right, others align left, and the feed auto-scrolls to the newest message.
- **Priority colour coding.** Important/urgent/emergency messages get a visible pill and border colour instead of plain text, so an emergency message actually stands out.
- **Edit and delete.** You can edit or delete your own messages (admins can edit/delete any message); edits show an "edited" marker and deletions are soft-deleted (kept in the database, hidden from the feed) rather than destroyed.
- **Inline image previews** for image attachments instead of a bare filename link.
- **Enter to send** in all three composers (room, event, venue).

This required a small schema addition (`messages.sender_id`, `edited_at`, `deleted_at`), applied automatically via the existing migration-on-boot pattern — no manual DB changes needed on upgrade.

## What changed in v0.3.3

v0.3.3 replaces hard-coded default credentials with a proper First Run Setup Wizard.

On first launch, AT RoomComms now asks you to create:

- Venue name
- Control Centre name
- Administrator display name
- Administrator username
- Administrator password
- Speaker Preview display name
- Speaker Preview username
- Speaker Preview password

No default `changeme` password is created in this release.

The wizard only appears until setup has been completed successfully.

## Existing installations

The existing persistent Docker volume `roomcomms-data` is reused.

When upgrading from v0.3.2, existing event, room, operator, message, attachment, device, and help-request data is retained.

Because v0.3.2 used seeded privileged accounts, v0.3.3 intentionally treats an installation without the `setup_complete` setting as requiring first-run setup. Completing the wizard rebuilds the privileged login accounts while preserving the operational data in the database.

## Login roles

### Room operator (new in v0.4.0)

Signs in from a room laptop by picking their name, event, room, and Main/Backup role — no password. Sees only their own room's Operations Feed, can send Help Requests, and can message Control Centre directly or privately follow up on an emergency they raised. Cannot see other rooms, the venue/event feeds, or any Control Centre management page.

### Administrator

Administrator accounts have full access to:

- Events
- Rooms
- Operators
- Operations feeds
- Help requests
- System settings
- Login account management

### Speaker Preview

Speaker Preview accounts can manage operational content including:

- Events
- Room assignments
- Operator assignments
- Room status
- Venue, event, and room operations feeds
- Help requests

Speaker Preview users cannot manage system settings or privileged login accounts.

## Operators

Room operators are deliberately separate from login accounts.

Operators are simple names used for room assignment, for example:

- Adam
- James
- Sarah

They do not need usernames or passwords.

## Event and room management

AT RoomComms supports:

- Create, edit, and delete events
- Create, edit, and remove rooms
- Assign rooms to events
- Assign an operator to each event-room combination
- Change live room status
- Venue-wide, event, and room operations feeds with live updates over WebSocket, priority colour coding, and message edit/delete
- File attachments with inline image previews
- Help requests
- Acknowledge and resolve help requests

## Room statuses

Supported room statuses include:

- Closed
- Setting Up
- Ready
- Rehearsal
- Live
- Technical Issue

## Persistent data

The Docker deployment uses the named volume:

```text
roomcomms-data
```

Do not delete this volume if you want to keep your RoomComms configuration and operational history.

## Install

From the repository root:

```bash
cd AT-RoomComms-v0.3.3
chmod +x install.sh
./install.sh
```

Then open:

```text
http://SERVER-IP:5070
```

The First Run Setup Wizard will appear automatically if setup has not yet been completed.

## Docker Compose

You can also start AT RoomComms manually with:

```bash
docker compose up -d --build
```

To view the service status:

```bash
docker compose ps
```

To view logs:

```bash
docker compose logs -f at-roomcomms
```

## Health check

The server exposes:

```text
/api/health
```

A healthy response includes the running version number.

## Port

AT RoomComms listens on:

```text
5070/tcp
```

## Upgrade notes

The installer removes and recreates only the `at-roomcomms` container. The persistent `roomcomms-data` Docker volume is left intact.

If an older RoomComms data volume is detected during first installation of the permanent volume, the installer attempts to migrate that data into `roomcomms-data` before starting the new container.

## Version

Current release: **v0.4.0**
