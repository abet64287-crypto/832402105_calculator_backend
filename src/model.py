"""SQLite persistence for successful calculations."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime, timezone
from pathlib import Path

from .service import decimal_to_json_number


@dataclass(frozen=True)
class HistoryRecord:
    id: int
    expression: str
    result: int | float
    result_text: str
    created_at: str

    def to_dict(self) -> dict[str, int | float | str]:
        return {
            "id": self.id,
            "expression": self.expression,
            "result": self.result,
            "result_text": self.result_text,
            "created_at": self.created_at,
        }


class HistoryRepository:
    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path).expanduser()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self._connect() as connection:
                connection.execute(
                    """CREATE TABLE IF NOT EXISTS calculation_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        expression TEXT NOT NULL,
                        result TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )"""
                )
            # A no-op transaction may succeed on a read-only database. Actually
            # write a row and roll it back to verify INSERT/DELETE capability.
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                try:
                    connection.execute(
                        "INSERT INTO calculation_history (expression, result, created_at) VALUES (?, ?, ?)",
                        ("startup-probe", "0", "startup-probe"),
                    )
                finally:
                    connection.rollback()
        except sqlite3.Error as exc:
            raise RuntimeError(f"SQLite database is not writable at {self.database_path}: {exc}") from exc

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def add(self, expression: str, stored_result: str) -> HistoryRecord:
        created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO calculation_history (expression, result, created_at) VALUES (?, ?, ?)",
                (expression, stored_result, created_at),
            )
            record_id = cursor.lastrowid
        assert record_id is not None
        return HistoryRecord(record_id, expression, decimal_to_json_number(Decimal(stored_result)), stored_result, created_at)

    def list(self) -> list[HistoryRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, expression, result, created_at FROM calculation_history ORDER BY id DESC"
            ).fetchall()
        return [
            HistoryRecord(
                row["id"], row["expression"], decimal_to_json_number(Decimal(row["result"])),
                row["result"], row["created_at"],
            )
            for row in rows
        ]

    def delete(self, record_id: int) -> bool:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM calculation_history WHERE id = ?", (record_id,))
            return cursor.rowcount > 0
