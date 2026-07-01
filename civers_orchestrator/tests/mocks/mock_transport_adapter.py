"""Mock transport adapter for testing.

This mock adapter records all translation calls for verification,
allowing tests to verify the orchestrator calls the adapter correctly
without needing real Kafka configuration.

Usage:
    from tests.mocks.mock_transport_adapter import MockTransportAdapter

    # In test setup
    adapter = MockTransportAdapter()
    adapter.set_mock_mapping("archive_generator", {
        "request_destination": "archive.requests",
        "response_destinations": {
            "success": "archive.completed",
            "failure": "archive.failed"
        }
    })

    # In test
    orchestrator = OrchestratorService(config, adapter)
    instruction = orchestrator.start_workflow(...)

    # Verify
    assert len(adapter.translation_calls) == 1
    assert adapter.translation_calls[0].component == "archive_generator"
"""

from typing import Any


class MockTransportAdapter:
    """
    Mock adapter that records translation calls for verification.

    Use in orchestrator tests to verify it calls adapter correctly
    without needing real Kafka configuration.

    Attributes:
        translation_calls: List of all StepInstructions passed to translate_instruction()
        mock_mappings: Dict of configured component mappings
    """

    def __init__(self):
        """Initialize mock adapter with empty call history."""
        self.translation_calls: list[Any] = []
        self.mock_mappings: dict[str, dict[str, Any]] = {}

    def set_mock_mapping(self, component: str, mapping: dict[str, Any]):
        """
        Configure mock mapping for a component.

        Args:
            component: Component identifier
            mapping: Mock mapping configuration

        Example:
            >>> adapter.set_mock_mapping("archive_generator", {
            ...     "request_destination": "archive.requests",
            ...     "response_destinations": {
            ...         "success": "archive.completed",
            ...         "failure": "archive.failed"
            ...     },
            ...     "request_message_type": "ArchiveRequestEvent"
            ... })
        """
        self.mock_mappings[component] = mapping

    def get_request_destination(self, component: str) -> str:
        """
        Mock method - returns configured destination.

        Args:
            component: Component identifier

        Returns:
            Configured request destination or default

        Example:
            >>> adapter.set_mock_mapping("comp", {"request_destination": "test.topic"})
            >>> adapter.get_request_destination("comp")
            'test.topic'
        """
        mapping = self.mock_mappings.get(component, {})
        return mapping.get("request_destination", "mock.destination")

    def get_response_destinations(self, component: str) -> dict[str, str]:
        """
        Mock method - returns response destinations.

        Args:
            component: Component identifier

        Returns:
            Dict with success/failure destinations

        Example:
            >>> adapter.set_mock_mapping("comp", {
            ...     "response_destinations": {"success": "s", "failure": "f"}
            ... })
            >>> adapter.get_response_destinations("comp")
            {'success': 's', 'failure': 'f'}
        """
        mapping = self.mock_mappings.get(component, {})
        return mapping.get("response_destinations", {
            "success": "mock.success",
            "failure": "mock.failure"
        })

    def translate_instruction(self, instruction: Any) -> dict[str, Any]:
        """
        Mock translation - records call and returns mock operation.

        Tests can verify:
        - Orchestrator called translate_instruction
        - With correct instruction data

        Args:
            instruction: StepInstruction to translate

        Returns:
            Mock operation dict

        Example:
            >>> adapter = MockTransportAdapter()
            >>> adapter.set_mock_mapping("comp", {"request_destination": "test"})
            >>> instruction = create_transport_agnostic_instruction(component="comp")
            >>> result = adapter.translate_instruction(instruction)
            >>> assert len(adapter.translation_calls) == 1
            >>> assert result["destination"] == "test"
        """
        # Record call for verification
        self.translation_calls.append(instruction)

        # Get component mapping
        component = instruction.component
        mapping = self.mock_mappings.get(component, {})

        # Return mock operation dict
        return {
            "destination": mapping.get("request_destination", "mock.destination"),
            "message_type": mapping.get("request_message_type", "MockMessage"),
            "data": instruction.input_data,
            "request_id": instruction.request_id
        }

    def clear_calls(self):
        """Clear recorded translation calls (useful between tests)."""
        self.translation_calls.clear()
