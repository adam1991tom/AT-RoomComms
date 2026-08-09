# AT RoomComms

AT RoomComms is a self-hosted live-event operations and room communications platform.

## Current stable release

**AT RoomComms v1.0.0**

Source folder:

```text
AT-RoomComms-v1.0.0
```

Install / upgrade on the Linux Docker server:

```bash
cd /opt/at-roomcomms && \
sudo git fetch origin main && \
sudo git reset --hard origin/main && \
cd AT-RoomComms-v1.0.0 && \
sudo chmod +x install.sh && \
sudo ./install.sh
```

Then open:

```text
http://SERVER-IP:5070
```

V1 keeps its operational database and uploads in the permanent Docker volume `roomcomms-data` and includes automatic compatibility repairs for older pre-V1 RoomComms database schemas.

See `AT-RoomComms-v1.0.0/README.md` for full release documentation.
