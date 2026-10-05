"""Check optional storage and startup handling of unsupported backends."""
import logging

import pytest

from configs.models import StorageConfig
from storage_layer import StorageManager

pytestmark = [pytest.mark.unit]

REST = {"upload_url": "http://localhost:8000/api/upload"}


def _warnings(caplog):
    return [r for r in caplog.records if r.levelno >= logging.WARNING]


def test_no_enabled_backends_initializes_cleanly(caplog):
    """No storage configured is a supported mode, not a warning."""
    with caplog.at_level(logging.DEBUG):
        manager = StorageManager(StorageConfig())

    assert manager.get_enabled_backends() == []
    assert _warnings(caplog) == []


def test_backend_this_service_does_not_implement_is_skipped(caplog):
    """local_file lives in the shared config for the metadata extractor's sake."""
    config = StorageConfig(
        enabled=["local_file", "civers_rest_api"],
        backends={"local_file": {"base_path": "archives"}, "civers_rest_api": REST},
    )

    with caplog.at_level(logging.DEBUG):
        manager = StorageManager(config)

    assert manager.get_enabled_backends() == ["civers_rest_api"]
    assert _warnings(caplog) == []


def test_backend_without_configuration_is_skipped_with_a_warning(caplog):
    """A typo'd or unconfigured backend is survivable, but must not pass silently."""
    config = StorageConfig(enabled=["civers_rest_api"], backends={})

    with caplog.at_level(logging.DEBUG):
        manager = StorageManager(config)

    assert manager.get_enabled_backends() == []
    assert _warnings(caplog) != []
