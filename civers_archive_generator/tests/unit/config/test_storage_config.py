"""
Tests for StorageConfig multi-backend support.

These tests verify that StorageConfig properly supports:
1. Multi-backend mode via 'enabled' list (required)
2. Validation of enabled backends
"""

import pytest
from configs.models import StorageConfig


class TestStorageConfigMultiBackend:
    """Tests for multi-backend StorageConfig support."""

    def test_enabled_list_returns_all_backends(self):
        """When enabled is set, get_enabled_backends returns the list."""
        config = StorageConfig(
            enabled=["local_file", "civers_rest_api"],
            backends={
                "local_file": {"base_path": "archives"},
                "civers_rest_api": {"upload_url": "http://localhost:8000/api/upload"}
            }
        )
        assert config.get_enabled_backends() == ["local_file", "civers_rest_api"]

    def test_enabled_empty_list_raises_error(self):
        """Empty enabled list should raise ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            StorageConfig(enabled=[])

    def test_enabled_unknown_backend_raises_error(self):
        """Enabled backend not in backends dict should raise ValueError."""
        with pytest.raises(ValueError, match="enabled but not configured"):
            StorageConfig(
                enabled=["local_file", "s3"],
                backends={"local_file": {"base_path": "archives"}}
            )

    def test_enabled_required(self):
        """enabled field is required."""
        with pytest.raises(Exception):  # ValidationError
            StorageConfig(backends={"local_file": {"base_path": "/tmp/archives"}})

    def test_get_backend_config_returns_correct_config(self):
        """get_backend_config should return config for specified backend."""
        config = StorageConfig(
            enabled=["local_file", "civers_rest_api"],
            backends={
                "local_file": {"base_path": "archives"},
                "civers_rest_api": {"upload_url": "http://example.com"}
            }
        )
        assert config.get_backend_config("local_file") == {"base_path": "archives"}
        assert config.get_backend_config("civers_rest_api") == {"upload_url": "http://example.com"}

    def test_enabled_with_single_backend(self):
        """enabled list with single backend should work."""
        config = StorageConfig(
            enabled=["local_file"],
            backends={"local_file": {"base_path": "archives"}}
        )
        assert config.get_enabled_backends() == ["local_file"]

    def test_get_backend_config_returns_empty_for_unknown_backend(self):
        """get_backend_config for unknown backend should return empty dict."""
        config = StorageConfig(
            enabled=["local_file"],
            backends={"local_file": {"base_path": "archives"}}
        )
        assert config.get_backend_config("unknown") == {}

    def test_enabled_order_is_preserved(self):
        """The order of enabled backends should be preserved."""
        config = StorageConfig(
            enabled=["civers_rest_api", "local_file"],
            backends={
                "local_file": {"base_path": "archives"},
                "civers_rest_api": {"upload_url": "http://example.com"}
            }
        )
        assert config.get_enabled_backends() == ["civers_rest_api", "local_file"]

    def test_has_enabled_field(self):
        """StorageConfig should have 'enabled' field."""
        config = StorageConfig(
            enabled=["local_file"],
            backends={"local_file": {"base_path": "archives"}}
        )
        assert hasattr(config, 'enabled')
        assert config.enabled == ["local_file"]

    def test_default_backends_used(self):
        """Default backends should be used if not specified."""
        config = StorageConfig(enabled=["local_file"])
        assert config.backends == {"local_file": {"base_path": "archives"}}
