"""JSON formatter for structured logging with correlation ID."""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict
from asgi_correlation_id.context import correlation_id


class JSONFormatter(logging.Formatter):
    """
    JSON formatter that includes correlation ID from asgi-correlation-id.

    Automatically filters sensitive data and includes correlation ID in all log entries.
    """

    # Sensitive field patterns for data filtering
    SENSITIVE_FIELDS = {
        'password', 'token', 'secret', 'key', 'authorization',
        'cookie', 'session', 'csrf', 'api_key', 'private'
    }

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON with correlation ID."""

        # Base log entry
        log_entry = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'correlation_id': correlation_id.get('not_set_yet'),
        }

        # Add extra fields from record
        if hasattr(record, 'extra') and isinstance(record.extra, dict):
            # Filter sensitive data
            filtered_extra = self._filter_sensitive_data(record.extra)
            log_entry.update(filtered_extra)

        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)

        # Add file and line info for debug level
        if record.levelno <= logging.DEBUG:
            log_entry['file'] = record.filename
            log_entry['line'] = record.lineno
            log_entry['function'] = record.funcName

        return json.dumps(log_entry, ensure_ascii=False)

    def _filter_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively filter sensitive data from log entry.

        Args:
            data: Dictionary potentially containing sensitive information

        Returns:
            Dictionary with sensitive values replaced by '[FILTERED]'
        """
        if not isinstance(data, dict):
            return data

        filtered = {}
        for key, value in data.items():
            key_lower = key.lower()

            # Check if key contains sensitive terms
            if any(sensitive in key_lower for sensitive in self.SENSITIVE_FIELDS):
                filtered[key] = '[FILTERED]'
            elif isinstance(value, dict):
                filtered[key] = self._filter_sensitive_data(value)
            elif isinstance(value, list):
                filtered[key] = [
                    self._filter_sensitive_data(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                filtered[key] = value

        return filtered