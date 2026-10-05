"""Check archive-specific configuration. Shared model tests live in civers_common."""

import pytest
from archive_generators.browsertrix import BrowsertrixGenerator
from archive_generators.scoop import ScoopGenerator
from archive_generators.singlefile import SingleFileGenerator
from configs.models import (
    AppConfig,
    ConfigDataModel,
    DomainConfig,
    GeneratorConfig,
    StorageConfig,
    TransportConfig,
)
from pydantic import ValidationError

# Helpers
def _storage(**kwargs) -> StorageConfig:
    defaults = {
        "enabled": ["civers_rest_api"],
        "backends": {
            "civers_rest_api": {"upload_url": "http://localhost:8000/api/upload"}
        },
    }
    return StorageConfig(**{**defaults, **kwargs})


def _transport(**kwargs) -> TransportConfig:
    defaults = {
        "enabled": ["kafka"],
        "transports": {
            "kafka": {
                "bootstrap_servers": "localhost:9092",
                "topics": {"requests": "archive.requests"},
                "consumer_group": "test-group",
            }
        },
    }
    return TransportConfig(**{**defaults, **kwargs})


def _app(**kwargs) -> AppConfig:
    defaults = {
        "archive_directory": "/tmp/archives",
        "storage": _storage(),
    }
    return AppConfig(**{**defaults, **kwargs})


# GeneratorConfig
class TestGeneratorConfig:
    def test_unknown_generator_rejected(self):
        with pytest.raises(ValidationError, match="Unknown generator: unknown"):
            GeneratorConfig(name="unknown", artifacts=["warc"])

    @pytest.mark.parametrize("name", ["browsertrix", "scoop", "singlefile"])
    def test_empty_artifacts_rejected(self, name):
        with pytest.raises(ValidationError, match="at least one supported artifact"):
            GeneratorConfig(name=name, artifacts=[])

    @pytest.mark.parametrize(
        ("name", "artifacts"),
        [
            ("browsertrix", ["warc", "summary"]),
            ("scoop", ["warc", "singlefile"]),
            ("singlefile", ["singlefile", "warc"]),
        ],
    )
    def test_unsupported_artifacts_rejected(self, name, artifacts):
        with pytest.raises(ValidationError, match="at least one supported artifact"):
            GeneratorConfig(name=name, artifacts=artifacts)

    @pytest.mark.parametrize(
        ("name", "generator_class"),
        [
            ("browsertrix", BrowsertrixGenerator),
            ("scoop", ScoopGenerator),
            ("singlefile", SingleFileGenerator),
        ],
    )
    def test_reads_generator_declaration_without_instantiation(
        self, monkeypatch, name, generator_class
    ):
        def fail_if_instantiated(*args, **kwargs):
            raise AssertionError("Config validation must not construct generators")

        monkeypatch.setattr(generator_class, "__init__", fail_if_instantiated)
        monkeypatch.setattr(
            generator_class,
            "CAPABILITIES",
            [*generator_class.CAPABILITIES, "custom-artifact"],
        )

        config = GeneratorConfig(name=name, artifacts=["custom-artifact"])

        assert config.artifacts == ["custom-artifact"]


# DomainConfig
class TestDomainConfig:
    """Require capture generators in domain settings."""

    def test_requires_at_least_one_generator(self):
        with pytest.raises(ValidationError, match="at least one generator"):
            DomainConfig(name="example.com", generators=[], webpage_types="dynamic")

    def test_accepts_single_generator(self):
        domain = DomainConfig(
            name="example.com",
            generators=[GeneratorConfig(name="scoop", artifacts=["warc"])],
            webpage_types="dynamic",
        )
        assert len(domain.generators) == 1
        assert domain.generators[0].name == "scoop"

    def test_accepts_multiple_generators(self):
        domain = DomainConfig(
            name="example.com",
            generators=[
                GeneratorConfig(name="scoop", artifacts=["warc", "screenshot"]),
                GeneratorConfig(name="singlefile", artifacts=["singlefile"]),
            ],
            webpage_types="dynamic",
        )
        assert len(domain.generators) == 2

    def test_generator_config_stores_artifacts(self):
        gen = GeneratorConfig(
            name="scoop", artifacts=["warc", "screenshot", "dom-snapshot"]
        )
        assert gen.artifacts == ["warc", "screenshot", "dom-snapshot"]


