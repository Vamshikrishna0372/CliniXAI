"""Centralized Logging Configuration for CliniXAI backend."""

import logging
import sys
from app.core.config import settings


def setup_logging() -> logging.Logger:
    """Configures the root logger according to settings.LOG_LEVEL."""
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    log_format = (
        "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s"
    )

    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
        force=True,
    )

    logger = logging.getLogger("clinixai")
    logger.setLevel(log_level)

    # Suppress verbose noisy third-party loggers if necessary
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    return logger


logger = setup_logging()
