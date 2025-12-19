"""
Tests for StorageConfig multi-backend updates.

Tests the updated StorageConfig model including multi-backend support,
validation, and backward compatibility with single-backend mode.
"""

import pytest
from pydantic import ValidationError
from configs.config_data_model import StorageConfig


class TestStorageConfigMultiBackend:
    """Test multi-backend configuration mode."""
    
    def test_multi_backend_with_enabled_list(self):
        """Test using enabled list for multiple backends."""
        config = StorageConfig(
            enabled=["local_file", "civers_rest_api"],
            backends={
                "local_file": {"base_path": "output"},
                "civers_rest_api": {"upload_url": "http://api.example.com"}
            }
        )
        
        assert config.enabled == ["local_file", "civers_rest_api"]
        assert config.get_enabled_backends() == ["local_file", "civers_rest_api"]
    
    def test_single_backend_in_enabled_list(self):
        """Test enabled list with single backend."""
        config = StorageConfig(
            enabled=["local_file"],
            backends={"local_file": {"base_path": "output"}}
        )
        
        assert config.get_enabled_backends() == ["local_file"]
    
    def test_enabled_empty_list_raises_error(self):
        """Test that empty enabled list raises validation error."""
        with pytest.raises(ValidationError, match="cannot be empty"):
            StorageConfig(
                enabled=[],
                backends={"local_file": {"base_path": "output"}}
            )
    
    def test_enabled_backend_without_config_raises_error(self):
        """Test that enabled backend without configuration raises error."""
        with pytest.raises(ValidationError, match="has no configuration"):
            StorageConfig(
                enabled=["local_file", "missing_backend"],
                backends={"local_file": {"base_path": "output"}}
            )
    
    def test_multiple_enabled_backends_with_configs(self):
        """Test multiple backends all have proper configurations."""
        config = StorageConfig(
            enabled=["local_file", "civers_rest_api", "s3"],
            backends={
                "local_file": {"base_path": "output"},
                "civers_rest_api": {"upload_url": "http://api.com"},
                "s3": {"bucket": "my-bucket"}
            }
        )
        
        assert len(config.get_enabled_backends()) == 3
        assert "local_file" in config.get_enabled_backends()
        assert "civers_rest_api" in config.get_enabled_backends()
        assert "s3" in config.get_enabled_backends()


class TestStorageConfigBackwardCompatibility:
    """Test backward compatibility with single-backend mode."""
    
    def test_legacy_single_backend_mode(self):
        """Test using legacy 'backend' field."""
        config = StorageConfig(
            backend="local_file",
            backends={"local_file": {"base_path": "archives"}}
        )
        
        # Should work in legacy mode
        assert config.backend == "local_file"
        assert config.enabled is None
        assert config.get_enabled_backends() == ["local_file"]
    
    def test_default_backend_value(self):
        """Test default backend value."""
        config = StorageConfig(
            backends={"local_file": {"base_path": "output"}}
        )
        
        assert config.backend == "local_file"
        assert config.get_enabled_backends() == ["local_file"]
    
    def test_legacy_backend_with_different_value(self):
        """Test changing legacy backend field."""
        config = StorageConfig(
            backend="s3",
            backends={
                "local_file": {"base_path": "output"},
                "s3": {"bucket": "my-bucket"}
            }
        )
        
        assert config.backend == "s3"
        assert config.get_enabled_backends() == ["s3"]
    
    def test_enabled_takes_precedence_over_backend(self):
        """Test that 'enabled' list takes precedence over 'backend' field."""
        config = StorageConfig(
            backend="local_file",  # This should be ignored
            enabled=["civers_rest_api", "s3"],  # This should be used
            backends={
                "local_file": {"base_path": "output"},
                "civers_rest_api": {"upload_url": "http://api.com"},
                "s3": {"bucket": "bucket"}
            }
        )
        
        # enabled should take precedence
        assert config.get_enabled_backends() == ["civers_rest_api", "s3"]
        assert "local_file" not in config.get_enabled_backends()


