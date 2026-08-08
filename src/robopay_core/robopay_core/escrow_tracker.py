"""Local record of escrows this robot opened, so the resolver can auto-refund
expired ones.
"""
import sqlite3
from pathlib import Path

DEFAULT_PATH = Path.home() / ".robopay" / "escrows.db"


class EscrowTracker:
    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else DEFAULT_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS escrows (
                escrow_id  TEXT PRIMARY KEY,
                payer      TEXT NOT NULL,
                deadline   INTEGER NOT NULL,
                resolved   INTEGER DEFAULT 0
            )
        """)
        self._conn.commit()

    def track(self, escrow_id: bytes, payer: str, deadline: int) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO escrows (escrow_id, payer, deadline, resolved) "
            "VALUES (?, ?, ?, 0)",
            (escrow_id.hex(), payer, int(deadline)),
        )
        self._conn.commit()

    def mark_resolved(self, escrow_id: bytes) -> None:
        self._conn.execute(
            "UPDATE escrows SET resolved = 1 WHERE escrow_id = ?", (escrow_id.hex(),))
        self._conn.commit()

    def expired_unresolved(self, now: int) -> list[dict]:
        rows = self._conn.execute(
            "SELECT escrow_id, payer, deadline FROM escrows "
            "WHERE resolved = 0 AND deadline < ?", (now,)
        ).fetchall()
        return [{"escrow_id": bytes.fromhex(r[0]), "payer": r[1], "deadline": r[2]}
                for r in rows]

    def close(self) -> None:
        self._conn.close()