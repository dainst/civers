"""Tests for civers_common.configs.exceptions."""

from civers_common.configs.exceptions import ConfigurationError


class TestConfigurationError:
    """Test ConfigurationError exception class."""

    def test_instantiation_with_message(self):
        error = ConfigurationError("test error message")
        assert str(error) == "test error message"

    def test_is_exception_subclass(self):
        error = ConfigurationError("test")
        assert isinstance(error, Exception)

    def test_can_be_raised_and_caught(self):
        try:
            raise ConfigurationError("domain not found")
        except ConfigurationError as e:
            assert str(e) == "domain not found"

    def test_subclassing(self):
        class ServiceConfigError(ConfigurationError):
            pass

        error = ServiceConfigError("service-specific error")
        assert isinstance(error, ConfigurationError)
        assert isinstance(error, Exception)
