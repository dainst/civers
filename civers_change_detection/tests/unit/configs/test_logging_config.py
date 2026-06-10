"""Tests for the logging configuration module."""

import logging

import pytest

from configs.logging_config import get_logger, setup_logging


class TestSetupLogging:
    def test_setup_logging_sets_root_level(self):
        setup_logging(level=logging.DEBUG)
        assert logging.getLogger().level == logging.DEBUG

    def test_setup_logging_default_level_is_info(self):
        setup_logging()
        assert logging.getLogger().level == logging.INFO

    def test_setup_logging_suppresses_kafka_logs(self):
        setup_logging(suppress_kafka_logs=True)
        kafka_logger = logging.getLogger("aiokafka")
        assert kafka_logger.level >= logging.WARNING

    def test_setup_logging_suppresses_urllib3_logs(self):
        setup_logging(suppress_kafka_logs=True)
        urllib3_logger = logging.getLogger("urllib3")
        assert urllib3_logger.level >= logging.WARNING

    def test_setup_logging_does_not_suppress_kafka_when_disabled(self):
        # Reset any previously set level on aiokafka
        logging.getLogger("aiokafka").setLevel(logging.NOTSET)
        setup_logging(level=logging.DEBUG, suppress_kafka_logs=False)
        # When suppression is disabled, aiokafka should NOT have been
        # explicitly set to WARNING — it inherits root level
        kafka_logger = logging.getLogger("aiokafka")
        assert kafka_logger.level != logging.WARNING

    def test_setup_logging_with_file(self, tmp_path):
        log_file = str(tmp_path / "test.log")
        setup_logging(log_file=log_file)
        logger = get_logger("test_file_logging")
        logger.info("test message")
        assert (tmp_path / "test.log").exists()
        content = (tmp_path / "test.log").read_text()
        assert "test message" in content


class TestGetLogger:
    def test_get_logger_returns_named_logger(self):
        logger = get_logger("my_component")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "my_component"

    def test_get_logger_different_names_different_loggers(self):
        a = get_logger("component_a")
        b = get_logger("component_b")
        assert a is not b
        assert a.name != b.name

    def test_get_logger_same_name_same_logger(self):
        a = get_logger("shared_name")
        b = get_logger("shared_name")
        assert a is b
