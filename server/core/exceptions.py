from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DataError


class AppError(Exception):
    """A rule or access failure. Rendered as {"detail": {"code", "message"}}."""

    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(DataError)
    async def _data_error(_: Request, __: DataError) -> JSONResponse:
        # The database refused the values themselves, most often text holding a NUL character (Postgres cannot store
        # one). That is bad input, not a server fault, and nothing was written. One place covers every text field.
        return JSONResponse(
            status_code=422,
            content={"detail": {"code": "invalid_input", "message": "Part of what you sent cannot be stored. Remove any unusual control characters and try again."}},
        )
