"""Unit tests for configuration Pydantic models."""

import pytest
from pydantic import ValidationError

from civers_common import ConfigurationError
from configs.models import (
    AppConfig,
    ChangeDetectionStrategyConfig,
    ConfigDataModel,
    DomainConfig,
    KafkaConfig,
    TransportConfig,
)


def _config_with_domains(domains: list[DomainConfig]) -> ConfigDataModel:
    return ConfigDataModel(app=AppConfig(), domains=domains)




class TestCssSelectorsValidation:
    """css_selectors must be a list, validated only when detection_strategy == 'css_selector'."""

    def test_css_selectors_defaults_to_body_list(self):
        cfg = ChangeDetectionStrategyConfig()
        assert cfg.css_selectors == ["body"]

    def test_css_selectors_accepts_multiple(self):
        cfg = ChangeDetectionStrategyConfig(
            detection_strategy="css_selector",
            css_selectors=["div.content", "article", "main"],
        )
        assert cfg.css_selectors == ["div.content", "article", "main"]

    def test_css_selectors_rejects_empty_list_when_css_strategy(self):
        with pytest.raises(ValidationError):
            ChangeDetectionStrategyConfig(
                detection_strategy="css_selector",
                css_selectors=[],
            )

    def test_css_selectors_rejects_empty_strings_in_list(self):
        with pytest.raises(ValidationError):
            ChangeDetectionStrategyConfig(
                detection_strategy="css_selector",
                css_selectors=["div.content", "  ", "article"],
            )

    def test_css_selectors_strips_whitespace(self):
        cfg = ChangeDetectionStrategyConfig(
            detection_strategy="css_selector",
            css_selectors=["  div.content  ", " article "],
        )
        assert cfg.css_selectors == ["div.content", "article"]



    def test_single_selector_accepted(self):
        cfg = ChangeDetectionStrategyConfig(
            detection_strategy="css_selector",
            css_selectors=["main"],
        )
        assert cfg.css_selectors == ["main"]






class TestSimhashThresholdValidation:
    """simhash_threshold range-checked only when comparison_algorithm == 'simhash'."""

    def test_simhash_threshold_validated_when_simhash(self):
        cfg = ChangeDetectionStrategyConfig(
            comparison_algorithm="simhash",
            simhash_threshold=5,
        )
        assert cfg.simhash_threshold == 5

    def test_simhash_threshold_zero_accepted_when_simhash(self):
        cfg = ChangeDetectionStrategyConfig(
            comparison_algorithm="simhash",
            simhash_threshold=0,
        )
        assert cfg.simhash_threshold == 0

    def test_simhash_threshold_64_accepted_when_simhash(self):
        cfg = ChangeDetectionStrategyConfig(
            comparison_algorithm="simhash",
            simhash_threshold=64,
        )
        assert cfg.simhash_threshold == 64

    def test_simhash_threshold_out_of_range_rejected_when_simhash(self):
        with pytest.raises(ValidationError):
            ChangeDetectionStrategyConfig(
                comparison_algorithm="simhash",
                simhash_threshold=65,
            )

    def test_simhash_threshold_negative_rejected_when_simhash(self):
        with pytest.raises(ValidationError):
            ChangeDetectionStrategyConfig(
                comparison_algorithm="simhash",
                simhash_threshold=-1,
            )

    def test_simhash_threshold_ignored_when_simple_text(self):
        """simple_text algorithm doesn't use simhash_threshold, any value OK."""
        cfg = ChangeDetectionStrategyConfig(
            comparison_algorithm="simple_text",
            simhash_threshold=99,
        )
        assert cfg.comparison_algorithm == "simple_text"



class TestArchiveInterval:
    def test_archive_interval_defaults_to_none(self):
        cfg = ChangeDetectionStrategyConfig()
        assert cfg.archive_interval is None

    def test_archive_interval_accepted(self):
        cfg = ChangeDetectionStrategyConfig(archive_interval="7d")
        assert cfg.archive_interval == "7d"

    def test_get_archive_interval_seconds_none(self):
        cfg = ChangeDetectionStrategyConfig()
        assert cfg.get_archive_interval_seconds() is None

    def test_parse_hours(self):
        cfg = ChangeDetectionStrategyConfig(archive_interval="6h")
        assert cfg.get_archive_interval_seconds() == 6 * 3600

    def test_parse_days(self):
        cfg = ChangeDetectionStrategyConfig(archive_interval="7d")
        assert cfg.get_archive_interval_seconds() == 7 * 86400

    def test_parse_weeks(self):
        cfg = ChangeDetectionStrategyConfig(archive_interval="2w")
        assert cfg.get_archive_interval_seconds() == 2 * 7 * 86400

    def test_parse_months(self):
        cfg = ChangeDetectionStrategyConfig(archive_interval="1m")
        assert cfg.get_archive_interval_seconds() == 30 * 86400

    def test_invalid_format_raises(self):
        cfg = ChangeDetectionStrategyConfig(archive_interval="abc")
        with pytest.raises(ValueError, match="Invalid archive_interval"):
            cfg.get_archive_interval_seconds()

    def test_zero_value_raises(self):
        cfg = ChangeDetectionStrategyConfig(archive_interval="0d")
        with pytest.raises(ValueError, match="must be positive"):
            cfg.get_archive_interval_seconds()

    def test_negative_value_raises(self):
        cfg = ChangeDetectionStrategyConfig(archive_interval="-3d")
        with pytest.raises(ValueError, match="Invalid archive_interval"):
            cfg.get_archive_interval_seconds()


