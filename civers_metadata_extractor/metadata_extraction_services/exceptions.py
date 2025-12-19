"""
Workflow-specific exception classes for metadata extraction services.

These exceptions provide detailed error information and support for workflow-specific
error handling and recovery mechanisms.
"""


class WorkflowError(Exception):
    """Base class for workflow-related errors."""
    
    def __init__(self, message: str, stage: str = None, recoverable: bool = False):
        super().__init__(message)
        self.stage = stage
        self.recoverable = recoverable
        self.message = message


class URLValidationError(WorkflowError):
    """URL validation failed during workflow processing."""
    
    def __init__(self, message: str, url: str = None, **kwargs):
        super().__init__(message, stage="url_validation", **kwargs)
        self.url = url


class ContentFetchError(WorkflowError):
    """Content fetching failed during workflow processing."""
    
    def __init__(self, message: str, url: str = None, status_code: int = None, **kwargs):
        super().__init__(message, stage="content_preparation", recoverable=True, **kwargs)
        self.url = url
        self.status_code = status_code


class MetadataExtractionError(WorkflowError):
    """Metadata extraction failed during workflow processing."""
    
    def __init__(self, message: str, domain: str = None, mappers_attempted: list = None, **kwargs):
        super().__init__(message, stage="metadata_extraction", **kwargs)
        self.domain = domain
        self.mappers_attempted = mappers_attempted or []


class OutputGenerationError(WorkflowError):
    """Output file generation failed during workflow processing."""
    
    def __init__(self, message: str, output_path: str = None, **kwargs):
        super().__init__(message, stage="output_generation", recoverable=True, **kwargs)
        self.output_path = output_path


class ConfigurationError(WorkflowError):
    """Configuration-related error during workflow processing."""
    
    def __init__(self, message: str, config_key: str = None, **kwargs):
        super().__init__(message, stage="configuration", **kwargs)
        self.config_key = config_key


class ValidationError(WorkflowError):
    """Data validation error during workflow processing."""
    
    def __init__(self, message: str, field: str = None, value: str = None, **kwargs):
        super().__init__(message, stage="data_mapping", **kwargs)
        self.field = field
        self.value = value