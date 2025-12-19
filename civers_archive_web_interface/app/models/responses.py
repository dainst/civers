"""
API response models for consistent response formatting.
"""

import json
from typing import Any, Dict, Generic, List, Optional, TypeVar
from pydantic import BaseModel, Field, ConfigDict

# Generic type for paginated data
T = TypeVar('T')


class ErrorDetail(BaseModel):
    """Detailed error information."""

    field: Optional[str] = Field(
        None,
        description="Field name that caused the error (if applicable)"
    )

    message: str = Field(
        ...,
        description="Human-readable error message"
    )

    code: Optional[str] = Field(
        None,
        description="Machine-readable error code"
    )

    def __str__(self) -> str:
        """String representation for fallback serialization."""
        if self.field:
            return f"{self.field}: {self.message}"
        return self.message

    def __json__(self):
        """Custom JSON serialization for FastAPI compatibility."""
        return self.model_dump()

    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return self.model_dump()


class ErrorResponse(BaseModel):
    """Standard error response format."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": False,
                "error": "Validation Error", 
                "message": "The provided data failed validation",
                "details": [
                    {
                        "field": "url_id",
                        "message": "url_id must contain only alphanumeric characters and underscores",
                        "code": "invalid_format"
                    }
                ]
            }
        }
    )
    
    success: bool = Field(
        False,
        description="Always false for error responses"
    )
    
    error: str = Field(
        ...,
        description="Brief error description"
    )
    
    message: str = Field(
        ...,
        description="Detailed error message"
    )
    
    details: Optional[List[ErrorDetail]] = Field(
        None,
        description="Additional error details (e.g., validation errors)"
    )
    
    request_id: Optional[str] = Field(
        None,
        description="Request ID for tracking and debugging"
    )


class SuccessResponse(BaseModel):
    """Standard success response format for simple operations."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Operation completed successfully",
                "data": {
                    "processed": 5,
                    "timestamp": "2024-03-15T14:30:22Z"
                }
            }
        }
    )
    
    success: bool = Field(
        True,
        description="Always true for success responses"
    )
    
    message: str = Field(
        ...,
        description="Success message"
    )
    
    data: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional response data"
    )


class PaginationMeta(BaseModel):
    """Pagination metadata."""
    
    page: int = Field(
        ...,
        description="Current page number (1-based)",
        ge=1
    )
    
    limit: int = Field(
        ..., 
        description="Number of items per page",
        ge=1,
        le=1000
    )
    
    total_count: int = Field(
        ...,
        description="Total number of items available",
        ge=0
    )
    
    total_pages: int = Field(
        ...,
        description="Total number of pages",
        ge=0
    )
    
    has_next: bool = Field(
        ...,
        description="Whether there is a next page"
    )
    
    has_previous: bool = Field(
        ...,
        description="Whether there is a previous page" 
    )
    
    @classmethod
    def create(cls, page: int, limit: int, total_count: int) -> 'PaginationMeta':
        """
        Create pagination metadata from basic parameters.
        
        Args:
            page: Current page number (1-based)
            limit: Items per page
            total_count: Total items available
            
        Returns:
            PaginationMeta object
        """
        total_pages = (total_count + limit - 1) // limit if total_count > 0 else 0
        has_next = page < total_pages
        has_previous = page > 1
        
        return cls(
            page=page,
            limit=limit,
            total_count=total_count,
            total_pages=total_pages,
            has_next=has_next,
            has_previous=has_previous
        )


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response format."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "data": [
                    {
                        "url_id": "example_com",
                        "original_url": "https://example.com",
                        "snapshot_count": 3
                    }
                ],
                "pagination": {
                    "page": 1,
                    "limit": 50,
                    "total_count": 150,
                    "total_pages": 3,
                    "has_next": True,
                    "has_previous": False
                }
            }
        }
    )
    
    success: bool = Field(
        True,
        description="Always true for success responses"
    )
    
    data: List[T] = Field(
        ...,
        description="List of items for current page"
    )
    
    pagination: PaginationMeta = Field(
        ...,
        description="Pagination metadata"
    )


class CitationResponse(BaseModel):
    """Response for citation generation."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "snapshot_id": "20240315T143022Z",
                "style": "APA",
                "citation": "Example Domain. (2024, March 15). Retrieved March 20, 2024, from https://example.com",
                "url": "https://example.com",
                "title": "Example Domain",
                "timestamp": "2024-03-15T14:30:22Z",
                "access_date": "2024-03-20T10:15:30Z"
            }
        }
    )
    
    success: bool = Field(
        True,
        description="Always true for success responses"
    )
    
    snapshot_id: str = Field(
        ...,
        description="ID of the snapshot being cited"
    )
    
    style: str = Field(
        ...,
        description="Citation style used (APA, MLA, Chicago)"
    )
    
    citation: str = Field(
        ...,
        description="Formatted citation text"
    )
    
    url: str = Field(
        ...,
        description="Original URL that was cited"
    )
    
    title: Optional[str] = Field(
        None,
        description="Title of the archived page"
    )
    
    timestamp: str = Field(
        ...,
        description="When the page was archived"
    )
    
    access_date: str = Field(
        ...,
        description="When the citation was generated"
    )


# Simple response types for single items
class ArchivedUrlResponse(BaseModel):
    """Response for single archived URL."""
    success: bool = Field(True)

class SnapshotResponse(BaseModel):
    """Response for single snapshot."""
    success: bool = Field(True) 

class ArtifactResponse(BaseModel):
    """Response for single artifact."""
    success: bool = Field(True)