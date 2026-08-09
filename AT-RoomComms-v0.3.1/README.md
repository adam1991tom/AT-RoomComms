# AT RoomComms v0.3.1

AT RoomComms is a venue operations and communications platform.

## Architecture

- Docker server: central system, database, Speaker Preview / Control Centre, events, rooms, devices, help requests, operations feeds and attachments.
- Windows client: separate room-client project will connect to this central server.

## v0.3.1 server

- Dark purple Base44-inspired Control Centre UI
- Multiple events and rooms
- Room status overview
- Venue, event and room Operations Feeds
- Help requests
- Photo and file attachments up to 25 MB
- Device registration and heartbeat API
- WebSocket live refresh
- Persistent SQLite database and upload volume
- Docker health check

## Install

Clone the repository, enter this version folder and run install.sh.

The web interface listens on port 5070.

## Data

Persistent data is stored in the Docker volume `roomcomms-data` and is not removed by normal container recreation or upgrades.
