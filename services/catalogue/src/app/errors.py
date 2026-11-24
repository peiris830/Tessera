"""Consistent error responses.

Every error leaves the service as:
    {"error": {"code": "NOT_FOUND", "message": "...", "correlationId": "..."}}
"""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.correlation import get_correlation_id

# --- Schema of the error body, used to document error responses in the OpenAPI spec ---


class ErrorDetail(BaseModel):
    code: str = Field(examples=["EVENT_NOT_FOUND"])
    message: str = Field(examples=["Event not found"])
    correlationId: str = Field(examples=["2f7fe8ec-c0af-4b49-bcf5-54a4bd6250e3"])


class ErrorResponse(BaseModel):
    error: ErrorDetail


_DESCRIPTIONS = {
    400: "Bad request (e.g. invalid nextToken)",
    401: "No valid identity",
    403: "Signed in, but not allowed (wrong role or not the owner)",
    404: "Not found (or not visible to this caller)",
    409: "Conflict with the resource's current state",
    422: "Request failed validation",
}


def error_responses(*status_codes: int) -> dict[int | str, dict[str, Any]]:
    """`responses=` value for a route, documenting its errors with the real error body."""
    return {
        code: {"model": ErrorResponse, "description": _DESCRIPTIONS[code]} for code in status_codes
    }


_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    429: "TOO_MANY_REQUESTS",
    500: "INTERNAL_ERROR",
    503: "SERVICE_UNAVAILABLE",
}


class APIError(Exception):
    """Raise from route code for an expected failure, e.g. APIError(404, "EVENT_NOT_FOUND", ...)."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def error_response(
    status_code: int, code: str, message: str, headers: dict[str, str] | None = None
) -> JSONResponse:
    body = {"error": {"code": code, "message": message, "correlationId": get_correlation_id()}}
    return JSONResponse(status_code=status_code, content=body, headers=headers)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(APIError)
    async def _api_error(_: Request, exc: APIError) -> JSONResponse:
        return error_response(exc.status_code, exc.code, exc.message)

    # Covers FastAPI's HTTPException and Starlette's own 404/405 for unknown routes.
    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _CODES.get(exc.status_code, "HTTP_ERROR")
        return error_response(exc.status_code, code, str(exc.detail), exc.headers)

    # Pydantic validation failures. Report the first problem without echoing input values.
    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = exc.errors()
        first = errors[0] if errors else {}
        location = ".".join(str(part) for part in first.get("loc", ()))
        reason = first.get("msg", "Invalid request")
        message = f"{location}: {reason}" if location else reason
        return error_response(422, "VALIDATION_ERROR", message)
