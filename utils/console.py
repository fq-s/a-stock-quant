"""Console compatibility helpers."""

import sys


def configure_utf8_console() -> None:
    """Prefer UTF-8 output and replace unsupported redirected characters."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8", errors="replace")
