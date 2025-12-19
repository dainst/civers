# Testing Framework

Comprehensive unit testing infrastructure for the CIVERS JSON-LD Metadata Extractor with focused test coverage for working components.

## Overview

The testing framework provides:

- **Unit Test Coverage**: Comprehensive testing of JSON-LD extraction and mapping
- **Rich Fixtures**: Pre-configured test data and domain configurations
- **Real-World Data**: Actual JSON-LD samples for realistic testing
- **Async Support**: Full asyncio testing capabilities for Kafka components
- **Coverage Reporting**: Code coverage analysis and reporting
- **Fast Execution**: Focused test suite runs quickly for development

## Test Organization

### Current Test Structure

```
tests/
├── conftest.py                     # Global fixtures and configuration
├── test_metadata_extractor/        # Unit test suite (ACTIVE)
│   ├── test_extractor_factory.py   # Factory registration and selection
│   ├── test_extractor_jsonld.py    # JSON-LD extractor tests
│   ├── test_html_parser.py         # HTML parsing utilities
│   ├── test_mapper_jsonld.py       # JSON-LD mapper tests
│   └── test_skipped_fields.py      # Field skipping logic
├── transport_services/             # Transport layer tests (ACTIVE)
│   ├── test_event_publisher.py     # Event publishing tests
│   ├── test_kafka_connection_manager.py  # Connection management
│   └── test_event_models.py        # Kafka event data models  
└── test_metadata_extraction_services/ # Service layer tests (ACTIVE)
    ├── test_metadata_extraction_service.py
    └── test_service_initialization.py
```

**Note**: Tests focus on the clean architecture with proper separation of concerns.

## Test Categories

### Unit Tests ✅ (Active)

**JSON-LD Extractor Tests** (`test_extractor_jsonld.py`):
- JSON-LD script discovery and parsing
- Hierarchical data flattening  
- Array processing with indexing
- Error handling and edge cases
- Performance benchmarks

**JSON-LD Mapper Tests** (`test_mapper_jsonld.py`):
- Configuration-driven mapping
- Array pattern processing (`[*]` syntax)
- DataCite model creation and validation
- Field skipping and error handling
- Complex nested structure mapping

**HTML Parser Tests** (`test_html_parser.py`):
- HTML parsing and validation
- JSON-LD script extraction
- Title and basic element extraction
- Error resilience testing

**Factory Tests** (`test_extractor_factory.py`):  
- Content analysis and detection
- Extractor/mapper pair creation
- Registration and configuration
- Fallback behavior testing

### Transport Service Tests ✅ (Active)

**Kafka Integration Tests**:
- Connection management and retry logic
- Event publishing and consumption
- Async workflow orchestration
- Error handling and recovery

**Event Model Tests**:
- Request/response serialization
- Validation and schema compliance
- Event routing and processing

## Running Tests

### Quick Test Runs

```bash
# Run all unit tests
pytest tests/test_metadata_extractor/ -v

# Run specific test modules
pytest tests/test_metadata_extractor/test_extractor_jsonld.py -v
pytest tests/test_metadata_extractor/test_mapper_jsonld.py -v

# Run with coverage
pytest tests/test_metadata_extractor/ --cov=metadata_extractors --cov-report=html

# Run transport service tests
pytest tests/transport_services/ -v
```

### Test Categories with Markers

```bash  
# Run unit tests only
pytest -m "unit" -v

# Run async tests
pytest -m "asyncio" -v

# Run performance tests  
pytest -m "performance" -v

# Skip slow tests
pytest -m "not slow" -v
```

### Comprehensive Coverage

```bash
# Full coverage report
pytest tests/ --cov=metadata_extractors --cov=transport_services --cov=metadata_extraction_services \
       --cov-report=html --cov-report=term

# View coverage report
open htmlcov/index.html
```

## Test Configuration

### Pytest Configuration (`pyproject.toml`)

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py", "*_test.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-v --tb=short --strict-markers"
markers = [
    "unit: Unit tests for individual components",
    "integration: Integration tests (currently disabled)",  
    "asyncio: Async/await tests",
    "performance: Performance benchmarks",
    "slow: Tests that take longer to run"
]
```

### Global Fixtures (`conftest.py`)

Key fixtures available across all tests:

```python  
@pytest.fixture
def arachne_real_data_mapping_config():
    """Real Arachne domain configuration for testing"""
    
@pytest.fixture  
def arachne_raw_json_data():
    """Actual JSON-LD data from arachne.dainst.org"""

@pytest.fixture
def test_data_builder():
    """Builder pattern for creating test data variations"""
```

## Current Test Status

### ✅ Working Tests (100% Pass Rate)

| Component | Test File | Tests | Status |
|-----------|-----------|-------|--------|
| **JSON-LD Extractor** | `test_extractor_jsonld.py` | 12 | ✅ All passing |
| **JSON-LD Mapper** | `test_mapper_jsonld.py` | 15 | ✅ All passing |
| **HTML Parser** | `test_html_parser.py` | 8 | ✅ All passing |
| **Factory** | `test_extractor_factory.py` | 6 | ✅ All passing |
| **Transport Services** | `test_kafka_*.py` | 25+ | ✅ All passing |

**Total Active Tests**: ~66 unit tests
**Success Rate**: 100%
**Avg Runtime**: <5 seconds

### 🔄 Placeholder Components

Stub extractors (CSS selectors, meta tags) have minimal testing:

```python
def test_meta_tags_extractor_returns_not_implemented():
    """Test that meta tags extractor properly returns NOT_IMPLEMENTED"""
    extractor = MetaTagsExtractor()
    result = extractor.extract("<html></html>", "https://example.com")
    
    assert result.status == ExtractionStatus.NOT_IMPLEMENTED
    assert "not yet implemented" in result.error_message
