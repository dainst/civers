"""Tests for DomainResolutionMixin."""

import pytest
from pydantic import BaseModel, Field

from civers_common.configs.exceptions import ConfigurationError
from civers_common.configs.models import BaseDomainConfig, DomainResolutionMixin


class DomainConfig(BaseDomainConfig):
    """Test subclass."""
    pass


class TestConfig(DomainResolutionMixin, BaseModel):
    """Test root config using the mixin."""
    domains: list[DomainConfig] = Field(default_factory=list)


class TestDomainResolution:
    """Test DomainResolutionMixin.resolve_domain()."""

    def test_exact_match(self):
        config = TestConfig(domains=[DomainConfig(name="example.com")])
        assert config.resolve_domain("example.com").name == "example.com"

    def test_case_insensitive(self):
        config = TestConfig(domains=[DomainConfig(name="Example.COM")])
        assert config.resolve_domain("example.com").name == "Example.COM"

    def test_wildcard_match(self):
        config = TestConfig(domains=[DomainConfig(name="*.dainst.org")])
        assert config.resolve_domain("sub.dainst.org").name == "*.dainst.org"

    def test_wildcard_no_match(self):
        config = TestConfig(domains=[DomainConfig(name="*.dainst.org")])
        with pytest.raises(ConfigurationError, match="No domain configuration"):
            config.resolve_domain("other.com")

    def test_default_fallback(self):
        config = TestConfig(
            domains=[
                DomainConfig(name="other.com"),
                DomainConfig(name="default"),
            ]
        )
        assert config.resolve_domain("unknown.org").name == "default"

    def test_exact_before_wildcard(self):
        config = TestConfig(
            domains=[
                DomainConfig(name="*.dainst.org"),
                DomainConfig(name="specific.dainst.org"),
            ]
        )
        assert config.resolve_domain("specific.dainst.org").name == "specific.dainst.org"

    def test_wildcard_before_default(self):
        config = TestConfig(
            domains=[
                DomainConfig(name="default"),
                DomainConfig(name="*.dainst.org"),
            ]
        )
        assert config.resolve_domain("sub.dainst.org").name == "*.dainst.org"

    def test_disabled_domain_raises(self):
        config = TestConfig(
            domains=[DomainConfig(name="example.com", enabled=False)]
        )
        with pytest.raises(ConfigurationError, match="disabled"):
            config.resolve_domain("example.com")

    def test_disabled_wildcard_raises(self):
        config = TestConfig(
            domains=[DomainConfig(name="*.dainst.org", enabled=False)]
        )
        with pytest.raises(ConfigurationError, match="disabled"):
            config.resolve_domain("sub.dainst.org")

    def test_disabled_default_raises(self):
        config = TestConfig(
            domains=[DomainConfig(name="default", enabled=False)]
        )
        with pytest.raises(ConfigurationError, match="disabled"):
            config.resolve_domain("unknown.org")

    def test_no_match_raises(self):
        config = TestConfig(domains=[DomainConfig(name="other.com")])
        with pytest.raises(ConfigurationError, match="No domain configuration"):
            config.resolve_domain("unknown.org")

    def test_empty_domains_raises(self):
        config = TestConfig(domains=[])
        with pytest.raises(ConfigurationError, match="No domain configuration"):
            config.resolve_domain("example.com")

    def test_port_stripped(self):
        config = TestConfig(domains=[DomainConfig(name="localhost")])
        assert config.resolve_domain("localhost:8080").name == "localhost"


class TestDomainResolutionForUrl:
    """Test DomainResolutionMixin.resolve_domain_for_url()."""

    def test_url_resolution(self):
        config = TestConfig(domains=[DomainConfig(name="example.com")])
        result = config.resolve_domain_for_url("https://example.com/path")
        assert result.name == "example.com"

    def test_url_without_hostname_raises(self):
        config = TestConfig(domains=[DomainConfig(name="example.com")])
        with pytest.raises(ConfigurationError, match="Could not extract hostname"):
            config.resolve_domain_for_url("not-a-url")


class TestNormalizeHostname:
    """Test DomainResolutionMixin.normalize_hostname()."""

    def test_lowercase(self):
        assert DomainResolutionMixin.normalize_hostname("Example.COM") == "example.com"

    def test_strip_whitespace(self):
        assert DomainResolutionMixin.normalize_hostname("  example.com  ") == "example.com"

    def test_strip_port(self):
        assert DomainResolutionMixin.normalize_hostname("localhost:8080") == "localhost"

    def test_empty_string(self):
        assert DomainResolutionMixin.normalize_hostname("") == ""
