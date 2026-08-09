# AT RoomComms v0.3.3

AT RoomComms is a self-hosted live-event operations and room communications platform for managing events, rooms, operators, messages, help requests, and privileged Control Centre logins from a web interface.

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
- Venue-wide operations messages
- Event operations messages
- Room operations messages
- File attachments
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

Current release: **v0.3.3**
