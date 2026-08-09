from __future__ import annotations

import asyncio
import mimetypes
import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

APP_VERSION = "0.2.0"
DB_PATH = Path(os.environ.get("ROOMCOMMS_DB", "/data/roomcomms.db"))
UPLOAD_PATH = Path(os.environ.get("ROOMCOMMS_UPLOADS", "/data/uploads"))
MAX_UPLOAD_BYTES = int(os.environ.get("ROOMCOMMS_MAX_UPLOAD", str(25 * 1024 * 1024)))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
UPLOAD_PATH.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="AT RoomComms", version=APP_VERSION)
BASE = Path(__file__).parent
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
app.mount("/uploads", StaticFiles(directory=UPLOAD_PATH), name="uploads")


def db() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    return con


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_column(con: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row[1] for row in con.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        con.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db() -> None:
    with db() as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS rooms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                enabled INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                client TEXT NOT NULL DEFAULT '',
                starts_at TEXT NOT NULL,
                ends_at TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS event_rooms (
                event_id INTEGER NOT NULL,
                room_id INTEGER NOT NULL,
                PRIMARY KEY (event_id, room_id),
                FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE,
                FOREIGN KEY(room_id) REFERENCES rooms(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_name TEXT NOT NULL,
                user_name TEXT NOT NULL,
                device_role TEXT NOT NULL,
                event_id INTEGER,
                room_id INTEGER,
                last_seen TEXT NOT NULL,
                UNIQUE(device_name),
                FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE SET NULL,
                FOREIGN KEY(room_id) REFERENCES rooms(id) ON DELETE SET NULL
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_type TEXT NOT NULL,
                channel_id INTEGER,
                sender_name TEXT NOT NULL,
                device_name TEXT NOT NULL,
                body TEXT NOT NULL DEFAULT '',
                priority TEXT NOT NULL DEFAULT 'normal',
                created_at TEXT NOT NULL
            );
            """
        )
        ensure_column(con, "messages", "attachment_name", "TEXT")
        ensure_column(con, "messages", "attachment_url", "TEXT")
        ensure_column(con, "messages", "attachment_mime", "TEXT")
        ensure_column(con, "messages", "attachment_size", "INTEGER")


@app.on_event("startup")
async def startup() -> None:
    init_db()


class RoomIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class EventIn(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    client: str = Field(default="", max_length=150)
    starts_at: str
    ends_at: str
    room_ids: list[int] = []


class SessionIn(BaseModel):
    device_name: str = Field(min_length=1, max_length=100)
    user_name: str = Field(min_length=1, max_length=100)
    device_role: str
    event_id: int | None = None
    room_id: int | None = None


class MessageIn(BaseModel):
    channel_type: str
    channel_id: int | None = None
    sender_name: str
    device_name: str
    body: str = Field(default="", max_length=2000)
    priority: str = "normal"


class ConnectionManager:
    def __init__(self) -> None:
        self.connections: set[WebSocket] = set()
        self.lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self.lock:
            self.connections.add(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self.lock:
            self.connections.discard(ws)

    async def broadcast(self, payload: dict[str, Any]) -> None:
        async with self.lock:
            sockets = list(self.connections)
        dead: list[WebSocket] = []
        for ws in sockets:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        if dead:
            async with self.lock:
                for ws in dead:
                    self.connections.discard(ws)


manager = ConnectionManager()


@app.get("/", response_class=HTMLResponse)
def home() -> HTMLResponse:
    html = (BASE / "static" / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(html.replace("{{VERSION}}", APP_VERSION))


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": APP_VERSION}


@app.get("/api/bootstrap")
def bootstrap() -> dict[str, Any]:
    with db() as con:
        rooms = [dict(r) for r in con.execute("SELECT * FROM rooms WHERE enabled=1 ORDER BY name")]
        events = [dict(r) for r in con.execute("SELECT * FROM events WHERE active=1 ORDER BY starts_at")]
        mappings = [dict(r) for r in con.execute("SELECT * FROM event_rooms")]
        sessions = [dict(r) for r in con.execute(
            """SELECT s.*, e.name AS event_name, r.name AS room_name
               FROM sessions s LEFT JOIN events e ON e.id=s.event_id
               LEFT JOIN rooms r ON r.id=s.room_id ORDER BY s.user_name"""
        )]
    return {"version": APP_VERSION, "rooms": rooms, "events": events, "event_rooms": mappings, "sessions": sessions}


@app.post("/api/rooms")
async def create_room(item: RoomIn) -> dict[str, Any]:
    try:
        with db() as con:
            cur = con.execute("INSERT INTO rooms(name) VALUES(?)", (item.name.strip(),))
            room_id = cur.lastrowid
    except sqlite3.IntegrityError:
        raise HTTPException(409, "A room with that name already exists")
    await manager.broadcast({"type": "refresh"})
    return {"id": room_id, "name": item.name.strip()}


@app.delete("/api/rooms/{room_id}")
async def disable_room(room_id: int) -> dict[str, bool]:
    with db() as con:
        con.execute("UPDATE rooms SET enabled=0 WHERE id=?", (room_id,))
    await manager.broadcast({"type": "refresh"})
    return {"ok": True}


@app.post("/api/events")
async def create_event(item: EventIn) -> dict[str, Any]:
    try:
        start = datetime.fromisoformat(item.starts_at)
        end = datetime.fromisoformat(item.ends_at)
    except ValueError:
        raise HTTPException(400, "Invalid start or end date")
    if end <= start:
        raise HTTPException(400, "Event end must be after event start")
    with db() as con:
        cur = con.execute("INSERT INTO events(name,client,starts_at,ends_at) VALUES(?,?,?,?)",
                          (item.name.strip(), item.client.strip(), item.starts_at, item.ends_at))
        event_id = cur.lastrowid
        con.executemany("INSERT OR IGNORE INTO event_rooms(event_id,room_id) VALUES(?,?)",
                        [(event_id, rid) for rid in item.room_ids])
    await manager.broadcast({"type": "refresh"})
    return {"id": event_id}


@app.post("/api/events/{event_id}/archive")
async def archive_event(event_id: int) -> dict[str, bool]:
    with db() as con:
        con.execute("UPDATE events SET active=0 WHERE id=?", (event_id,))
        con.execute("UPDATE sessions SET event_id=NULL,room_id=NULL WHERE event_id=?", (event_id,))
    await manager.broadcast({"type": "refresh"})
    return {"ok": True}


@app.post("/api/session")
async def upsert_session(item: SessionIn) -> dict[str, Any]:
    if item.device_role not in {"main", "backup", "speaker_preview"}:
        raise HTTPException(400, "Invalid device role")
    with db() as con:
        con.execute(
            """INSERT INTO sessions(device_name,user_name,device_role,event_id,room_id,last_seen)
               VALUES(?,?,?,?,?,?) ON CONFLICT(device_name) DO UPDATE SET
               user_name=excluded.user_name,device_role=excluded.device_role,event_id=excluded.event_id,
               room_id=excluded.room_id,last_seen=excluded.last_seen""",
            (item.device_name.strip().upper(), item.user_name.strip(), item.device_role,
             item.event_id, item.room_id, now_iso()))
    await manager.broadcast({"type": "refresh"})
    return {"ok": True}


@app.post("/api/heartbeat")
def heartbeat(payload: dict[str, str]) -> dict[str, bool]:
    device_name = payload.get("device_name", "").strip().upper()
    if not device_name:
        raise HTTPException(400, "device_name required")
    with db() as con:
        con.execute("UPDATE sessions SET last_seen=? WHERE device_name=?", (now_iso(), device_name))
    return {"ok": True}


def validate_channel(channel_type: str, priority: str) -> None:
    if channel_type not in {"venue", "event", "room"}:
        raise HTTPException(400, "Invalid channel type")
    if priority not in {"normal", "important", "urgent", "emergency"}:
        raise HTTPException(400, "Invalid priority")


def insert_message(message: dict[str, Any]) -> dict[str, Any]:
    with db() as con:
        cur = con.execute(
            """INSERT INTO messages(channel_type,channel_id,sender_name,device_name,body,priority,created_at,
               attachment_name,attachment_url,attachment_mime,attachment_size)
               VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (message["channel_type"], message["channel_id"], message["sender_name"], message["device_name"],
             message["body"], message["priority"], message["created_at"], message.get("attachment_name"),
             message.get("attachment_url"), message.get("attachment_mime"), message.get("attachment_size")))
        message["id"] = cur.lastrowid
    return message


@app.get("/api/messages")
def list_messages(channel_type: str, channel_id: int | None = None) -> list[dict[str, Any]]:
    validate_channel(channel_type, "normal")
    with db() as con:
        if channel_type == "venue":
            rows = con.execute("SELECT * FROM messages WHERE channel_type='venue' ORDER BY id DESC LIMIT 200").fetchall()
        else:
            rows = con.execute("SELECT * FROM messages WHERE channel_type=? AND channel_id=? ORDER BY id DESC LIMIT 200",
                               (channel_type, channel_id)).fetchall()
    return [dict(r) for r in reversed(rows)]


@app.post("/api/messages")
async def send_message(item: MessageIn) -> dict[str, Any]:
    validate_channel(item.channel_type, item.priority)
    if not item.body.strip():
        raise HTTPException(400, "Message text is required when no attachment is supplied")
    message = insert_message({
        "channel_type": item.channel_type, "channel_id": item.channel_id,
        "sender_name": item.sender_name.strip(), "device_name": item.device_name.strip().upper(),
        "body": item.body.strip(), "priority": item.priority, "created_at": now_iso(),
        "attachment_name": None, "attachment_url": None, "attachment_mime": None, "attachment_size": None,
    })
    await manager.broadcast({"type": "message", "message": message})
    return message


def safe_filename(name: str) -> str:
    base = Path(name).name
    clean = re.sub(r"[^A-Za-z0-9._ -]", "_", base).strip(" .")
    return clean[:180] or "attachment"


@app.post("/api/messages/upload")
async def upload_message(
    channel_type: str = Form(...), channel_id: str = Form(""), sender_name: str = Form(...),
    device_name: str = Form(...), body: str = Form(""), priority: str = Form("normal"),
    attachment: UploadFile = File(...),
) -> dict[str, Any]:
    validate_channel(channel_type, priority)
    content = await attachment.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"Attachment exceeds {MAX_UPLOAD_BYTES // (1024*1024)} MB")
    original = safe_filename(attachment.filename or "attachment")
    ext = Path(original).suffix[:12]
    stored = f"{uuid.uuid4().hex}{ext}"
    (UPLOAD_PATH / stored).write_bytes(content)
    mime = attachment.content_type or mimetypes.guess_type(original)[0] or "application/octet-stream"
    parsed_channel_id = int(channel_id) if channel_id.strip() else None
    message = insert_message({
        "channel_type": channel_type, "channel_id": parsed_channel_id,
        "sender_name": sender_name.strip(), "device_name": device_name.strip().upper(),
        "body": body.strip(), "priority": priority, "created_at": now_iso(),
        "attachment_name": original, "attachment_url": f"/uploads/{stored}",
        "attachment_mime": mime, "attachment_size": len(content),
    })
    await manager.broadcast({"type": "message", "message": message})
    return message


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    await manager.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except (WebSocketDisconnect, Exception):
        await manager.disconnect(ws)
