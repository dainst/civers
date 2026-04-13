"""
Event models for archive request publishing.

These models define the structure of events published to Kafka for the 
archive request feature. They are designed to be compatible with the 
civers_orchestrator's event consumer.

Reference:
    civers_orchestrator/transport_services/kafka/event_models.py

Key Design Decisions:
    - Uses the same field structure as the orchestrator's OrchestratorRequestEvent
    - Auto-generates created_at in ISO 8601 UTC format
    - Includes validation for required fields
    - The orchestrator will consume these events from the 'orchestrator.requests' topic
"""

import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator, ConfigDict


class EventBaseModel(BaseModel):
    """Base model for all events.
    
    This mirrors the orchestrator's EventBaseModel to ensure compatibility.
    
    Following the CiVers pattern:
    - request_id: REQUIRED - unique identifier for tracking
    - created_at: Auto-generated ISO 8601 UTC timestamp
    - url: REQUIRED - the URL to be archived
    """
    model_config = ConfigDict(extra='ignore')
    
    request_id: str = Field(
        ..., 
        description="Unique identifier for the request (UUID recommended)"
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        description="Timestamp when the event was created, in ISO 8601 UTC format"
    )
    url: str = Field(
        ..., 
        description="The URL to be archived"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional request metadata"
    )

    @field_validator("request_id")
    @classmethod
    def validate_request_id(cls, v: str) -> str:
        """Validate request_id is not empty or whitespace."""
        if not v or v.strip() == "":
            raise ValueError("request_id cannot be empty")
        return v.strip()

    @field_validator("created_at", mode="before")
    @classmethod
    def validate_created_at_format(cls, v: Any) -> Any:
        """Validate created_at is in ISO 8601 UTC format if provided."""
        if isinstance(v, str):
            iso8601_utc_regex = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
            if not re.match(iso8601_utc_regex, v):
                raise ValueError(
                    "created_at must be in ISO 8601 UTC format (e.g. '2023-10-01T12:00:00Z')"
                )
        return v

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate url is not empty and has valid format."""
        if not v or v.strip() == "":
            raise ValueError("url cannot be empty")
        
        v = v.strip()
        
        # Basic URL format validation
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("url must start with http:// or https://")
        
        return v


class OrchestratorRequestEvent(EventBaseModel):
    """Event to request a new archive workflow from the orchestrator.
    
    This is the entry point event that triggers a workflow execution.
    The web interface publishes this event to the 'orchestrator.requests' topic.
    
    Field compatibility with civers_orchestrator/transport_services/kafka/event_models.py:
    - request_id: str (required) - Unique identifier
    - created_at: str - ISO 8601 UTC timestamp  
    - url: str (required) - URL to archive
    - priority: int - Processing priority 1-10 (default: 1)
    - callback_url: Optional[str] - Webhook URL for status updates
    - metadata: Dict[str, Any] - Additional metadata
    
    Example:
        >>> event = OrchestratorRequestEvent(
        ...     request_id="abc-123",
        ...     url="https://example.com/page",
        ...     callback_url="https://web-interface/api/webhook/status"
        ... )
        >>> event.model_dump()
        {
            'request_id': 'abc-123',
            'created_at': '2026-01-06T12:00:00Z',
            'url': 'https://example.com/page',
            'priority': 1,
            'callback_url': 'https://web-interface/api/webhook/status',
            'metadata': {}
        }
    """
    
    priority: int = Field(
        default=1,
        ge=1,
        le=10,
        description="Processing priority (1=low, 10=high). Default is 1."
    )
    callback_url: Optional[str] = Field(
        default=None,
        description="Optional webhook URL for push notifications (status updates, completion, failure)"
    )
    
    @field_validator("callback_url")
    @classmethod
    def validate_callback_url(cls, v: Optional[str]) -> Optional[str]:
        """Validate callback_url format if provided."""
        if v is None:
            return v
        
        v = v.strip()
        if not v:
            return None
            
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("callback_url must start with http:// or https://")
        
        return v


# Form submission model (for API request validation)
class ArchiveRequestForm(BaseModel):
    """Form data model for archive request submission.
    
    This model validates the form data submitted by the user before
    it's converted to an OrchestratorRequestEvent.
    
    Fields:
        url: The URL to archive (required)
        domain: The domain selected from dropdown (required for validation)
    """
    model_config = ConfigDict(extra='ignore')
    
    url: str = Field(
        ...,
        description="The URL to archive",
        min_length=10,
        max_length=2048
    )
    domain: str = Field(
        ...,
        description="The domain selected from the dropdown"
    )
    
    @field_validator("url")
    @classmethod
    def validate_url_format(cls, v: str) -> str:
        """Validate URL has proper format."""
        v = v.strip()
        if not v:
            raise ValueError("URL cannot be empty")
        
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("URL must start with http:// or https://")
        
        return v
    
    @field_validator("domain")
    @classmethod
    def validate_domain(cls, v: str) -> str:
        """Validate domain is not empty."""
        v = v.strip()
        if not v:
            raise ValueError("Domain cannot be empty")
        return v