class TestStorageConfigGetBackendConfig:
    """Test get_backend_config method."""
    
    def test_get_backend_config_legacy_mode(self):
        """Test getting config in legacy single-backend mode."""
        config = StorageConfig(
            backend="local_file",
            backends={"local_file": {"base_path": "archives"}}
        )
        
        backend_config = config.get_backend_config()
        assert backend_config == {"base_path": "archives"}
    
    def test_get_backend_config_multi_backend_default(self):
        """Test getting config in multi-backend mode without specifying backend."""
        config = StorageConfig(
            enabled=["local_file", "civers_rest_api"],
            backends={
                "local_file": {"base_path": "output"},
                "civers_rest_api": {"upload_url": "http://api.com"}
            }
        )
        
        # Should return first enabled backend's config
        backend_config = config.get_backend_config()
        assert backend_config == {"base_path": "output"}
    
    def test_get_backend_config_specific_backend(self):
        """Test getting config for specific backend."""
        config = StorageConfig(
            enabled=["local_file", "civers_rest_api"],
            backends={
                "local_file": {"base_path": "output"},
                "civers_rest_api": {"upload_url": "http://api.com"}
            }
        )
        
        # Get specific backend config
        local_config = config.get_backend_config("local_file")
        api_config = config.get_backend_config("civers_rest_api")
        
        assert local_config == {"base_path": "output"}
        assert api_config == {"upload_url": "http://api.com"}
    
    def test_get_backend_config_nonexistent_backend(self):
        """Test getting config for backend that doesn't exist."""
        config = StorageConfig(
            enabled=["local_file"],
            backends={"local_file": {"base_path": "output"}}
        )
        
        # Should return empty dict for nonexistent backend
        config_result = config.get_backend_config("nonexistent")
        assert config_result == {}


class TestStorageConfigValidation:
    """Test configuration validation."""
    
    def test_validation_all_enabled_backends_must_exist(self):
        """Test that all enabled backends must have configs."""
        with pytest.raises(ValidationError) as exc_info:
            StorageConfig(
                enabled=["local_file", "s3", "azure"],
                backends={
                    "local_file": {"base_path": "output"},
                    "s3": {"bucket": "my-bucket"}
                    # azure is missing!
                }
            )
        
        assert "azure" in str(exc_info.value)
        assert "has no configuration" in str(exc_info.value)
    
    def test_validation_error_lists_available_backends(self):
        """Test that validation error lists available backends."""
        with pytest.raises(ValidationError) as exc_info:
            StorageConfig(
                enabled=["missing"],
                backends={
                    "local_file": {"base_path": "output"},
                    "civers_rest_api": {"upload_url": "http://api.com"}
                }
            )
        
        error_msg = str(exc_info.value)
        assert "Available backends" in error_msg
        assert "local_file" in error_msg
        assert "civers_rest_api" in error_msg
    
    def test_backends_dict_can_have_extra_configs(self):
        """Test that backends dict can contain configs for disabled backends."""
        # This should be valid - having extra backend configs is fine
        config = StorageConfig(
            enabled=["local_file"],
            backends={
                "local_file": {"base_path": "output"},
                "civers_rest_api": {"upload_url": "http://api.com"},  # Not enabled, but config exists
                "s3": {"bucket": "my-bucket"}  # Not enabled, but config exists
            }
        )
        
        assert config.get_enabled_backends() == ["local_file"]
        # Should still be able to get configs for disabled backends
        assert config.get_backend_config("civers_rest_api") == {"upload_url": "http://api.com"}


class TestStorageConfigRealWorldScenarios:
    """Test real-world usage scenarios."""
    
    def test_local_file_only_configuration(self):
        """Test configuration with only local file storage."""
        config = StorageConfig(
            enabled=["local_file"],
            backends={
                "local_file": {
                    "base_path": "output/metadata",
                    "create_subdirectories": True
                }
            }
        )
        
        assert config.get_enabled_backends() == ["local_file"]
        assert config.get_backend_config("local_file")["base_path"] == "output/metadata"
    
    def test_dual_backend_local_and_api(self):
        """Test configuration with local file + CIVERS API."""
        config = StorageConfig(
            enabled=["local_file", "civers_rest_api"],
            backends={
                "local_file": {
                    "base_path": "output/metadata",
                    "create_subdirectories": True
                },
                "civers_rest_api": {
                    "upload_url": "http://localhost:8000/api/upload",
                    "timeout_seconds": 30,
                    "retry_attempts": 3,
                    "verify_ssl": True,
                    "auth": {
                        "enabled": False
                    }
                }
            }
        )
        
        assert len(config.get_enabled_backends()) == 2
        local_cfg = config.get_backend_config("local_file")
        api_cfg = config.get_backend_config("civers_rest_api")
        
        assert local_cfg["create_subdirectories"] is True
        assert api_cfg["timeout_seconds"] == 30
    
    def test_triple_backend_configuration(self):
        """Test configuration with three backends."""
        config = StorageConfig(
            enabled=["local_file", "civers_rest_api", "s3"],
            backends={
                "local_file": {"base_path": "output"},
                "civers_rest_api": {"upload_url": "http://api.com"},
                "s3": {
                    "bucket": "my-archives",
                    "region": "us-east-1"
                }
            }
        )
        
        assert len(config.get_enabled_backends()) == 3
        assert config.get_backend_config("s3")["region"] == "us-east-1"
