"""Catalogue service entry point.

Locally:   uvicorn app.main:app --reload --port 8001
On Lambda: API Gateway invokes `handler`; Mangum translates the API Gateway event into an
           ASGI request for FastAPI and the response back into API Gateway's format.
"""

import logging
import time

from fastapi import FastAPI, Request, Response
from mangum import Mangum

from app.correlation import HEADER, resolve_correlation_id, set_correlation_id
from app.errors import error_response, register_error_handlers
from app.logging_config import configure_logging

SERVICE_NAME = "catalogue"
logger = logging.getLogger(SERVICE_NAME)


def create_app() -> FastAPI:
    app = FastAPI(title="Tessera Catalogue API", version="0.1.0")
    register_error_handlers(app)

    @app.middleware("http")
    async def correlation_and_access_log(request: Request, call_next) -> Response:
        correlation_id = resolve_correlation_id(request.headers.get(HEADER))
        set_correlation_id(correlation_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            # Last line of defence: log the stack trace, but never send it to the client.
            logger.exception("Unhandled error")
            response = error_response(500, "INTERNAL_ERROR", "Internal server error")
        response.headers[HEADER] = correlation_id
        logger.info(
            "request",
            extra={
                "method": request.method,
                "path": request.url.path,  # path only: query strings may carry user input
                "status": response.status_code,
                "durationMs": round((time.perf_counter() - started) * 1000, 1),
            },
        )
        return response

    @app.get("/v1/health", tags=["ops"])
    def health() -> dict[str, str]:
        """Liveness check: the function is up and can serve requests."""
        return {"status": "ok", "service": SERVICE_NAME}

    return app


configure_logging(SERVICE_NAME)
app = create_app()
handler = Mangum(app, lifespan="off")
