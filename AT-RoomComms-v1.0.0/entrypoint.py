import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

VERSION = "1.0.0"
DATA = Path(os.getenv("ROOMCOMMS_DATA", "/data"))
DB = DATA / "roomcomms.db"
DATA.mkdir(parents=True, exist_ok=True)


def table_exists(c, table):
    return c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None


def columns(c, table):
    if not table_exists(c, table):
        return set()
    return {r[1] for r in c.execute(f"PRAGMA table_info({table})").fetchall()}


def add_column(c, table, name, sql_type_default):
    if table_exists(c, table) and name not in columns(c, table):
        print(f"[V1 migration] Adding {table}.{name}")
        c.execute(f"ALTER TABLE {table} ADD COLUMN {name} {sql_type_default}")


def migrate():
    if not DB.exists():
        print("[V1 migration] No existing database. Fresh install.")
        return

    backup = DATA / f"roomcomms-pre-v1-{datetime.now().strftime('%Y%m%d-%H%M%S')}.db"
    shutil.copy2(DB, backup)
    print(f"[V1 migration] Database backup: {backup}")

    c = sqlite3.connect(DB)
    try:
        c.execute("PRAGMA foreign_keys=OFF")

        # Sessions are temporary and changed shape during the pre-V1 builds.
        if table_exists(c, "sessions"):
            sc = columns(c, "sessions")
            if not {"token", "account_id", "created_at"}.issubset(sc):
                print("[V1 migration] Rebuilding incompatible sessions table")
                c.execute("DROP TABLE sessions")
                c.execute("CREATE TABLE sessions(token TEXT PRIMARY KEY, account_id INTEGER NOT NULL, created_at TEXT NOT NULL)")

        # Known legacy schema upgrades. ALTER TABLE preserves existing rows.
        add_column(c, "events", "client", "TEXT DEFAULT ''")
        add_column(c, "events", "event_color", "TEXT DEFAULT '#8b5cf6'")
        add_column(c, "events", "starts_at", "TEXT DEFAULT ''")
        add_column(c, "events", "ends_at", "TEXT DEFAULT ''")
        add_column(c, "events", "event_status", "TEXT DEFAULT 'scheduled'")
        add_column(c, "events", "archived", "INTEGER NOT NULL DEFAULT 0")

        add_column(c, "rooms", "short_name", "TEXT DEFAULT ''")
        add_column(c, "rooms", "current_status", "TEXT DEFAULT 'closed'")
        add_column(c, "rooms", "enabled", "INTEGER NOT NULL DEFAULT 1")

        add_column(c, "event_rooms", "operator_name", "TEXT DEFAULT ''")
        add_column(c, "operators", "active", "INTEGER NOT NULL DEFAULT 1")

        add_column(c, "accounts", "display_name", "TEXT DEFAULT ''")
        add_column(c, "accounts", "role", "TEXT DEFAULT 'speaker_preview'")
        add_column(c, "accounts", "active", "INTEGER NOT NULL DEFAULT 1")

        for name, definition in [
            ("role", "TEXT DEFAULT 'general'"),
            ("room_id", "INTEGER"),
            ("event_id", "INTEGER"),
            ("operator", "TEXT DEFAULT ''"),
            ("online_status", "TEXT DEFAULT 'offline'"),
            ("last_heartbeat", "TEXT"),
            ("app_version", "TEXT DEFAULT ''"),
        ]:
            add_column(c, "devices", name, definition)

        for name, definition in [
            ("scope", "TEXT DEFAULT 'venue'"),
            ("scope_id", "INTEGER"),
            ("sender", "TEXT DEFAULT ''"),
            ("body", "TEXT DEFAULT ''"),
            ("priority", "TEXT DEFAULT 'normal'"),
            ("created_at", "TEXT DEFAULT ''"),
        ]:
            add_column(c, "messages", name, definition)

        for name, definition in [
            ("message_id", "INTEGER"),
            ("original_name", "TEXT DEFAULT ''"),
            ("stored_name", "TEXT DEFAULT ''"),
            ("mime_type", "TEXT DEFAULT ''"),
            ("size", "INTEGER NOT NULL DEFAULT 0"),
        ]:
            add_column(c, "attachments", name, definition)

        for name, definition in [
            ("event_id", "INTEGER"),
            ("room_id", "INTEGER"),
            ("room_name", "TEXT DEFAULT ''"),
            ("requested_by", "TEXT DEFAULT ''"),
            ("category", "TEXT DEFAULT 'other'"),
            ("description", "TEXT DEFAULT ''"),
            ("priority", "TEXT DEFAULT 'important'"),
            ("status", "TEXT DEFAULT 'new'"),
            ("assigned_to", "TEXT DEFAULT ''"),
            ("created_at", "TEXT DEFAULT ''"),
            ("acknowledged_at", "TEXT"),
            ("resolved_at", "TEXT"),
        ]:
            add_column(c, "help_requests", name, definition)

        c.commit()
        print("[V1 migration] Compatibility migration complete")
    finally:
        c.close()


migrate()

# Import the proven application only after legacy schema repair.
import main

# Promote runtime identity to V1 without changing the working API surface.
main.VERSION = VERSION
main.app.version = VERSION
app = main.app
