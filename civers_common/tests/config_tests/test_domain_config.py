"""Tests for BaseDomainConfig."""

import pytest
from pydantic import ValidationError

from civers_common.configs.models import BaseDomainConfig


class TestBaseDomainConfig:
    """Test BaseDomainConfig base class."""

    def test_valid_fqdn(self):
        config = BaseDomainConfig(name="example.com")
        assert config.name == "example.com"

    def test_valid_wildcard(self):
        config = BaseDomainConfig(name="*.dainst.org")
        assert config.name == "*.dainst.org"

    def test_valid_default(self):
        config = BaseDomainConfig(name="default")
        assert config.name == "default"

    def test_valid_local_hostname(self):
        config = BaseDomainConfig(name="localhost")
        assert config.name == "localhost"

    def test_empty_name_rejected(self):
        with pytest.raises(ValidationError, match="Domain name cannot be empty"):
            BaseDomainConfig(name="")

    def test_whitespace_name_rejected(self):
        with pytest.raises(ValidationError, match="Domain name cannot be empty"):
            BaseDomainConfig(name="   ")

    def test_name_stripped(self):
        config = BaseDomainConfig(name="  example.com  ")
        assert config.name == "example.com"

    def test_defaults(self):
        config = BaseDomainConfig(name="example.com")
        assert config.enabled is True
        assert config.description == ""

    def test_enabled_false(self):
        config = BaseDomainConfig(name="example.com", enabled=False)
        assert config.enabled is False

    def test_description(self):
        config = BaseDomainConfig(name="example.com", description="A test domain")
        assert config.description == "A test domain"

    def test_extra_fields_ignored(self):
        config = BaseDomainConfig(
            name="example.com",
            unknown_field="should be ignored",
        )
        assert not hasattr(config, "unknown_field")

    def test_is_wildcard_true(self):
        config = BaseDomainConfig(name="*.dainst.org")
        assert config.is_wildcard is True

    def test_is_wildcard_false(self):
        config = BaseDomainConfig(name="example.com")
        assert config.is_wildcard is False

    def test_is_default_true(self):
        config = BaseDomainConfig(name="default")
        assert config.is_default is True

    def test_is_default_false(self):
        config = BaseDomainConfig(name="example.com")
        assert config.is_default is False

    def test_is_default_case_insensitive(self):
        config = BaseDomainConfig(name="Default")
        assert config.is_default is True

    def test_subclass_inherits_validators(self):
        """Verify subclasses get domain name validation for free."""

        class ServiceDomainConfig(BaseDomainConfig):
            extra_field: str = "test"

        with pytest.raises(ValidationError):
            ServiceDomainConfig(name="")

        config = ServiceDomainConfig(name="example.com", extra_field="custom")
        assert config.extra_field == "custom"
        assert config.is_wildcard is False


@pytest.mark.parametrize("name", [
    "https://www.aljazeera.net",
    "http://www.aljazeera.net/",
    "https://localhost",
    "//www.aljazeera.net",
    "www.aljazeera.net/news/liveblog",
    "www.aljazeera.net?update=9784467",
    "www.aljazeera.net#latest",
    "user@www.aljazeera.net",
    "*.example.com/path",
    "www.aljazeera.net\\news",
    "www.aljazeera .net",
])
def test_url_parts_are_rejected_before_domain_matching(name):
    with pytest.raises(ValidationError, match="Domain name must be a hostname") as error:
        BaseDomainConfig(name=name)
    assert error.value.errors()[0]["loc"] == ("name",)


@pytest.mark.parametrize("name", [
    "www.aljazeera.net",
    "www.aljazeera.net:8080",
    "*.aljazeera.net",
    "*",
    "127.0.0.1",
    "::1",
    "local_demo",
])
def test_hostname_validation_preserves_supported_domain_names(name):
    assert BaseDomainConfig(name=name).name == name
