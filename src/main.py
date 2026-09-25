"""Entry point: run with ``python -m src.main`` from calculator_backend."""

from __future__ import annotations

import os
from pathlib import Path

from .controller import create_server


def main() -> None:
    backend_root = Path(__file__).resolve().parent.parent
    database_path = os.getenv("CALCULATOR_DB_PATH", str(backend_root / "calculations.db"))
    host = os.getenv("CALCULATOR_HOST", "127.0.0.1")
    port = int(os.getenv("CALCULATOR_PORT", os.getenv("PORT", "8000")))
    allowed_origins = os.getenv("CALCULATOR_ALLOWED_ORIGINS", "*")
    try:
        server = create_server(host, port, database_path, allowed_origins)
    except (OSError, RuntimeError) as exc:
        raise SystemExit(f"Calculator API could not start on {host}:{port}: {exc}") from exc
    print(f"Calculator API listening on http://{host}:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
