from app.common.exceptions import AppError


class InvalidTrimError(AppError):
    """Raised when clip trim points are logically invalid."""

    status_code = 422
    message = "Invalid trim points"
