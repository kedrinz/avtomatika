import sqlite3
import json
import secrets
from contextlib import contextmanager
from pathlib import Path

def _db_path() -> str:
    try:
        from config import get_settings
        return get_settings().database_path
    except Exception:
        return "data/bot.db"


def ensure_db():
    path = _db_path()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_token TEXT UNIQUE NOT NULL,
                name TEXT,
                packages TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        conn.commit()
    finally:
        conn.close()
    # Инициализация канала из .env при первом запуске
    try:
        from config import get_settings
        cfg = get_settings()
        if cfg.telegram_channel_id and not _get_channel_id_raw(path):
            conn2 = sqlite3.connect(path)
            try:
                conn2.execute(
                    "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)",
                    ("channel_id", cfg.telegram_channel_id),
                )
                conn2.commit()
            finally:
                conn2.close()
    except Exception:
        pass


def _get_channel_id_raw(path: str) -> str:
    conn = sqlite3.connect(path)
    try:
        row = conn.execute("SELECT value FROM config WHERE key = ?", ("channel_id",)).fetchone()
        return (row[0] or "").strip() if row else ""
    finally:
        conn.close()


@contextmanager
def _conn():
    ensure_db()
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def create_device(name: str = "") -> str:
    token = secrets.token_urlsafe(24)
    with _conn() as c:
        c.execute(
            "INSERT INTO devices (device_token, name, packages) VALUES (?, ?, ?)",
            (token, (name or "Устройство").strip(), "[]"),
        )
    return token


def get_device_by_token(token: str) -> dict | None:
    with _conn() as c:
        row = c.execute(
            "SELECT id, device_token, name, packages FROM devices WHERE device_token = ?",
            (token,),
        ).fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "device_token": row["device_token"],
        "name": row["name"] or "Устройство",
        "packages": json.loads(row["packages"] or "[]"),
    }


def list_devices() -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT id, device_token, name, packages, created_at FROM devices ORDER BY id"
        ).fetchall()
    return [
        {
            "id": r["id"],
            "device_token": r["device_token"],
            "name": r["name"] or "Устройство",
            "packages": json.loads(r["packages"] or "[]"),
            "created_at": r["created_at"],
        }
        for r in rows
    ]


def set_device_name(device_token: str, name: str) -> bool:
    with _conn() as c:
        cur = c.execute("UPDATE devices SET name = ? WHERE device_token = ?", (name.strip(), device_token))
        return cur.rowcount > 0


def set_device_packages(device_token: str, packages: list[str]) -> bool:
    with _conn() as c:
        cleaned = [p.strip() for p in packages if p and p.strip()]
        cur = c.execute(
            "UPDATE devices SET packages = ? WHERE device_token = ?",
            (json.dumps(cleaned), device_token),
        )
        return cur.rowcount > 0


def delete_device(device_token: str) -> bool:
    with _conn() as c:
        cur = c.execute("DELETE FROM devices WHERE device_token = ?", (device_token,))
        return cur.rowcount > 0


def get_channel_id() -> str:
    with _conn() as c:
        row = c.execute("SELECT value FROM config WHERE key = ?", ("channel_id",)).fetchone()
    return (row["value"] or "").strip() if row else ""


def set_channel_id(channel_id: str) -> None:
    with _conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)",
            ("channel_id", channel_id.strip()),
        )
