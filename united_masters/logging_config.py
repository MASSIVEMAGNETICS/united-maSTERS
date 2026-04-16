"""
logging_config.py — Centralized logging configuration for united-masters.

Call :func:`configure_logging` once at application startup (CLI entry point,
WSGI startup, etc.) to set a consistent log format across all modules.

Usage::

    from united_masters.logging_config import configure_logging
    configure_logging(level="INFO")
"""

from __future__ import annotations

import logging
import os
import sys


def configure_logging(level: str | None = None) -> None:
    """Configure the root logger with a structured, human-readable format.

    Parameters
    ----------
    level:
        Log level string (``"DEBUG"``, ``"INFO"``, ``"WARNING"``, …).
        When *None*, reads the ``UM_LOG_LEVEL`` environment variable,
        defaulting to ``"WARNING"`` if not set.
    """
    if level is None:
        level = os.environ.get("UM_LOG_LEVEL", "WARNING").upper()

    numeric_level = getattr(logging, level, logging.WARNING)

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )

    root = logging.getLogger()
    root.setLevel(numeric_level)
    # Replace any existing handlers to avoid duplicate log lines.
    root.handlers.clear()
    root.addHandler(handler)

    logging.getLogger("united_masters").setLevel(numeric_level)
    logging.getLogger("vos_core").setLevel(numeric_level)
