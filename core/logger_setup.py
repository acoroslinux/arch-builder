# -*- coding: utf-8 -*-
"""
Core logger configuration for the arch‑builder project.

This module centralises all logging initialisation, providing:
* colour‑coded console output,
* rotating file logs stored in ~/logs/,
* a simple API to obtain a logger for any component.
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

# ----------------------------------------------------------------------
# Colour definitions (used only when the terminal supports colour)
# ----------------------------------------------------------------------
COLOR_DEBUG = "\033[94m"  # Blue
COLOR_INFO = "\033[92m"  # Green
COLOR_WARNING = "\033[93m"  # Yellow
COLOR_ERROR = "\033[91m"  # Red
COLOR_CRITICAL = "\033[95m"  # Magenta
COLOR_RESET = "\033[0m"


def supports_color() -> bool:
    """Return True if the current stdout supports colour sequences."""
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


class ColorFormatter(logging.Formatter):
    """Formatter that injects colour codes based on the log level."""

    level_colors = {
        logging.DEBUG: COLOR_DEBUG,
        logging.INFO: COLOR_INFO,
        logging.WARNING: COLOR_WARNING,
        logging.ERROR: COLOR_ERROR,
        logging.CRITICAL: COLOR_CRITICAL,
    }

    def __init__(self, fmt=None, datefmt=None, style="%"):
        super().__init__(fmt=fmt, datefmt=datefmt, style=style)

    def format(self, record):
        message = super().format(record)
        if supports_color():
            colour = self.level_colors.get(record.levelno, COLOR_RESET)
            message = f"{colour}{message}{COLOR_RESET}"
        return message


def setup_logger(
    component_name: str,
    log_filename: str = "builder.log",
    log_level: int = logging.DEBUG,
) -> logging.Logger:
    """
    Create (or retrieve) a logger for a given component.

    The logger writes to:
    • the console (colourised, INFO+ by default)
    • a rotating file in ``~/logs/`` (DEBUG+ by default)

    Parameters
    ----------
    component_name : str
        Unique identifier for the component (e.g. ``'iso_engine'``).
    log_filename : str, optional
        Name of the log file. Defaults to ``builder.log``.
    log_level : int, optional
        Minimum severity to capture. Defaults to ``logging.DEBUG``.

    Returns
    -------
    logging.Logger
        A ready‑to‑use logger instance.
    """
    logger = logging.getLogger(component_name)
    logger.setLevel(log_level)
    logger.propagate = False

    # Prevent duplicate handlers when ``setup_logger`` is called more than once
    if logger.handlers:
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
            handler.close()

    # ------------------------------------------------------------------
    # Console handler (colourised)
    # ------------------------------------------------------------------
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(
        ColorFormatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )

    # ------------------------------------------------------------------
    # File handler (rotating, no colours)
    # ------------------------------------------------------------------
    log_dir = Path(os.path.expanduser("~")) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    file_handler = RotatingFileHandler(
        log_dir / log_filename,
        maxBytes=1024 * 1024,  # 1 MiB per file
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )

    # ------------------------------------------------------------------
    # Attach handlers
    # ------------------------------------------------------------------
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


def get_global_logger() -> logging.Logger:
    """A convenience logger for ad‑hoc, project‑wide messages."""
    return setup_logger("arch-builder-global", "global.log", logging.INFO)
