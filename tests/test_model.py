import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from src.model import HistoryRepository


class HistoryRepositoryStartupTests(unittest.TestCase):
    def test_read_only_database_fails_at_startup(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "history.db"
            HistoryRepository(database_path)
            real_connect = sqlite3.connect

            def read_only_connect(*_args, **_kwargs):
                return real_connect(database_path.resolve().as_uri() + "?mode=ro", uri=True)

            with patch("src.model.sqlite3.connect", side_effect=read_only_connect):
                with self.assertRaisesRegex(RuntimeError, "SQLite database is not writable"):
                    HistoryRepository(database_path)

            with closing(real_connect(database_path)) as connection:
                count = connection.execute("SELECT COUNT(*) FROM calculation_history").fetchone()[0]
            self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
