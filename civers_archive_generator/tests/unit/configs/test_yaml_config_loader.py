# tests/unit/configs/test_yaml_config_loader.py
"""
Tests for YamlFileConfigLoader.

These tests verify that YamlFileConfigLoader properly:
1. Loads configuration from hierarchical YAML files
2. Detects environment correctly
3. Merges default and environment configs
4. Validates configuration against Pydantic models
"""
import os
import pytest
from configs.loaders import YamlFileConfigLoader


# =============================================================================
# Environment Detection Tests
# =============================================================================

@pytest.mark.unit
def test_environment_detection_default():
    """Test that default environment is 'testing' when running under pytest."""
    # Ensure CONFIG_ENVIRONMENT is not set to test default
    if "CONFIG_ENVIRONMENT" in os.environ:
        os.environ.pop("CONFIG_ENVIRONMENT")
    loader = YamlFileConfigLoader()
    # When running under pytest, should detect 'testing' environment
    assert loader.environment == "testing"


@pytest.mark.unit
def test_environment_detection_from_env_var(monkeypatch):
    """Test that CONFIG_ENVIRONMENT environment variable overrides detection."""
    monkeypatch.setenv("CONFIG_ENVIRONMENT", "production")
    loader = YamlFileConfigLoader()
    assert loader.environment == "production"


@pytest.mark.unit
def test_config_dir_path():
    """Test that config_dir points to the correct location."""
    loader = YamlFileConfigLoader()
    assert loader.config_dir.exists()
    assert (loader.config_dir / "defaults").exists()
    assert (loader.config_dir / "environments").exists()


# =============================================================================
# Valid Configuration Loading Tests
# =============================================================================

@pytest.mark.unit
def test_config_loading():
    """Test that configuration loads correctly from hierarchical YAML files."""
    loader = YamlFileConfigLoader()
    config = loader.load()

    # Basic app assertions
    assert config.app.name == "archive_generator"
    assert config.app.version == "1.0.0"
    
    # Test transport configuration
    transport_config = config.app.transport
    assert hasattr(transport_config, "kafka")
    assert transport_config.kafka is not None
    assert hasattr(transport_config.kafka, "topics")
    assert isinstance(transport_config.kafka.topics, dict)
    
    # Test domains exist
    assert config.domains
    assert len(config.domains) > 0
    assert all(hasattr(d, "name") for d in config.domains)


@pytest.mark.unit
def test_load_storage_config():
    """Test that storage configuration is loaded correctly."""
    loader = YamlFileConfigLoader()
    config = loader.load()
    
    storage_config = config.app.get_storage_config()
    assert storage_config is not None
    assert hasattr(storage_config, 'enabled')
    assert len(storage_config.get_enabled_backends()) > 0


@pytest.mark.unit
def test_load_transport_config():
    """Test that transport configuration is loaded correctly."""
    loader = YamlFileConfigLoader()
    config = loader.load()
    
    transport_config = config.app.transport
    assert transport_config.enabled == ["kafka"]
    assert transport_config.kafka is not None



# =============================================================================
# Deep Merge Tests
# =============================================================================

@pytest.mark.unit
def test_deep_merge_basic():
    """Test basic deep merge functionality."""
    loader = YamlFileConfigLoader()
    
    dict1 = {"a": 1, "b": {"c": 2}}
    dict2 = {"b": {"d": 3}, "e": 4}
    
    result = loader._deep_merge(dict1, dict2)
    
    assert result["a"] == 1
    assert result["b"]["c"] == 2
    assert result["b"]["d"] == 3
    assert result["e"] == 4


@pytest.mark.unit
def test_deep_merge_override():
    """Test that later dicts override earlier ones."""
    loader = YamlFileConfigLoader()
    
    dict1 = {"a": 1, "b": 2}
    dict2 = {"b": 3}
    
    result = loader._deep_merge(dict1, dict2)
    
    assert result["a"] == 1
    assert result["b"] == 3


@pytest.mark.unit
def test_deep_merge_domains_override():
    """Test that domains list from override replaces base (simple override, not merge by name)."""
    loader = YamlFileConfigLoader()
    
    dict1 = {
        "domains": [
            {"name": "example.com", "artifacts": ["warc"]},
            {"name": "test.com", "artifacts": ["html"]}
        ]
    }
    dict2 = {
        "domains": [
            {"name": "example.com", "artifacts": ["warc", "html"]},
            {"name": "new.com", "artifacts": ["screenshots"]}
        ]
    }
    
    result = loader._deep_merge(dict1, dict2)
    
    # Override replaces the entire domains list
    assert len(result["domains"]) == 2
    
    # Should have the domains from dict2
    domain_names = [d["name"] for d in result["domains"]]
    assert "example.com" in domain_names
    assert "new.com" in domain_names


# =============================================================================
# Error Handling Tests
# =============================================================================

@pytest.mark.unit
def test_invalid_environment_raises_error(monkeypatch):
    """Test that non-existent environment config file causes error."""
    monkeypatch.setenv("CONFIG_ENVIRONMENT", "nonexistent_environment")
    
    loader = YamlFileConfigLoader()
    
    # Should raise FileNotFoundError because the environment config was explicitly set but file doesn't exist
    with pytest.raises(FileNotFoundError):
        loader.load()
