"""Centralized logging configuration for NFMD ETL pipeline."""

import logging
import sys


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Get a configured logger for ETL modules.

    Args:
        name: Logger name (typically __name__ of the calling module).
        level: Logging level. Defaults to INFO.

    Returns:
        Configured Logger instance with stderr handler.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(
            logging.Formatter("%(levelname)s [%(name)s] %(message)s")
        )
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger
