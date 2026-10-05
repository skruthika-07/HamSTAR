"""One error type and one response envelope for the whole API."""
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .logging import log


class ApiError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        self.code, self.message, self.status = code, message, status


def not_found(what: str) -> ApiError:
    return ApiError(f"{what.upper()}_NOT_FOUND", f"{what.replace('_', ' ').capitalize()} not found.", 404)


def ok(data: Any = None) -> dict:
    return {"success": True, "data": data}


def _fail(code: str, message: str, status: int) -> JSONResponse:
    return JSONResponse({"success": False, "error": {"code": code, "message": message}}, status_code=status)


def install(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api(_: Request, e: ApiError):
        return _fail(e.code, e.message, e.status)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, e: RequestValidationError):
        first = e.errors()[0] if e.errors() else {}
        where = ".".join(str(p) for p in first.get("loc", []) if p != "body")
        return _fail("VALIDATION_ERROR", f"{where}: {first.get('msg', 'invalid input')}".strip(": "), 422)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, e: StarletteHTTPException):
        code = {401: "UNAUTHORIZED", 403: "FORBIDDEN", 404: "NOT_FOUND"}.get(e.status_code, "HTTP_ERROR")
        return _fail(code, str(e.detail), e.status_code)

    @app.exception_handler(Exception)
    async def _crash(request: Request, e: Exception):
        log.exception("Unhandled error on %s %s", request.method, request.url.path)
        return _fail("INTERNAL_ERROR", "Something went wrong on our side.", 500)
