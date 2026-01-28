"""Logging configuration using asgi-correlation-id pattern."""

import logging
from logging.config import dictConfig
from typing import Optional
from asgi_correlation_id import CorrelationIdFilter


def configure_logging(level: str = "INFO", json_format: bool = True, log_file: Optional[str] = None) -> None:
    """
    Configure application logging using asgi-correlation-id pattern.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        json_format: Use JSON formatter for structured logging
        log_file: Optional file path for file logging
    """

    config = {
        'version': 1,
        'disable_existing_loggers': False,
        'filters': {
            'correlation_id': {'()': CorrelationIdFilter},
        },
        'formatters': {
            'json': {'()': 'app.logging.formatters.JSONFormatter'},
            'console': {
                'format': '%(levelname)s: %(name)s [%(correlation_id)s] %(message)s',
                'datefmt': '%H:%M:%S',
            },
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'filters': ['correlation_id'],
                'formatter': 'json' if json_format else 'console',
            },
        },
        'root': {
            'handlers': ['console'],
            'level': level.upper()
        },
        'loggers': {
            # Application loggers
            'app': {'level': level.upper()},
            # Third-party loggers
            'uvicorn': {'level': 'INFO'},
            'uvicorn.access': {'level': 'INFO'},
            'httpx': {'level': 'INFO'},
            'asgi_correlation_id': {'level': 'WARNING'},
            'kafka': {'level': 'WARNING'},
            'aiokafka': {'level': 'WARNING'},
        }
    }

    # Add file handler if specified
    if log_file:
        try:
            config['handlers']['file'] = {
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': log_file,
                'maxBytes': 10*1024*1024,  # 10MB
                'backupCount': 5,
                'filters': ['correlation_id'],
                'formatter': 'json' if json_format else 'console',
            }
            config['root']['handlers'].append('file')
        except Exception as e:
            # Fall back to console logging if file logging fails
            logging.warning(f"Failed to set up file logging: {e}")

    dictConfig(config)