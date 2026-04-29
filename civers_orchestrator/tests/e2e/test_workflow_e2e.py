import asyncio
import pytest
import uuid

@pytest.mark.asyncio
async def test_archaeology_workflow_e2e(
    live_kafka_service, 
    create_mock_component, 
    e2e_test_driver,
    test_config
):
    """
    End-to-end test for the archaeology workflow.
    
    Flow:
    1. Start Mock Archive Generator
    2. Start Mock Metadata Extractor
    3. Publish request to orchestrator.requests
    4. Verify orchestrator routes to Archive Generator
    5. Mock Archive Generator responds
    6. Verify orchestrator routes to Metadata Extractor
    7. Mock Metadata Extractor responds
    8. Verify orchestrator publishes final completion event
    """
    # 1. Start mock components
    # They automatically listen and respond based on testing.yaml topics
    archive_gen = await create_mock_component("archive_generator")
    metadata_ext = await create_mock_component("metadata_extractor")
    
    # 2. Prepare test data
    request_id = f"e2e-test-{uuid.uuid4().hex[:8]}"
    url = "https://arachne.dainst.org/entity/12345"
    
    # 3. Submit request
    await e2e_test_driver.send_request(url, request_id)
    
    # 4. Wait for completion (via orchestrator.completed topic)
    # The mocks handle the intermediate steps automatically in their background loops
    result = await e2e_test_driver.wait_for_result(request_id, timeout=30)
    
    # 5. Verify results
    assert result["request_id"] == request_id
    assert result["workflow_name"] == "archaeology_workflow"
    
    # Results are grouped by step name
    results = result["step_results"]
    assert "archive_generation" in results
    assert "metadata_extraction" in results
    assert results["archive_generation"]["snapshot_id"] == f"snap-{request_id}"
    assert results["metadata_extraction"]["extracted_metadata"]["title"] == "Test Title"
    
    print(f"✅ E2E Test Passed for {request_id}")

@pytest.mark.asyncio
async def test_simple_workflow_e2e(
    live_kafka_service, 
    create_mock_component, 
    e2e_test_driver,
    test_config
):
    """Test a simple single-step workflow."""
    archive_gen = await create_mock_component("archive_generator")
    
    request_id = f"e2e-simple-{uuid.uuid4().hex[:8]}"
    url = "https://example.com/page"
    
    await e2e_test_driver.send_request(url, request_id)
    result = await e2e_test_driver.wait_for_result(request_id, timeout=15)
    
    assert result["request_id"] == request_id
    assert result["workflow_name"] == "simple_workflow"
    assert "archive_generation" in result["step_results"]
    assert result["step_results"]["archive_generation"]["snapshot_id"] == f"snap-{request_id}"
