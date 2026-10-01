"""Create a consistent SQLite backup while the calculator API is running."""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


def backup(source_path: Path, backup_dir: Path) -> Path:
    source_path = source_path.resolve(strict=True)
    backup_dir = backup_dir.resolve(strict=True)
    if not source_path.is_file() or not backup_dir.is_dir():
        raise ValueError("Source must be a database file and destination must be a directory.")

    backup_name = f"calculations-{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}.db"
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=backup_dir, prefix=".calculations-", suffix=".db", delete=False
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)

        with closing(sqlite3.connect(f"{source_path.as_uri()}?mode=ro", uri=True, timeout=30)) as source:
            with closing(sqlite3.connect(temporary_path, timeout=30)) as destination:
                source.backup(destination)
                result = destination.execute("PRAGMA quick_check").fetchone()
                if result != ("ok",):
                    raise RuntimeError(f"SQLite backup check failed: {result}")

        final_path = backup_dir / backup_name
        os.replace(temporary_path, final_path)
        return final_path
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: backup_sqlite.py DATABASE_PATH BACKUP_DIRECTORY", file=sys.stderr)
        return 2
    try:
        destination = backup(Path(sys.argv[1]), Path(sys.argv[2]))
    except (OSError, sqlite3.Error, RuntimeError, ValueError) as exc:
        print(f"SQLite backup failed: {exc}", file=sys.stderr)
        return 1
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
