class ApplicationError(Exception):
    """Base exception for expected application-level errors."""

    def __init__(
        self,
        message: str,
        code: str = "APPLICATION_ERROR",
    ):
        self.message = message
        self.code = code
        super().__init__(message)