# AppConfig
class TestAppConfig:
    """Check capture paths, tool settings and storage configuration."""

    def test_defaults(self):
        cfg = _app()
        assert cfg.name == "archive_generator"
        assert cfg.scoop_cli_command == "scoop"
        assert cfg.scoop_timeout_sec == 120
        assert cfg.scoop_extra_args is None
        assert cfg.ssrf_protection_enabled is True

    def test_archive_directory_is_required(self):
        with pytest.raises(ValidationError):
            AppConfig(storage=_storage())

    def test_storage_is_required(self):
        with pytest.raises(ValidationError):
            AppConfig(archive_directory="/tmp/archives")

    @pytest.mark.parametrize(
        "field",
        [
            "archive_directory",
            "scoop_cli_command",
            "singlefile_binary_path",
            "browsertrix_jobs_dir",
        ],
    )
    @pytest.mark.parametrize("blank", ["", "   "])
    def test_blank_paths_and_commands_rejected(self, field: str, blank: str):
        """A blank path silently resolves to somewhere unintended, so reject it here."""
        with pytest.raises(ValidationError, match=f"'{field}' cannot be blank"):
            _app(**{field: blank})

    @pytest.mark.parametrize(
        "field",
        ["scoop_timeout_sec", "singlefile_timeout_sec", "browsertrix_timeout_sec"],
    )
    @pytest.mark.parametrize("bad", [0, -5])
    def test_non_positive_timeouts_rejected(self, field: str, bad: int):
        with pytest.raises(ValidationError, match="greater than 0"):
            _app(**{field: bad})

    def test_surrounding_whitespace_is_stripped(self):
        cfg = _app(archive_directory="  /tmp/archives  ", scoop_cli_command=" scoop ")
        assert cfg.archive_directory == "/tmp/archives"
        assert cfg.scoop_cli_command == "scoop"

    def test_get_storage_config_returns_storage(self):
        storage = _storage()
        cfg = _app(storage=storage)
        assert cfg.get_storage_config() is storage

    def test_scoop_extra_args_accepts_list(self):
        cfg = _app(scoop_extra_args=["--log-level", "info", "--no-sandbox"])
        assert cfg.scoop_extra_args == ["--log-level", "info", "--no-sandbox"]

    def test_browsertrix_defaults(self):
        cfg = _app()
        assert cfg.browsertrix_jobs_dir == "/jobs"
        assert cfg.browsertrix_timeout_sec == 300
        assert cfg.browsertrix_extra_args is None

    def test_browsertrix_accepts_custom(self):
        cfg = _app(
            browsertrix_jobs_dir="/shared/jobs",
            browsertrix_timeout_sec=600,
            browsertrix_extra_args=["--scopeType", "page"],
        )
        assert cfg.browsertrix_jobs_dir == "/shared/jobs"
        assert cfg.browsertrix_timeout_sec == 600
        assert cfg.browsertrix_extra_args == ["--scopeType", "page"]


# ConfigDataModel
class TestConfigDataModelConstruction:
    """ConfigDataModel structure and validators."""

    def test_root_transport_exposes_adapter_entries(self):
        """Adapters read their config from the root `transport.transports.<name>`."""
        config = ConfigDataModel(
            domains=[
                DomainConfig(
                    name="example.com",
                    generators=[GeneratorConfig(name="scoop", artifacts=["warc"])],
                    webpage_types="dynamic",
                )
            ],
            app=_app(),
            transport=_transport(),
        )
        kafka = config.transport.get_transport_config("kafka")
        assert kafka["bootstrap_servers"] == "localhost:9092"

    def test_root_transport_is_required(self):
        """AG needs a transport to run; the root `transport` block is mandatory."""
        with pytest.raises(ValidationError):
            ConfigDataModel(
                domains=[
                    DomainConfig(
                        name="example.com",
                        generators=[GeneratorConfig(name="scoop", artifacts=["warc"])],
                        webpage_types="dynamic",
                    )
                ],
                app=_app(),
            )
