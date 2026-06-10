"""Centralized logging configuration for CiVers ChangeDetection."""
##todo: To be moved to civers_common
import logging
import os
import sys


def setup_logging(
    level: int = logging.INFO,
    log_file: str | None = None,
    suppress_kafka_logs: bool = True,
) -> None:
    """Configure logging for the ChangeDetection system."""
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_file:
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers,
        force=True,
    )

    if suppress_kafka_logs:
        kafka_log_level = os.getenv("KAFKA_LOG_LEVEL", "WARNING").upper()
        kafka_level = getattr(logging, kafka_log_level, logging.WARNING)
        for logger_name in [
            "kafka", "aiokafka", "aiokafka.conn", "aiokafka.consumer",
            "aiokafka.consumer.fetcher", "aiokafka.consumer.group_coordinator",
            "aiokafka.producer", "aiokafka.cluster",
            "kafka.client", "kafka.producer", "kafka.consumer",
        ]:
            logging.getLogger(logger_name).setLevel(kafka_level)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("requests").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger."""
    return logging.getLogger(name)
