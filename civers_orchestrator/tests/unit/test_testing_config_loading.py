"""Test that testing.yaml configuration is loaded correctly in pytest.

This test verifies that:
1. Config loader auto-detects 'testing' environment
2. testing.yaml is loaded and merged with defaults
3. Test-specific values override defaults
4. Workflows and domains are inherited from defaults/
"""

from configs.loaders import YamlFileConfigLoader


class TestConfigurationLoading:
    """Test configuration loading in pytest environment."""

    def test_config_auto_detects_testing_environment(self, test_config):
        """Test that pytest automatically uses testing environment."""
        assert test_config.app.environment == "testing"
        assert test_config.app.name == "civers-orchestrator-test"

    def test_config_loads_from_testing_yaml(self):
        """Test loading config directly (without fixture)."""
        config = YamlFileConfigLoader().load()

        # Should auto-detect testing environment in pytest
        assert config.app.environment == "testing"

    def test_kafka_bootstrap_servers_from_testing_yaml(self, test_config):
        """Test that Kafka bootstrap servers come from testing.yaml."""
        # testing.yaml specifies localhost:29092
        assert test_config.transport.kafka.bootstrap_servers == "localhost:29092"

    def test_kafka_consumer_group_from_testing_yaml(self, test_config):
        """Test that consumer group comes from testing.yaml."""
        expected_group = "civers-orchestrator-test-group"
        assert test_config.transport.kafka.consumer.group_id == expected_group

    def test_topics_have_test_prefix(self, test_config):
        """Test that Kafka topics have 'test.' prefix from testing.yaml."""
        topics = test_config.transport.kafka.topics

        # All orchestrator topics should have test. prefix
        assert topics.orchestrator_requests == "test.orchestrator.requests"
        assert topics.orchestrator_status == "test.orchestrator.status"
        assert topics.orchestrator_completed == "test.orchestrator.completed"
        assert topics.orchestrator_failed == "test.orchestrator.failed"

    def test_component_mappings_have_test_topics(self, test_config):
        """Test that component mappings use test. prefix."""
        mappings = test_config.transport.kafka.component_mappings

        # Archive generator topics
        archive = mappings["archive_generator"]
        assert archive.request_topic == "test.archive.requests"
        assert archive.response_topics["success"] == "test.archive.completed"
        assert archive.response_topics["failure"] == "test.archive.failed"

        # Metadata extractor topics
        metadata = mappings["metadata_extractor"]
        assert metadata.request_topic == "test.metadata.requests"
        assert metadata.response_topics["success"] == "test.metadata.completed"
        assert metadata.response_topics["failure"] == "test.metadata.failed"

    def test_workflows_defined_in_testing_yaml(self, test_config):
        """Test that workflows are defined in testing.yaml (overrides defaults)."""
        workflow_names = [w.name for w in test_config.workflows]

        # Should include test-specific workflows (simpler than production)
        assert "simple_workflow" in workflow_names
        assert "archaeology_workflow" in workflow_names
        assert "dainst_workflow" in workflow_names
        assert len(workflow_names) == 3  # Only 3 test workflows

    def test_domains_defined_in_testing_yaml(self, test_config):
        """Test that domains are defined in testing.yaml (overrides defaults)."""
        domain_names = [d.name for d in test_config.domains]

        # Should include test-specific domains
        assert "example.com" in domain_names
        assert "arachne.dainst.org" in domain_names
        assert "*.dainst.org" in domain_names
        assert "default" in domain_names
        assert len(domain_names) == 4  # Only 4 test domains

    def test_domain_to_workflow_mapping(self, test_config):
        """Test that domain → workflow mappings work correctly."""
        domains = {d.name: d.workflow for d in test_config.domains}

        # Verify correct mappings from testing.yaml
        assert domains["example.com"] == "simple_workflow"
        assert domains["arachne.dainst.org"] == "archaeology_workflow"
        assert domains["*.dainst.org"] == "dainst_workflow"
        assert domains["default"] == "simple_workflow"

    def test_workflow_structure(self, test_config):
        """Test that workflows have correct structure."""
        # Get archaeology workflow
        archaeology = next(w for w in test_config.workflows if w.name == "archaeology_workflow")

        # Should have expected steps (test version has only 2 steps, no DOI)
        step_names = [s.name for s in archaeology.steps]
        assert "archive_generation" in step_names
        assert "metadata_extraction" in step_names
        assert len(step_names) == 2  # Test workflow simpler than production

        # Verify dependencies
        metadata_step = next(s for s in archaeology.steps if s.name == "metadata_extraction")
        assert "archive_generation" in metadata_step.depends_on

    def test_kafka_producer_config(self, test_config):
        """Test Kafka producer configuration from testing.yaml."""
        producer = test_config.transport.kafka.producer

        assert producer.acks == "all"
        assert producer.retries == 3

    def test_kafka_consumer_config(self, test_config):
        """Test Kafka consumer configuration from testing.yaml."""
        consumer = test_config.transport.kafka.consumer

        assert consumer.group_id == "civers-orchestrator-test-group"
        assert consumer.auto_offset_reset == "earliest"

    def test_orchestrator_can_be_initialized_with_config(self, test_config):
        """Test that orchestrator can be initialized with loaded config."""
        from orchestration_services import OrchestratorService

        # Should initialize without errors
        orchestrator = OrchestratorService(test_config)

        assert orchestrator is not None
        assert orchestrator.config == test_config

    def test_orchestrator_fixture_is_ready_to_use(self, orchestrator):
        """Test that orchestrator fixture works correctly."""
        # Orchestrator should be initialized and ready
        assert orchestrator is not None

        # Should be able to get workflow status (returns None for non-existent)
        status = orchestrator.get_workflow_status("non-existent-id")
        assert status is None

    def test_orchestrator_can_match_domains(self, orchestrator):
        """Test that orchestrator can match domains using config."""
        # Start workflow with arachne domain
        instruction = orchestrator.start_workflow(
            request_id="test-domain-match",
            url="https://arachne.dainst.org/entity/123"
        )

        # Should match archaeology_workflow
        state = orchestrator.get_workflow_state("test-domain-match")
        assert state.workflow_name == "archaeology_workflow"

    def test_transport_enabled_in_testing(self, test_config):
        """Test that Kafka transport is enabled in testing config."""
        assert "kafka" in test_config.transport.enabled


class TestConfigVsHardcodedComparison:
    """Compare loaded config with previously hardcoded values."""

    def test_port_matches_hardcoded_tests(self, test_config):
        """Verify port matches what integration tests used (29092 not 29093)."""
        # Previously hardcoded as localhost:29092 in many tests
        # testing.yaml was incorrectly set to 29093 - now fixed to 29092
        assert test_config.transport.kafka.bootstrap_servers == "localhost:29092"

    def test_all_component_mappings_present(self, test_config):
        """Verify all component mappings from hardcoded tests are present."""
        mappings = test_config.transport.kafka.component_mappings

        # All components that were hardcoded in tests
        assert "archive_generator" in mappings
        assert "metadata_extractor" in mappings
        assert "doi_service" in mappings

    def test_event_models_match_hardcoded(self, test_config):
        """Verify event model names match what was hardcoded."""
        archive = test_config.transport.kafka.component_mappings["archive_generator"]

        # Event model names should match hardcoded tests
        assert archive.event_models["request"] == "ArchiveRequestEvent"
        assert archive.event_models["success"] == "ArchiveCompletedEvent"
        assert archive.event_models["failure"] == "ArchiveFailedEvent"
