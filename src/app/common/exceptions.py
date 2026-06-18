class AppError(Exception):
    """Base class for expected application errors mapped to HTTP responses."""

    status_code: int = 500
    message: str = "Internal server error"

    def __init__(self, message: str | None = None) -> None:
        if message is not None:
            self.message = message
        super().__init__(self.message)


class NotFoundError(AppError):
    status_code = 404
    message = "Resource not found"


class ConflictError(AppError):
    status_code = 409
    message = "Conflict"


class UnsupportedMediaTypeError(AppError):
    status_code = 415
    message = "Unsupported media type"


class UploadTooLargeError(AppError):
    status_code = 413
    message = "Upload exceeds maximum allowed size"