# ── Existing: General defaults & domain config ───────────────────────────


class TestChangeDetectionStrategyConfigDefaults:
    def test_defaults(self):
        cfg = ChangeDetectionStrategyConfig()
        assert cfg.detection_strategy == "css_selector"
        assert cfg.comparison_algorithm == "simple_text"
        assert cfg.rendering_engine == "httpx"
        assert cfg.css_selectors == ["body"]
        assert cfg.simhash_threshold == 3
        assert cfg.archive_interval is None
        assert cfg.request_timeout_seconds == 30


class TestDomainConfig:
    def test_invalid_domain_name_rejected(self):
        with pytest.raises(ValidationError):
            DomainConfig(name="not a valid name!!!")

    def test_accepts_wildcard_name(self):
        domain = DomainConfig(name="*.example.org", webpage_types="dynamic")
        assert domain.name == "*.example.org"


# ── Existing: Domain resolution ──────────────────────────────────────────


class TestConfigDataModelDomainResolution:
    def test_exact_match(self):
        config = _config_with_domains(
            [
                DomainConfig(
                    name="example.com",
                    change_detection=ChangeDetectionStrategyConfig(
                        comparison_algorithm="simhash"
                    ),
                    webpage_types="dynamic"
                )
            ]
        )
        domain = config.resolve_domain_for_url("https://example.com/page")
        assert domain.name == "example.com"
        assert domain.change_detection.comparison_algorithm == "simhash"

    def test_exact_match_case_insensitive(self):
        config = _config_with_domains([DomainConfig(name="Example.COM", webpage_types="dynamic")])
        domain = config.resolve_domain_for_url("https://example.com/resource")
        assert domain.name == "Example.COM"

    def test_wildcard_match(self):
        config = _config_with_domains([DomainConfig(name="*.other.org", webpage_types="dynamic")])
        domain = config.resolve_domain_for_url("https://sub.other.org/path")
        assert domain.name == "*.other.org"

    def test_default_fallback(self):
        config = _config_with_domains(
            [
                DomainConfig(name="example.com", webpage_types="dynamic"),
                DomainConfig(
                    name="default",
                    webpage_types="dynamic",
                    change_detection=ChangeDetectionStrategyConfig(
                        comparison_algorithm="simhash",
                    ),
                ),
            ]
        )
        domain = config.resolve_domain_for_url("https://unknown.example.org/")
        assert domain.name == "default"
        assert domain.change_detection.comparison_algorithm == "simhash"

    def test_unknown_domain_raises(self):
        config = _config_with_domains([DomainConfig(name="example.com", webpage_types="dynamic")])
        with pytest.raises(ConfigurationError, match="No domain configuration"):
            config.resolve_domain_for_url("https://unknown.org/")

    def test_disabled_domain_raises(self):
        config = _config_with_domains([DomainConfig(name="example.com", webpage_types="dynamic", enabled=False)])
        with pytest.raises(ConfigurationError, match="disabled"):
            config.resolve_domain_for_url("https://example.com/")

    def test_invalid_url_raises(self):
        config = _config_with_domains([DomainConfig(name="example.com", webpage_types="dynamic")])
        with pytest.raises(ConfigurationError, match="Could not extract hostname"):
            config.resolve_domain_for_url("not-a-valid-url")


# ── Existing: YAML integration tests ────────────────────────────────────


class TestConfigDataModelFromTestingYaml:
    """Validate ConfigDataModel built from defaults + environments/testing.yaml."""

    def test_testing_config_is_config_data_model(self, testing_config):
        assert isinstance(testing_config, ConfigDataModel)

    def test_testing_yaml_overrides_app_environment(self, testing_config):
        assert testing_config.app.environment == "testing"

    def test_testing_yaml_overrides_kafka(self, testing_config):
        kafka = testing_config.app.get_kafka_config()
        assert kafka is not None
        assert kafka.bootstrap_servers == "localhost:29092"
        assert kafka.consumer_group == "change_detection_group_test"

    def test_domains_loaded_from_defaults(self, testing_config):
        names = {d.name for d in testing_config.domains}
        assert "arachne.test.dainst.org" in names
        assert "example.com" in names

    def test_arachne_change_detection_from_domains_yaml(self, testing_config):
        domain = testing_config.resolve_domain_for_url(
            "https://arachne.test.dainst.org/entity/1"
        )
        assert domain.change_detection.detection_strategy == "css_selector"
        assert domain.change_detection.comparison_algorithm == "simhash"
        assert domain.change_detection.archive_interval == "1m"

    def test_example_com_change_detection_from_domains_yaml(self, testing_config):
        domain = testing_config.resolve_domain_for_url("https://example.com/page")
        assert domain.change_detection.css_selectors == ["article.content", "div.main-text"]
        assert domain.change_detection.rendering_engine == "httpx"
        assert domain.change_detection.archive_interval == "7d"

    def test_transport_synced_to_app(self, testing_config):
        assert testing_config.app.transport is not None
        assert testing_config.transport is not None
        assert testing_config.app.transport.kafka is testing_config.transport.kafka



class TestConfigDataModelConstruction:
    def test_transport_requires_kafka_when_enabled(self):
        with pytest.raises(ValidationError, match="not configured"):
            TransportConfig(enabled=["kafka"], kafka=None)

    def test_kafka_requires_topics(self):
        with pytest.raises(ValidationError, match="At least one Kafka topic"):
            KafkaConfig(bootstrap_servers="localhost:9092", topics={})
