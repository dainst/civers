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


class TestNormalizeHostnameIsIPv6Safe:
    """An IPv6 literal is mostly colons, and urlparse hands it over without brackets."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("Example.COM", "example.com"),
            ("example.com:8080", "example.com"),
            ("::1", "::1"),
            ("[::1]:8080", "::1"),
            ("[2001:db8::1]", "2001:db8::1"),
            ("2001:db8::1", "2001:db8::1"),
        ],
    )
    def test_normalize_hostname(self, raw, expected):
        assert DomainResolutionMixin.normalize_hostname(raw) == expected

    def test_ipv6_url_resolves_to_its_own_entry(self):
        config = TestConfig(domains=[DomainConfig(name="::1")])
        assert config.resolve_domain_for_url("http://[::1]:8080/x").name == "::1"


class TestWildcardSpecificity:
    """Reordering two blocks in a YAML file must not change which policy a site gets."""

    @pytest.mark.parametrize(
        "order", [["*.org", "*.dainst.org"], ["*.dainst.org", "*.org"]]
    )
    def test_most_specific_wildcard_wins_regardless_of_order(self, order):
        config = TestConfig(domains=[DomainConfig(name=n) for n in order])
        assert config.resolve_domain("sub.dainst.org").name == "*.dainst.org"

    @pytest.mark.parametrize("order", [["*", "*.org"], ["*.org", "*"]])
    def test_bare_catch_all_sorts_last(self, order):
        config = TestConfig(domains=[DomainConfig(name=n) for n in order])
        assert config.resolve_domain("sub.dainst.org").name == "*.org"

    def test_bare_catch_all_matches_everything_else(self):
        config = TestConfig(domains=[DomainConfig(name="*")])
        assert config.resolve_domain("anything.com").name == "*"

    def test_a_disabled_wildcard_is_reported_not_skipped(self):
        config = TestConfig(domains=[DomainConfig(name="*.org", enabled=False)])
        with pytest.raises(ConfigurationError, match="is disabled"):
            config.resolve_domain("sub.org")

    @pytest.mark.parametrize("name", ["example.*", "*example.com", "a*b.com", "**"])
    def test_patterns_the_matcher_cannot_support_are_rejected(self, name):
        """Resolution is suffix matching; anything else validates and matches nothing."""
        with pytest.raises(ValueError, match="only suffix matching is supported"):
            DomainConfig(name=name)


class TestDefaultFallbackIsCaseInsensitive:
    """is_default and the resolver must agree, or one capital letter removes the
    fallback while every health check still reports it present."""

    @pytest.mark.parametrize("name", ["default", "Default", "DEFAULT"])
    def test_default_entry_is_the_fallback_whatever_its_case(self, name):
        config = TestConfig(domains=[DomainConfig(name=name)])
        assert config.resolve_domain("unknown.org").name == name

    def test_a_disabled_default_is_reported(self):
        config = TestConfig(domains=[DomainConfig(name="Default", enabled=False)])
        with pytest.raises(ConfigurationError, match="disabled"):
            config.resolve_domain("unknown.org")


def test_domain_matching_ignores_page_path_and_query():
    config = TestConfig(domains=[DomainConfig(name="www.aljazeera.net")])
    url = "https://www.aljazeera.net/news/liveblog/2026/9/14/%D8%A5%D9%8A?update=9784467"
    assert config.resolve_domain_for_url(url).name == "www.aljazeera.net"
