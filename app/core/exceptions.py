"""Application errors and the single place that turns them into HTTP responses.

Services raise these instead of FastAPI's HTTPException, so business code never depends on the
web framework. Every error is rendered the same way:

    {"detail": "Product not found", "code": "not_found"}

`detail` is for people; `code` is a stable identifier clients can branch on.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    status_code = 400
    code = "error"

    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class InvalidRequestError(AppError):
    status_code = 422
    code = "invalid_request"


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"


class PayloadTooLargeError(AppError):
    status_code = 413
    code = "payload_too_large"


class UnsupportedMediaError(AppError):
    status_code = 415
    code = "unsupported_media_type"


async def _handle_app_error(request: Request, error: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code, content={"detail": error.detail, "code": error.code}
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _handle_app_error)
