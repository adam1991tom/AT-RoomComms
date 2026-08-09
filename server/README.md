# AT RoomComms Server v0.2.0

This is the central local-network Docker application. It contains:

- Speaker Preview administration dashboard
- Event and room setup
- Venue, event and room chats
- Main / Backup / Speaker Preview session roles
- Priority and emergency messages
- Device heartbeat records
- Persistent SQLite database
- Modern dark-purple web interface

The future Windows room client is deliberately not included in this package.

## Install

```bash
unzip AT-RoomComms-Server-v0.2.0.zip
cd AT-RoomComms-Server-v0.2.0
sudo ./install.sh
```

Open `http://SERVER-IP:5070`.

To change the port, edit `.env` before installation:

```text
ROOMCOMMS_PORT=5070
TZ=Europe/London
```

## One-line local installation after copying the ZIP to the server

```bash
unzip -o AT-RoomComms-Server-v0.2.0.zip && cd AT-RoomComms-Server-v0.2.0 && sudo ./install.sh
```

## Operations

```bash
sudo ./update.sh
sudo ./backup.sh
./logs.sh
sudo ./remove.sh
```

`remove.sh` preserves the database. To deliberately delete the database too:

```bash
sudo ./remove.sh --delete-data
```

## Health check

```bash
curl http://localhost:5070/api/health
```

Expected response:

```json
{"status":"ok","version":"0.2.0"}
```

## Data location

Docker volume: `roomcomms-data`

Updates and normal removal do not delete this volume.

## v0.2.0 additions
- Browser opens directly in Speaker Preview mode.
- Speaker Preview can browse every active event and every room beneath it.
- Photos and file attachments up to 25 MB can be shared in venue, event and room chats.
- Uploaded files persist in the same Docker data volume under `/data/uploads`.
- Windows clients receive structured native-notification events through WebView2.
