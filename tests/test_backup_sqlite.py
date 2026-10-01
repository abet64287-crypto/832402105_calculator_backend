"""Verify that the deployment backup is a usable SQLite snapshot."""

from __future__ import annotations

import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from src.model import HistoryRepository


BACKUP_SCRIPT = Path(__file__).resolve().parents[1] / "deploy" / "tencent" / "backup_sqlite.py"


class SqliteBackupTests(unittest.TestCase):
    def test_backup_contains_committed_history_and_can_be_opened(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_path = root / "calculations.db"
            backup_dir = root / "backups"
            backup_dir.mkdir()

            history = HistoryRepository(source_path)
            first = history.add("1+2", "3")
            completed = subprocess.run(
                [sys.executable, str(BACKUP_SCRIPT), str(source_path), str(backup_dir)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            backup_path = Path(completed.stdout.strip())
            self.assertEqual(backup_path.parent, backup_dir)
            self.assertTrue(backup_path.is_file())

            history.add("4+5", "9")
            with closing(sqlite3.connect(backup_path)) as connection:
                rows = connection.execute(
                    "SELECT id, expression, result FROM calculation_history ORDER BY id"
                ).fetchall()
                self.assertEqual(connection.execute("PRAGMA quick_check").fetchone(), ("ok",))
            self.assertEqual(rows, [(first.id, "1+2", "3")])


if __name__ == "__main__":
    unittest.main()
