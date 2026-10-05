import pytest
from archive_generators.archive_generator_factory import ArchiveGeneratorFactory
from configs.models import DomainConfig, GeneratorConfig


@pytest.fixture(autouse=True)
def mock_generator_dependencies(monkeypatch):
    """Mock dependency validation to allow tests to run without Node/Chromium."""
    from archive_generators.scoop.scoop_generator import ScoopGenerator
    from archive_generators.singlefile.singlefile_generator import SingleFileGenerator

    monkeypatch.setattr(ScoopGenerator, "_validate_dependencies", lambda self: None)
    monkeypatch.setattr(
        SingleFileGenerator, "_validate_dependencies", lambda self: None
    )


def _domain(*generators: GeneratorConfig) -> DomainConfig:
    """A single test domain served by ``generators``."""
    return DomainConfig(
        name="test.com", webpage_types="dynamic", generators=list(generators)
    )


def test_factory_initialization(sample_config):
    factory = ArchiveGeneratorFactory(sample_config)
    info = factory.get_factory_info()
    assert {"scoop", "singlefile", "browsertrix"} <= set(info["supported_generators"])


def test_validate_domain_configs_success(sample_config):
    # Valid configuration: scoop produces warc
    sample_config.domains = [_domain(GeneratorConfig(name="scoop", artifacts=["warc"]))]

    factory = ArchiveGeneratorFactory(sample_config)
    # Should not raise
    factory.validate_domain_configs()


def test_validate_domain_configs_invalid_generator(sample_config):
    # Invalid generator name
    generator = GeneratorConfig(name="scoop", artifacts=["warc"])
    sample_config.domains = [_domain(generator)]
    generator.name = "invalid_gen"  # Exercise the factory guard after model validation.

    factory = ArchiveGeneratorFactory(sample_config)
    with pytest.raises(ValueError, match="requests unknown generator"):
        factory.validate_domain_configs()


def test_validate_domain_configs_unsupported_artifact(sample_config):
    # scoop cannot produce "unsupported"
    generator = GeneratorConfig(name="scoop", artifacts=["warc"])
    sample_config.domains = [_domain(generator)]
    generator.artifacts = ["unsupported"]

    factory = ArchiveGeneratorFactory(sample_config)
    with pytest.raises(ValueError, match="requests unsupported artifacts"):
        factory.validate_domain_configs()


def test_create_generators(sample_config):
    domain_config = _domain(
        GeneratorConfig(name="scoop", artifacts=["warc"]),
        GeneratorConfig(name="singlefile", artifacts=["singlefile"]),
    )

    factory = ArchiveGeneratorFactory(sample_config)
    generators = factory.create_generators(domain_config)

    assert len(generators) == 2
    assert [config for config, _ in generators] == domain_config.generators
    from archive_generators.scoop.scoop_generator import ScoopGenerator
    from archive_generators.singlefile.singlefile_generator import SingleFileGenerator

    assert isinstance(generators[0][1], ScoopGenerator)
    assert isinstance(generators[1][1], SingleFileGenerator)


def test_generator_singleton_per_factory(sample_config):
    domain_config = _domain(GeneratorConfig(name="scoop", artifacts=["warc"]))

    factory = ArchiveGeneratorFactory(sample_config)
    gens1 = factory.create_generators(domain_config)
    gens2 = factory.create_generators(domain_config)

    # Same instance should be returned
    assert gens1[0][1] is gens2[0][1]
