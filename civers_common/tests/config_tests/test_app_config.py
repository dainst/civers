"""Tests for BaseAppConfig."""


from civers_common.configs.models import BaseAppConfig


class TestBaseAppConfig:
    """Test BaseAppConfig base class."""

    def test_defaults(self):
        config = BaseAppConfig()
        assert config.name == "civers_service"
        assert config.version == "1.0.0"
        assert config.environment == "development"

    def test_app_transport_key_is_ignored(self):
        """Transport lives at the root only; an app-level block (legacy YAML) is dropped."""
        config = BaseAppConfig(transport={"enabled": ["kafka"]})
        assert not hasattr(config, "transport")

    def test_extra_fields_ignored(self):
        config = BaseAppConfig(unknown="ignored")
        assert not hasattr(config, "unknown")

    def test_subclass_can_override_defaults(self):
        """Services override name, version defaults."""

        class CDAppConfig(BaseAppConfig):
            name: str = "change_detection_system"
            version: str = "0.1.0"

        config = CDAppConfig()
        assert config.name == "change_detection_system"
        assert config.version == "0.1.0"
        assert config.environment == "development"

    def test_subclass_can_add_fields(self):
        """Services add their own fields."""

        class AGAppConfig(BaseAppConfig):
            archive_directory: str = "archives"

        config = AGAppConfig()
        assert config.archive_directory == "archives"
        assert config.name == "civers_service"
