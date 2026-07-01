"""Shared pytest fixtures for all tests.

This conftest.py is at the root of tests/ directory and provides fixtures
available to all test modules (unit/, integration/, etc.).
"""

import os

import pytest

from configs.loaders import YamlFileConfigLoader
from configs.models import ConfigDataModel
from orchestration_services import OrchestratorService


@pytest.fixture(scope="session", autouse=True)
def force_testing_environment(request):
    """Force testing environment for all tests.

    This fixture automatically sets CONFIG_ENVIRONMENT=testing before any tests run,
    ensuring that testing.yaml is loaded instead of docker.yaml (which would be
    detected if /.dockerenv exists).

    This is a session-scoped autouse fixture, so it runs once at the start of the
    test session and affects all tests.

    Note: Tests that use temporary config directories (test_config_loader.py,
    test_config_validation.py, test_env_variable_expansion.py) should unset
    CONFIG_ENVIRONMENT themselves if needed.
    """
    old_env = os.environ.get("CONFIG_ENVIRONMENT")
    os.environ["CONFIG_ENVIRONMENT"] = "testing"
    yield
    # Restore original environment after all tests
    if old_env is not None:
        os.environ["CONFIG_ENVIRONMENT"] = old_env
    else:
        os.environ.pop("CONFIG_ENVIRONMENT", None)


@pytest.fixture(scope="session")
def test_config() -> ConfigDataModel:
    """Load configuration from testing.yaml environment file.

    This fixture loads the actual testing.yaml configuration instead of
    using hardcoded values. The config loader auto-detects the 'testing'
    environment when PYTEST_CURRENT_TEST environment variable is set.

    The configuration is loaded from:
    - configs/data/defaults/ (base config: workflows, domains, etc.)
    - configs/data/environments/testing.yaml (test-specific overrides)

    Benefits:
    - Single source of truth (testing.yaml)
    - No hardcoded values scattered in test files
    - Easy to update test configuration
    - Inherits workflows and domains from defaults/
    - Consistent across all tests

    Returns:
        ConfigDataModel: Complete configuration for testing

    Example:
        def test_something(test_config):
            assert test_config.app.environment == "testing"
            assert test_config.transport.kafka.bootstrap_servers == "localhost:29092"
    """
    config_loader = YamlFileConfigLoader()
    return config_loader.load()


@pytest.fixture
def orchestrator(test_config: ConfigDataModel) -> OrchestratorService:
    """Provides initialized OrchestratorService with test configuration.

    This fixture creates a fully initialized orchestrator using the test_config
    fixture. Use this when you need to test orchestrator functionality without
    manually creating the service.

    Returns:
        OrchestratorService: Initialized orchestrator service

    Example:
        def test_workflow(orchestrator):
            instruction = orchestrator.start_workflow(
                request_id="test-001",
                url="https://example.com"
            )
            assert instruction is not None
    """
    return OrchestratorService(test_config)
