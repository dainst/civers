"""Logging configuration for CiVers Orchestrator."""

import logging
import os
import sys


def setup_logging(
    level: str = "INFO",
    format_string: str | None = None,
) -> None:
    """
    Configure structured logging for the application.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_string: Custom format string. If None, uses default structured format.
    """
    if format_string is None:
        format_string = (
            "%(asctime)s - %(name)s - %(levelname)s - "
            "%(filename)s:%(lineno)d - %(funcName)s() - %(message)s"
        )

    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format=format_string,
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )

    # Set third-party library log levels (controllable via env)
    kafka_log_level = os.getenv("KAFKA_LOG_LEVEL", "WARNING").upper()
    kafka_level = getattr(logging, kafka_log_level, logging.WARNING)
    logging.getLogger("kafka").setLevel(kafka_level)
    logging.getLogger("aiokafka").setLevel(kafka_level)
    logging.getLogger("kafka.conn").setLevel(logging.ERROR)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the specified name.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)
