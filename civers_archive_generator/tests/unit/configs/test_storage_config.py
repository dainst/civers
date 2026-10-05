"""Check optional publication settings; capture files are already saved locally."""

import pytest
from configs.models import StorageConfig

pytestmark = [pytest.mark.unit]

REST = {"upload_url": "http://localhost:8000/api/upload"}


class TestStorageConfigMultiBackend:
    """Tests for multi-backend StorageConfig support."""

    def test_enabled_list_returns_all_backends(self):
        """When enabled is set, get_enabled_backends returns the list."""
        config = StorageConfig(
            enabled=["civers_rest_api"],
            backends={"civers_rest_api": REST},
        )
        assert config.get_enabled_backends() == ["civers_rest_api"]

    def test_enabled_empty_list_is_allowed(self):
        """Storage is optional — an empty list disables it."""
        assert StorageConfig(enabled=[]).get_enabled_backends() == []

    def test_enabled_absent_is_allowed(self):
        """Omitting enabled backends disables publication."""
        assert StorageConfig().get_enabled_backends() == []

    def test_enabled_null_is_allowed(self):
        """A YAML key left blank parses as None and must disable storage too."""
        assert StorageConfig(enabled=None).get_enabled_backends() == []

    def test_unconfigured_backend_is_not_rejected(self):
        """A backend without a config block is skipped at init, not a config error."""
        config = StorageConfig(
            enabled=["civers_rest_api", "s3"],
            backends={"civers_rest_api": REST},
        )
        assert config.get_enabled_backends() == ["civers_rest_api", "s3"]

    def test_enabled_order_is_preserved(self):
        """The order of enabled backends should be preserved."""
        config = StorageConfig(
            enabled=["civers_rest_api", "other"],
            backends={"civers_rest_api": REST, "other": {}},
        )
        assert config.get_enabled_backends() == ["civers_rest_api", "other"]

    def test_backends_default_to_empty(self):
        """No publication backend is enabled by default."""
        assert StorageConfig().backends == {}
