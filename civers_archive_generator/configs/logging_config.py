"""Logging setup for the Archive Generator, with Kafka log suppression."""

import logging
import os
import sys
from typing import Optional

_VALID_LEVELS = ("CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG")


def resolve_log_level(name: Optional[str], default: int = logging.INFO) -> int:
    """Return the named logging level; warn and use default for an unknown name."""
    if not name:
        return default
    level = getattr(logging, name.strip().upper(), None)
    if isinstance(level, int):
        return level
    print(
        f"⚠️ Warning: unknown LOG_LEVEL '{name}'; using "
        f"{logging.getLevelName(default)}. Valid: {', '.join(_VALID_LEVELS)}",
        file=sys.stderr,
    )
    return default


def setup_logging(
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    suppress_kafka_logs: bool = True
) -> None:
    """Replace logging handlers with stdout and an optional log file.

    Keep stdout logging if the file cannot be opened. File logs are not rotated here.
    """
    handlers = [logging.StreamHandler(sys.stdout)]
    
    if log_file:
        try:
            handlers.append(logging.FileHandler(log_file))
        except (PermissionError, OSError) as e:
            print(f"⚠️ Warning: Cannot create log file '{log_file}': {e}")
            print("   Falling back to console-only logging.")
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers,
        force=True  # Override any existing configuration
    )
    
    # Apply KAFKA_LOG_LEVEL to Kafka clients.
    if suppress_kafka_logs:
        kafka_log_level = os.getenv("KAFKA_LOG_LEVEL", "WARNING").upper()
        kafka_level = getattr(logging, kafka_log_level, logging.WARNING)
        
        logging.getLogger("kafka").setLevel(kafka_level)
        logging.getLogger("aiokafka").setLevel(kafka_level)
        logging.getLogger("aiokafka.conn").setLevel(kafka_level)
        logging.getLogger("aiokafka.consumer").setLevel(kafka_level)
        logging.getLogger("aiokafka.consumer.fetcher").setLevel(kafka_level)
        logging.getLogger("aiokafka.consumer.group_coordinator").setLevel(kafka_level)
        logging.getLogger("aiokafka.producer").setLevel(kafka_level)
        logging.getLogger("aiokafka.cluster").setLevel(kafka_level)
        logging.getLogger("kafka.client").setLevel(kafka_level) 
        logging.getLogger("kafka.producer").setLevel(kafka_level)
        logging.getLogger("kafka.consumer").setLevel(kafka_level)
        logging.getLogger("kafka.conn").setLevel(kafka_level)
        logging.getLogger("kafka.coordinator").setLevel(kafka_level)
        logging.getLogger("kafka.cluster").setLevel(kafka_level)
        
        # Other potentially verbose loggers
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("requests").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a logger under the given name, typically ``__name__``."""
    return logging.getLogger(name)
