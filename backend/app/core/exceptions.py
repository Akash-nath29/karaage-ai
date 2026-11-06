from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """An error with a user-facing message and HTTP status. Safe to raise from services and workers."""

    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status


class NotFoundError(AppError):
    def __init__(self, resource: str) -> None:
        super().__init__(404, f"{resource} not found")


async def app_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    return JSONResponse(status_code=exc.status, content={"detail": str(exc)})