```

## Testing Best Practices

### Writing New Tests

1. **Use Existing Fixtures**: Leverage `conftest.py` fixtures for consistency
2. **Test Real Scenarios**: Use actual JSON-LD data samples  
3. **Cover Edge Cases**: Test error conditions and boundary cases
4. **Performance Awareness**: Include timing assertions for critical paths
5. **Clear Assertions**: Use descriptive assertion messages

### Example Test Structure

```python
def test_jsonld_extraction_with_complex_arrays(arachne_real_data):
    """Test JSON-LD extraction handles complex nested arrays correctly"""
    # Arrange
    extractor = JsonLDExtractor()
    html_content = arachne_real_data['complex_arrays_sample']
    
    # Act  
    result = extractor.extract(html_content, "https://test.example.org")
    
    # Assert
    assert result.status == ExtractionStatus.SUCCESS
    assert result.metadata_count > 10, "Should extract multiple fields"
    assert "author[0].name" in result.raw_data, "Should flatten array structures"
    assert result.processing_time_seconds < 0.1, "Should process quickly"
```

### Mock and Fixture Patterns

```python
@pytest.fixture
def mock_kafka_producer():
    """Mock Kafka producer for transport tests"""
    with patch('kafka.KafkaProducer') as mock:
        yield mock

def test_event_publishing_with_mock(mock_kafka_producer):
    """Test event publishing without real Kafka dependency"""
    # Test implementation using mock
```

## Test Data Management  

### Real-World Test Data

The test suite includes actual JSON-LD samples from:

- **Arachne Database**: Archaeological artifact metadata
- **Schema.org Examples**: Standard JSON-LD structures  
- **Edge Cases**: Malformed or complex structures

### Test Data Builder

```python
from tests.conftest import TestDataBuilder

def test_custom_json_ld_structure():
    """Test with custom JSON-LD structure"""
    builder = TestDataBuilder()
    json_ld = builder.create_article_jsonld(
        title="Test Article",
        authors=["Dr. Smith", "Dr. Jones"], 
        keywords=["test", "archaeology"]
    )
    
    # Test with generated data
    extractor = JsonLDExtractor()
    result = extractor.extract(json_ld, "https://example.com")
    # ... assertions
```

## Performance Testing

### Benchmarks

Current performance benchmarks in test suite:

```python
def test_jsonld_extraction_performance():
    """Ensure JSON-LD extraction meets performance requirements"""
    extractor = JsonLDExtractor()
    
    start_time = time.time()
    result = extractor.extract(large_jsonld_sample, url)
    processing_time = time.time() - start_time
    
    assert processing_time < 0.05, f"Processing too slow: {processing_time}s"
    assert result.metadata_count > 50, "Should extract many fields"
```

### Memory Usage

```python  
def test_memory_usage_within_bounds():
    """Ensure extraction doesn't consume excessive memory"""
    import psutil
    process = psutil.Process()
    
    initial_memory = process.memory_info().rss
    
    # Process large document
    extractor = JsonLDExtractor()
    result = extractor.extract(huge_jsonld_document, url)
    
    final_memory = process.memory_info().rss
    memory_increase = final_memory - initial_memory
    
    assert memory_increase < 50 * 1024 * 1024, "Memory usage too high"
```

## Continuous Integration

### GitHub Actions Integration

```yaml
# .github/workflows/tests.yml
name: Test Suite
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
    - name: Run tests
      run: pytest tests/ --cov --cov-report=xml
    - name: Upload coverage
      uses: codecov/codecov-action@v3
```

### Test Reports

The CI system generates:
- **Test Results**: Pass/fail status for each test
- **Coverage Reports**: Code coverage percentages  
- **Performance Metrics**: Execution time tracking
- **Regression Detection**: Performance regression alerts

## Future Testing

### Planned Test Enhancements

When CSS selector and meta tags extractors are implemented:

1. **New Test Modules**: 
   - `test_extractor_css_selectors.py`
   - `test_extractor_meta_tags.py`
   - `test_mapper_css_selectors.py` 
   - `test_mapper_meta_tags.py`

2. **Integration Test Revival**: 
   - End-to-end workflow testing
   - Multi-extractor scenarios
   - Cross-extractor consistency validation

3. **Advanced Test Scenarios**:
   - Fallback behavior testing
   - Performance comparison tests
   - Data quality validation

### Contributing to Tests

1. **Add Tests for New Features**: Every new feature needs comprehensive tests
2. **Maintain Coverage**: Keep test coverage above 90%
3. **Real-World Testing**: Include actual web content samples
4. **Performance Benchmarks**: Add timing assertions for new components
5. **Documentation**: Update this README when adding new test categories

See [DEVELOPMENT_ROADMAP.md](../DEVELOPMENT_ROADMAP.md) for planned testing enhancements.