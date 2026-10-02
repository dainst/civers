"""Tests for BaseStorageConfig."""

import pytest
from pydantic import ValidationError

from civers_common.configs.models import BaseStorageConfig


class TestBaseStorageConfig:
    """Test BaseStorageConfig base class."""

    def test_defaults(self):
        config = BaseStorageConfig()
        assert config.backend == "local_file"
        assert config.enabled is None
        assert config.backends == {"local_file": {"base_path": "archives"}}

    def test_get_enabled_backends_with_enabled_list(self):
        config = BaseStorageConfig(
            enabled=["local_file", "s3"],
            backends={
                "local_file": {"base_path": "archives"},
                "s3": {"bucket": "test"},
            },
        )
        assert config.get_enabled_backends() == ["local_file", "s3"]

    def test_get_enabled_backends_falls_back_to_backend(self):
        config = BaseStorageConfig()
        assert config.get_enabled_backends() == ["local_file"]

    def test_empty_enabled_list_rejected(self):
        with pytest.raises(ValidationError, match="cannot be empty"):
            BaseStorageConfig(enabled=[])

    def test_enabled_backend_without_config_rejected(self):
        with pytest.raises(ValidationError, match="not configured"):
            BaseStorageConfig(enabled=["nonexistent"])

    def test_get_backend_config(self):
        config = BaseStorageConfig()
        assert config.get_backend_config("local_file") == {"base_path": "archives"}

    def test_get_backend_config_nonexistent(self):
        config = BaseStorageConfig()
        assert config.get_backend_config("nonexistent") == {}

    def test_get_backend_config_default_first_enabled(self):
        config = BaseStorageConfig(
            enabled=["s3", "local_file"],
            backends={
                "s3": {"bucket": "test"},
                "local_file": {"base_path": "archives"},
            },
        )
        assert config.get_backend_config() == {"bucket": "test"}

    def test_extra_fields_ignored(self):
        config = BaseStorageConfig(unknown="ignored")
        assert not hasattr(config, "unknown")

    def test_valid_multi_backend(self):
        config = BaseStorageConfig(
            enabled=["local_file", "s3"],
            backends={
                "local_file": {"base_path": "archives"},
                "s3": {"bucket": "my-bucket"},
            },
        )
        assert config.get_enabled_backends() == ["local_file", "s3"]
        assert config.get_backend_config("s3") == {"bucket": "my-bucket"}
