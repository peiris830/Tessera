"""Catalogue service entry point.

Locally:   uvicorn app.main:app --reload --port 8001 --app-dir src
On Lambda: API Gateway invokes `handler`; Mangum translates the API Gateway event into an
           ASGI request for FastAPI and the response back into API Gateway's format.
"""

import logging
import os
import time
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.openapi.utils import get_openapi
from mangum import Mangum

from app.correlation import HEADER, resolve_correlation_id, set_correlation_id
from app.errors import error_response, register_error_handlers
from app.events import router as events_router
from app.logging_config import configure_logging
from app.organisers import router as organisers_router

SERVICE_NAME = "catalogue"
PUBLIC_PATHS = {"/v1/health"}  # everything else requires a Cognito JWT
logger = logging.getLogger(SERVICE_NAME)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Tessera Catalogue API",
        version="0.1.0",
        description="Events: browse (signed-in users) and manage (organisers).",
    )
    register_error_handlers(app)
    _document_jwt_security(app)

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

    app.include_router(events_router)
    app.include_router(organisers_router)
    return app


def _document_jwt_security(app: FastAPI) -> None:
    """Mark protected operations in the OpenAPI spec as requiring a bearer JWT.

    Identity is read from API Gateway's verified claims (app/auth.py), not from a FastAPI
    security class, so FastAPI can't infer this on its own.
    """

    def openapi() -> dict[str, Any]:
        if app.openapi_schema is None:
            schema = get_openapi(
                title=app.title,
                version=app.version,
                description=app.description,
                routes=app.routes,
            )
            schema.setdefault("components", {})["securitySchemes"] = {
                "cognitoJwt": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT",
                    "description": "Cognito token; verified by API Gateway's JWT authorizer.",
                }
            }
            for path, operations in schema["paths"].items():
                if path not in PUBLIC_PATHS:
                    for operation in operations.values():
                        operation["security"] = [{"cognitoJwt": []}]
            app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = openapi  # type: ignore[method-assign]


configure_logging(SERVICE_NAME, os.environ.get("LOG_LEVEL", "INFO"))
app = create_app()
handler = Mangum(app, lifespan="off")
