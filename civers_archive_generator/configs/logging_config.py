"""
Centralized logging configuration for the Archive Generator system.
Provides consistent logging setup with Kafka log suppression.
"""
import logging
import os
import sys
from typing import Optional


def setup_logging(
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    suppress_kafka_logs: bool = True
) -> None:
    """
    Configure logging for the Archive Generator system.
    
    Args:
        level: Logging level (default: INFO)
        log_file: Optional file to write logs to
        suppress_kafka_logs: Whether to suppress verbose Kafka logs (default: True)
    """
    # Setup basic logging configuration
    handlers = [logging.StreamHandler(sys.stdout)]
    
    if log_file:
        try:
            handlers.append(logging.FileHandler(log_file))
        except (PermissionError, OSError) as e:
            # Fall back to console-only logging in Docker or when file access fails
            print(f"⚠️ Warning: Cannot create log file '{log_file}': {e}")
            print("   Falling back to console-only logging.")
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers,
        force=True  # Override any existing configuration
    )
    
    # Suppress verbose third-party logging (level controllable via env)
    if suppress_kafka_logs:
        kafka_log_level = os.getenv("KAFKA_LOG_LEVEL", "WARNING").upper()
        kafka_level = getattr(logging, kafka_log_level, logging.WARNING)
        
        # Kafka-related loggers - suppress all verbose logging
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
    """
    Get a logger with the specified name.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)
