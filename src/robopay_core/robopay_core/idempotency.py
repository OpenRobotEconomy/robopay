"""Durable record of payment attempts, for crash-safe and network-safe transfers.
"""
import json
import sqlite3
from pathlib import Path

DEFAULT_PATH = Path.home() / ".robopay" / "payments.db"


class IdempotencyStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else DEFAULT_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False, timeout=5.0)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                key         TEXT PRIMARY KEY,
                status      TEXT NOT NULL,
                tx_hash     TEXT,
                nonce       INTEGER,
                request     TEXT,
                result      TEXT,
                updated_at  REAL DEFAULT (strftime('%s','now'))
            )
        """)
        self._conn.commit()

    def get(self, key: str) -> dict | None:
        row = self._conn.execute(
            "SELECT key, status, tx_hash, nonce, request, result "
            "FROM payments WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return None
        return {
            "key": row[0], "status": row[1], "tx_hash": row[2], "nonce": row[3],
            "request": json.loads(row[4]) if row[4] else None,
            "result": json.loads(row[5]) if row[5] else None,
        }

    def mark_pending(self, key: str, request: dict) -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO payments (key, status, request) VALUES (?, 'pending', ?)",
            (key, json.dumps(request)),
        )
        self._conn.commit()

    def mark_broadcast(self, key: str, tx_hash: str, nonce: int) -> None:
        self._conn.execute(
            "UPDATE payments SET status='broadcast', tx_hash=?, nonce=?, "
            "updated_at=strftime('%s','now') WHERE key=?",
            (tx_hash, nonce, key),
        )
        self._conn.commit()

    def mark_final(self, key: str, status: str, result: dict) -> None:
        self._conn.execute(
            "UPDATE payments SET status=?, result=?, "
            "updated_at=strftime('%s','now') WHERE key=?",
            (status, json.dumps(result), key),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def list_by_status(self, status: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT key FROM payments WHERE status = ?", (status,)
        ).fetchall()
        return [self.get(r[0]) for r in rows]