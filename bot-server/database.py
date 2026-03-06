import sqlite3
import json
import secrets
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

# Считаем устройство онлайн, если была активность за последние N минут.
# Уведомление «не выходит на связь» отправляется только если дольше этого порога нет ответа.
ONLINE_THRESHOLD_MINUTES = 30


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
    # Миграция: колонки last_seen и last_offline_alert_at
    for col in ("last_seen", "last_offline_alert_at"):
        try:
            conn = sqlite3.connect(path)
            conn.execute(f"ALTER TABLE devices ADD COLUMN {col} TEXT")
            conn.commit()
            conn.close()
        except sqlite3.OperationalError:
            pass  # колонка уже есть
    # Инициализация канала
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
            "SELECT id, device_token, name, packages, last_seen, last_offline_alert_at FROM devices WHERE device_token = ?",
            (token,),
        ).fetchone()
    if not row:
        return None
    return _row_to_device(row)


def get_device_by_id(device_id: int) -> dict | None:
    with _conn() as c:
        row = c.execute(
            "SELECT id, device_token, name, packages, last_seen, last_offline_alert_at FROM devices WHERE id = ?",
            (device_id,),
        ).fetchone()
    if not row:
        return None
    return _row_to_device(row)


def _row_to_device(r) -> dict:
    return {
        "id": r["id"],
        "device_token": r["device_token"],
        "name": r["name"] or "Устройство",
        "packages": json.loads(r["packages"] or "[]"),
        "last_seen": r["last_seen"] if r["last_seen"] else None,
        "last_offline_alert_at": r["last_offline_alert_at"] if r["last_offline_alert_at"] else None,
    }


def list_devices() -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT id, device_token, name, packages, created_at, last_seen, last_offline_alert_at FROM devices ORDER BY id"
        ).fetchall()
    return [_row_to_device(r) | {"created_at": r["created_at"]} for r in rows]


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


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def update_device_last_seen(device_token: str) -> bool:
    """Обновляет last_seen и сбрасывает last_offline_alert_at. Возвращает True если устройство было в «офлайн-алерте» (т.е. только что вышло в сеть)."""
    with _conn() as c:
        row = c.execute(
            "SELECT last_offline_alert_at FROM devices WHERE device_token = ?",
            (device_token,),
        ).fetchone()
        if not row:
            return False
        had_alert = bool(row["last_offline_alert_at"])
        c.execute(
            "UPDATE devices SET last_seen = ?, last_offline_alert_at = NULL WHERE device_token = ?",
            (_now_iso(), device_token),
        )
    return had_alert


def get_devices_overdue_for_offline_alert(threshold_minutes: int = ONLINE_THRESHOLD_MINUTES) -> list[dict]:
    """Устройства, которые не выходили на связь threshold_minutes минут и по которым ещё не отправляли алерт."""
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=threshold_minutes)).isoformat()
    with _conn() as c:
        rows = c.execute(
            """SELECT id, device_token, name, packages, last_seen, last_offline_alert_at
               FROM devices
               WHERE (last_seen IS NULL OR last_seen < ?) AND (last_offline_alert_at IS NULL OR last_offline_alert_at = '')""",
            (cutoff,),
        ).fetchall()
    return [_row_to_device(r) for r in rows]


def mark_device_offline_alert_sent(device_token: str) -> None:
    with _conn() as c:
        c.execute(
            "UPDATE devices SET last_offline_alert_at = ? WHERE device_token = ?",
            (_now_iso(), device_token),
        )
