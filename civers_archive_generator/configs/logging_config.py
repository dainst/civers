"""
Centralized logging configuration for the Archive Generator system.
Provides consistent logging setup with Kafka log suppression.
"""
import logging
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
    
    # Suppress verbose third-party logging
    if suppress_kafka_logs:
        # Kafka-related loggers
        logging.getLogger("kafka").setLevel(logging.WARNING)
        logging.getLogger("kafka.client").setLevel(logging.WARNING) 
        logging.getLogger("kafka.producer").setLevel(logging.WARNING)
        logging.getLogger("kafka.consumer").setLevel(logging.WARNING)
        logging.getLogger("kafka.conn").setLevel(logging.WARNING)
        logging.getLogger("kafka.coordinator").setLevel(logging.WARNING)
        logging.getLogger("kafka.cluster").setLevel(logging.WARNING)
        
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
