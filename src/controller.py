"""HTTP/JSON endpoints for the calculator service."""

from __future__ import annotations

import json
import logging
import re
import socket
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .model import HistoryRepository
from .service import CalculationError, decimal_to_json_number, decimal_to_storage, evaluate


MAX_REQUEST_BYTES = 16 * 1024
MAX_RECORD_ID = 2**63 - 1
HISTORY_ITEM_PATH = re.compile(r"^/api/history/([1-9][0-9]*)$")


class ExclusiveThreadingHTTPServer(ThreadingHTTPServer):
    """Prevent two calculator processes from serving the same address."""

    allow_reuse_address = False

    def server_bind(self) -> None:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


@dataclass(frozen=True)
class ApiError(Exception):
    status: HTTPStatus
    code: str
    message: str


class CalculatorService:
    def __init__(self, repository: HistoryRepository):
        self.repository = repository

    def calculate(self, expression: Any) -> dict[str, Any]:
        value = evaluate(expression)
        decimal_to_json_number(value)  # Validate JSON range before committing history.
        record = self.repository.add(expression.strip(), decimal_to_storage(value))
        return {"success": True, **record.to_dict()}

    def history(self) -> dict[str, Any]:
        return {"success": True, "history": [item.to_dict() for item in self.repository.list()]}

    def delete(self, record_id: int) -> dict[str, Any]:
        if not self.repository.delete(record_id):
            raise ApiError(HTTPStatus.NOT_FOUND, "RECORD_NOT_FOUND", "History record was not found.")
        return {"success": True, "id": record_id}


def create_server(
    host: str,
    port: int,
    database_path: str,
    allowed_origins: str = "*",
) -> ExclusiveThreadingHTTPServer:
    service = CalculatorService(HistoryRepository(database_path))
    origins = {origin.strip() for origin in allowed_origins.split(",") if origin.strip()}

    class RequestHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def _cors_origin(self) -> str | None:
            if "*" in origins:
                return "*"
            request_origin = self.headers.get("Origin")
            return request_origin if request_origin in origins else None

        def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
            data = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            if (origin := self._cors_origin()) is not None:
                self.send_header("Access-Control-Allow-Origin", origin)
                if origin != "*":
                    self.send_header("Vary", "Origin")
            self.end_headers()
            self.wfile.write(data)

        def _error(self, status: HTTPStatus, code: str, message: str) -> None:
            self._send_json(status, {"success": False, "error": {"code": code, "message": message}})

        def _run(self, action) -> None:
            try:
                action()
            except CalculationError as exc:
                self._error(HTTPStatus.BAD_REQUEST, exc.code, exc.message)
            except ApiError as exc:
                self._error(exc.status, exc.code, exc.message)
            except Exception:
                logging.exception("Unhandled calculator request error")
                self._error(HTTPStatus.INTERNAL_SERVER_ERROR, "INTERNAL_ERROR", "An internal server error occurred.")

        def _path(self) -> str:
            return self.path.split("?", 1)[0]

        def _read_json_object(self) -> dict[str, Any]:
            content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if content_type != "application/json":
                raise ApiError(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "UNSUPPORTED_MEDIA_TYPE", "Content-Type must be application/json.")
            length_header = self.headers.get("Content-Length")
            if length_header is None or not length_header.isdecimal():
                raise ApiError(HTTPStatus.LENGTH_REQUIRED, "INVALID_CONTENT_LENGTH", "A valid Content-Length is required.")
            length = int(length_header)
            if length > MAX_REQUEST_BYTES:
                raise ApiError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "REQUEST_TOO_LARGE", "Request body is too large.")
            try:
                value = json.loads(
                    self.rfile.read(length).decode("utf-8"),
                    parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Non-finite JSON number")),
                )
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                raise ApiError(HTTPStatus.BAD_REQUEST, "INVALID_JSON", "Request body must contain valid JSON.") from exc
            if not isinstance(value, dict):
                raise ApiError(HTTPStatus.BAD_REQUEST, "INVALID_REQUEST", "Request body must be a JSON object.")
            return value

        def do_GET(self) -> None:
            def action() -> None:
                if self._path() == "/api/history":
                    self._send_json(HTTPStatus.OK, service.history())
                elif self._path() == "/api/health":
                    self._send_json(HTTPStatus.OK, {"success": True, "status": "ok"})
                else:
                    raise ApiError(HTTPStatus.NOT_FOUND, "NOT_FOUND", "Endpoint was not found.")

            self._run(action)

        def do_POST(self) -> None:
            def action() -> None:
                if self._path() != "/api/calculate":
                    raise ApiError(HTTPStatus.NOT_FOUND, "NOT_FOUND", "Endpoint was not found.")
                body = self._read_json_object()
                self._send_json(HTTPStatus.OK, service.calculate(body.get("expression")))

            self._run(action)

        def do_DELETE(self) -> None:
            def action() -> None:
                match = HISTORY_ITEM_PATH.fullmatch(self._path())
                if match is None:
                    if self._path().startswith("/api/history/"):
                        raise ApiError(HTTPStatus.BAD_REQUEST, "INVALID_ID", "History ID must be a positive integer.")
                    raise ApiError(HTTPStatus.NOT_FOUND, "NOT_FOUND", "Endpoint was not found.")
                id_text = match.group(1)
                if len(id_text) > 19:
                    raise ApiError(HTTPStatus.BAD_REQUEST, "INVALID_ID", "History ID is outside the supported range.")
                record_id = int(id_text)
                if record_id > MAX_RECORD_ID:
                    raise ApiError(HTTPStatus.BAD_REQUEST, "INVALID_ID", "History ID is outside the supported range.")
                self._send_json(HTTPStatus.OK, service.delete(record_id))

            self._run(action)

        def do_OPTIONS(self) -> None:
            self.send_response(HTTPStatus.NO_CONTENT)
            self.send_header("Content-Length", "0")
            if (origin := self._cors_origin()) is not None:
                self.send_header("Access-Control-Allow-Origin", origin)
                if origin != "*":
                    self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Max-Age", "600")
            self.end_headers()

    return ExclusiveThreadingHTTPServer((host, port), RequestHandler)
