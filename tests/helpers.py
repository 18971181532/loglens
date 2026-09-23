"""Test helpers."""
import os
import tempfile


class TempLogFile:
    """Context manager that writes lines to a temp log file."""

    def __init__(self, lines):
        self.lines = lines
        self.path = None

    def __enter__(self):
        fd, self.path = tempfile.mkstemp(suffix=".log")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("\n".join(self.lines) + "\n")
        return self

    def __exit__(self, *args):
        if self.path and os.path.exists(self.path):
            os.unlink(self.path)
