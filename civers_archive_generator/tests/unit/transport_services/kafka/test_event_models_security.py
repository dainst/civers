import pytest
from pydantic import ValidationError
from transport_services.kafka.event_models import EventBaseModel

def test_request_id_hardened_validation():
    # Valid request IDs
    EventBaseModel(request_id="valid-id-123", url="http://example.com")
    EventBaseModel(request_id="simple_id", url="http://example.com")
    
    # Invalid request IDs (Path Traversal attempt)
    with pytest.raises(ValidationError) as excinfo:
        EventBaseModel(request_id="../../../etc/passwd", url="http://example.com")
    assert "request_id must contain only alphanumeric characters" in str(excinfo.value)
    
    # Invalid request IDs (Suspicious characters)
    with pytest.raises(ValidationError) as excinfo:
        EventBaseModel(request_id="id; drop table users", url="http://example.com")
    assert "request_id must contain only alphanumeric characters" in str(excinfo.value)

def test_url_hardened_validation():
    # Valid URLs
    EventBaseModel(request_id="test", url="http://example.com")
    EventBaseModel(request_id="test", url="https://sub.domain.org/path?q=1")
    
    # Invalid URLs (Not HTTP/HTTPS)
    with pytest.raises(ValidationError) as excinfo:
        EventBaseModel(request_id="test", url="ftp://example.com")
    assert "URL must be a valid http or https address" in str(excinfo.value)
    
    # Invalid URLs (Injection characters)
    with pytest.raises(ValidationError) as excinfo:
        EventBaseModel(request_id="test", url="http://example.com\n--bad-flag")
    assert any(msg in str(excinfo.value) for msg in ["URL contains prohibited characters", "URL must be a valid http or https address"])
    
    with pytest.raises(ValidationError) as excinfo:
        EventBaseModel(request_id="test", url="http://example.com?q=' OR 1=1")
    assert any(msg in str(excinfo.value) for msg in ["URL contains prohibited characters", "URL must be a valid http or https address"])
