"""
Tests for metadata_extraction_services/url_validator.py

UrlValidator validates URLs in three steps:
1. Format check — must be non-empty string, have scheme+netloc, and use http/https
2. Domain extraction — pulls netloc from the parsed URL
3. Domain support check — calls config_data_model.resolve_domain(domain), treating a
   civers_common.ConfigurationError as "not supported"

Returns a dict with keys: valid (bool), domain_supported (bool), reason (str), domain (str).
"""

from unittest.mock import Mock

import pytest
from civers_common import ConfigurationError

from metadata_extraction_services.url_validator import UrlValidator


@pytest.fixture
def supported_config():
    """Mock ConfigDataModel that resolves only arachne.dainst.org."""
    config = Mock()

    def _resolve(domain):
        if domain == "arachne.dainst.org":
            return Mock()
        raise ConfigurationError(f"No domain configuration for '{domain}'")

    config.resolve_domain.side_effect = _resolve
    return config


@pytest.fixture
def validator(supported_config):
    return UrlValidator(supported_config)


@pytest.mark.unit
class TestUrlValidatorValidateUrl:
    def test_valid_supported_url(self, validator):
        result = validator.validate_url("https://arachne.dainst.org/entity/1")

        assert result["valid"] is True
        assert result["domain_supported"] is True
        assert result["domain"] == "arachne.dainst.org"

    def test_valid_unsupported_domain(self, validator):
        result = validator.validate_url("https://unknown.example.com/page")

        assert result["valid"] is True
        assert result["domain_supported"] is False
        assert "domain" in result

    def test_empty_url_returns_invalid(self, validator):
        result = validator.validate_url("")

        assert result["valid"] is False
        assert "non-empty string" in result["reason"]

    def test_none_url_returns_invalid(self, validator):
        result = validator.validate_url(None)

        assert result["valid"] is False

    def test_url_without_scheme_returns_invalid(self, validator):
        result = validator.validate_url("arachne.dainst.org/entity/1")

        assert result["valid"] is False
        assert "scheme" in result["reason"]

    def test_ftp_scheme_returns_invalid(self, validator):
        result = validator.validate_url("ftp://arachne.dainst.org/file")

        assert result["valid"] is False
        assert "supported" in result["reason"]

    def test_http_scheme_accepted(self, validator):
        result = validator.validate_url("http://arachne.dainst.org/entity/1")

        assert result["valid"] is True

    def test_reason_present_in_all_results(self, validator):
        for url in ["", "https://arachne.dainst.org/x", "ftp://x.com"]:
            result = validator.validate_url(url)
            assert "reason" in result


@pytest.mark.unit
class TestUrlValidatorParseDomain:
    def test_returns_domain_from_https_url(self, validator):
        domain = validator.parse_domain_from_url("https://foo.bar.com/path?q=1")

        assert domain == "foo.bar.com"

    def test_returns_empty_string_for_non_url(self, validator):
        # urlparse never raises — returns netloc="" for garbage input
        domain = validator.parse_domain_from_url("not-a-url")

        assert domain == ""

    def test_preserves_port_in_domain(self, validator):
        domain = validator.parse_domain_from_url("http://localhost:8080/page")

        assert domain == "localhost:8080"


@pytest.mark.unit
class TestUrlValidatorDomainFormat:
    def test_valid_domain(self, validator):
        assert validator.is_valid_domain_format("foo.bar.com") is True

    def test_domain_without_dot_is_invalid(self, validator):
        assert validator.is_valid_domain_format("localhost") is False

    def test_domain_starting_with_dot_is_invalid(self, validator):
        assert validator.is_valid_domain_format(".foo.com") is False

    def test_domain_ending_with_dot_is_invalid(self, validator):
        assert validator.is_valid_domain_format("foo.com.") is False

    def test_domain_with_space_is_invalid(self, validator):
        assert validator.is_valid_domain_format("foo bar.com") is False

    def test_domain_with_slash_is_invalid(self, validator):
        assert validator.is_valid_domain_format("foo.com/path") is False

    def test_empty_string_is_invalid(self, validator):
        assert validator.is_valid_domain_format("") is False
