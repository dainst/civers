import pytest
from unittest.mock import MagicMock
from archive_generators.archive_generator_factory import ArchiveGeneratorFactory
from configs.models import ConfigDataModel, DomainConfig, GeneratorConfig

@pytest.fixture
def mock_config():
    config = MagicMock(spec=ConfigDataModel)
    return config

@pytest.fixture(autouse=True)
def mock_generator_dependencies(monkeypatch):
    """Mock dependency validation to allow tests to run without Node/Chromium."""
    from archive_generators.scoop.scoop_generator import ScoopGenerator
    from archive_generators.singlefile.singlefile_generator import SingleFileGenerator
    
    monkeypatch.setattr(ScoopGenerator, "_validate_dependencies", lambda self: None)
    monkeypatch.setattr(SingleFileGenerator, "_validate_dependencies", lambda self: None)

def test_factory_initialization(mock_config):
    factory = ArchiveGeneratorFactory(mock_config)
    info = factory.get_factory_info()
    assert "scoop" in info["supported_generators"]
    assert "singlefile" in info["supported_generators"]

def test_validate_domain_configs_success(mock_config):
    # Valid configuration: scoop produces warc
    gen_config = GeneratorConfig(name="scoop", artifacts=["warc"])
    domain_config = DomainConfig(name="test.com", webpage_types="dynamic", generators=[gen_config])
    mock_config.domains = [domain_config]
    
    factory = ArchiveGeneratorFactory(mock_config)
    # Should not raise
    factory.validate_domain_configs()

def test_validate_domain_configs_invalid_generator(mock_config):
    # Invalid generator name
    gen_config = GeneratorConfig(name="invalid_gen", artifacts=["warc"])
    domain_config = DomainConfig(name="test.com", webpage_types="dynamic", generators=[gen_config])
    mock_config.domains = [domain_config]
    
    factory = ArchiveGeneratorFactory(mock_config)
    with pytest.raises(ValueError, match="requests unknown generator"):
        factory.validate_domain_configs()

def test_validate_domain_configs_unsupported_artifact(mock_config):
    # scoop cannot produce "unsupported"
    gen_config = GeneratorConfig(name="scoop", artifacts=["unsupported"])
    domain_config = DomainConfig(name="test.com", webpage_types="dynamic", generators=[gen_config])
    mock_config.domains = [domain_config]
    
    factory = ArchiveGeneratorFactory(mock_config)
    with pytest.raises(ValueError, match="requests unsupported artifacts"):
        factory.validate_domain_configs()

def test_create_generators(mock_config):
    gen_config1 = GeneratorConfig(name="scoop", artifacts=["warc"])
    gen_config2 = GeneratorConfig(name="singlefile", artifacts=["singlefile"])
    domain_config = DomainConfig(name="test.com", webpage_types="dynamic", generators=[gen_config1, gen_config2])
    
    factory = ArchiveGeneratorFactory(mock_config)
    generators = factory.create_generators(domain_config)
    
    assert len(generators) == 2
    assert generators[0].__class__.__name__ == "ScoopGenerator"
    assert generators[1].__class__.__name__ == "SingleFileGenerator"

def test_generator_singleton_per_factory(mock_config):
    gen_config = GeneratorConfig(name="scoop", artifacts=["warc"])
    domain_config = DomainConfig(name="test.com", webpage_types="dynamic", generators=[gen_config])
    
    factory = ArchiveGeneratorFactory(mock_config)
    gens1 = factory.create_generators(domain_config)
    gens2 = factory.create_generators(domain_config)
    
    # Same instance should be returned
    assert gens1[0] is gens2[0]
