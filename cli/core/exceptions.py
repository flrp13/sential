import os
from typing import Optional


class TempFileError(Exception):
    """Raised when there an error interacting with temp files"""

    def __init__(
        self,
        message: Optional[str] = None,
        original_exception: Optional[Exception] = None,
    ):
        self.message = message or "An error occurred with a temporary file"
        super().__init__(self.message)
        self.original_exception = original_exception
        self.diagnostic_info = {
            "type": (
                type(original_exception).__name__ if original_exception else "Unknown"
            ),
            "details": str(original_exception) if original_exception else "No details",
            "os_name": os.name,
        }


class TempFileCreationError(TempFileError):
    """Raised when a temp file can't be created"""

    def __init__(
        self,
        message: Optional[str] = None,
        original_exception: Optional[Exception] = None,
    ):
        super().__init__(
            message="Failed to create temporary file",
            original_exception=original_exception,
        )


class TempFileWriteError(TempFileError):
    """Raised when a temp file can't be written to"""

    def __init__(
        self,
        message: Optional[str] = None,
        original_exception: Optional[Exception] = None,
    ):
        super().__init__(
            message="Failed to write to temporary file",
            original_exception=original_exception,
        )


class EmptyInventoryError(Exception):
    """Raised when no files are found matching the specified criteria"""

    def __init__(self, message: Optional[str] = None):
        self.message = (
            message or "No files found matching the specified language and scopes"
        )
        super().__init__(self.message)
