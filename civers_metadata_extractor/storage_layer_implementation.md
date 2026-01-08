# Storage Layer Implementation Plan

## Executive Summary

This document outlines the design and implementation plan for a pluggable storage layer in the CIVERS Metadata Extractor. The storage layer will abstract file persistence operations, supporting **multiple storage backends simultaneously** including local filesystem storage (default) and cloud storage via CIVERS REST API uploads.

## Key Updates (Per User Requirements)

### ✅ Multi-Backend Support

- **Enable Multiple Backends**: Users can enable multiple storage backends at once
- **Configuration**: `storage.enabled: ["local_file", "civers_rest_api", "s3"]`
- **Simultaneous Storage**: Metadata is stored to ALL enabled backends in parallel
- **Graceful Degradation**: Service succeeds if ANY backend succeeds

### ✅ Specific Storage Naming

- **`civers_rest_api`**: Instead of generic `http_api` - specifically for CIVERS archive upload API
- **`local_file`**: Local filesystem storage (default, always available)
- **Future**: `s3`, `azure_blob`, `google_cloud_storage`, etc.

### ✅ Per-Backend Configuration

- Each backend has its own `enabled` flag in configuration
- Backend-specific settings under `storage.backends.{backend_name}`
- Easy to add new storage types without modifying existing code

### ✅ Extensibility via Registry Pattern

- New storage types registered via `StorageStrategyRegistry.register()`
- Plugin architecture - add new backends by implementing `StorageStrategy` interface
- No changes needed to core service layer when adding new storage types

---

## Current State Analysis

### Current Storage Implementation

**Location**: Hardcoded in `metadata_extraction_services/metadata_extraction_service.py`

**Current Implementation** (lines 377-461):

```python
async def _generate_json_output(
    self, 
    result: ExtractionResult,
    mapping_result: MappingResult,
    output_dir: str = "output/metadata"  # HARDCODED
) -> Optional[str]:
    # Hardcoded local file operations
    await aiofiles.os.makedirs(output_dir, exist_ok=True)
    
    # Hardcoded filename generation
    filename = f"metadata_{domain_name}_{result.request_id}_{timestamp}.json"
    filepath = os.path.join(output_dir, filename)
    
    # Hardcoded file write
    async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
        await f.write(json.dumps(output_data, ...))
    
    return filepath  # Returns local path
```

**Problems with Current Implementation**:

1. ❌ Storage logic coupled to business logic
2. ❌ No abstraction - can't switch storage backends
3. ❌ Hardcoded directory path (`output/metadata`)
4. ❌ No support for cloud storage or external APIs
5. ❌ Difficult to test (requires filesystem)
6. ❌ No configuration flexibility

---

## Upload API Analysis

**API Endpoint**: `POST http://localhost:8000/api/upload`

**Request Schema** (from OpenAPI spec):

```json
{
  "url": "string",              // Original URL being archived
  "request_id": "string",       // Unique request identifier  
  "allow_existing": false,      // Allow adding to existing snapshot
  "files": ["binary"]           // Archive files to upload (multipart/form-data)
}
```

**Response Schema**:

```json
{
  "success": true,
  "snapshot_id": "string",
  "url": "string",
  "artifacts_uploaded": ["string"],
  "message": "string"
}
```

**Supported File Types**:

- `archive.wacz` - WACZ archive
- `screenshot.png` - Screenshot image
- `singlefile.html` - SingleFile HTML
- `metadata.json` - Metadata JSON ← **OUR USE CASE**
- `document.html` - Document HTML

**Storage Structure**:

```
archives/{domain}/{path}/req_{request_id}_{timestamp}/
  ├── archive.wacz
  ├── screenshot.png
  ├── singlefile.html
  ├── metadata.json      ← We upload this
  └── document.html
```

---

## Design Decisions

### 1. Design Pattern: Strategy Pattern

**Why Strategy Pattern?**

- ✅ Allows runtime selection of storage backend
- ✅ Easy to add new storage backends without modifying existing code
- ✅ Clear separation between business logic and storage logic
- ✅ Each strategy is independently testable

**Pattern Structure**:

```
StorageStrategy (Interface)
    ↓
    ├── LocalFileStorageStrategy (Default)
    └── HttpApiStorageStrategy (Cloud Upload)
```

### 2. Configuration Strategy - Multi-Backend Support

**Updated `app_config.yaml` with Multiple Enabled Backends**:

```yaml
storage:
  # List of enabled storage backends (supports multiple simultaneously)
  enabled: ["local_file", "civers_rest_api"]  # Can enable multiple backends
  
  # Backend-specific configurations
  backends:
    # Local filesystem storage (always available, no dependencies)
    local_file:
      base_path: "output/metadata"
      create_subdirectories: true
      enabled: true  # Can be toggled independently
      
    # CIVERS REST API storage (requires httpx)
    civers_rest_api:
      upload_url: "http://localhost:8000/api/upload"
      timeout_seconds: 30
      retry_attempts: 3
      verify_ssl: true
      enabled: true  # Can be toggled independently
      # Optional authentication
      auth:
        enabled: false
        token: null
        type: "bearer"  # bearer, api_key, etc.
    
    # Future: S3 storage (example - not implemented yet)
    s3:
      enabled: false
      bucket: "civers-metadata"
      region: "eu-central-1"
      endpoint: null  # Optional for S3-compatible services
      credentials:
        access_key_id: "${AWS_ACCESS_KEY_ID}"  # Environment variable
        secret_access_key: "${AWS_SECRET_ACCESS_KEY}"
    
    # Future: Azure Blob storage (example - not implemented yet)
    azure_blob:
      enabled: false
      container_name: "metadata"
      connection_string: "${AZURE_STORAGE_CONNECTION_STRING}"
```

**Updated ConfigDataModel**:

```python
class StorageConfig(BaseModel):
    """Extensible storage configuration supporting multiple backends."""
    
    # List of currently enabled storage backends
    enabled: List[str] = ["local_file"]
    
    # Backend-specific configurations (extensible)
    backends: Dict[str, Dict[str, Any]] = {
        "local_file": {"base_path": "output/metadata", "enabled": True}
    }
    
    @model_validator(mode='after')
    def validate_enabled_backends(self):
        """Validate that enabled backends have configuration."""
        for backend_name in self.enabled:
            if backend_name not in self.backends:
                raise ValueError(
                    f"Backend '{backend_name}' is enabled but has no configuration. "
                    f"Available backends: {list(self.backends.keys())}"
                )
            
            backend_config = self.backends[backend_name]
            if not backend_config.get('enabled', True):
                raise ValueError(
                    f"Backend '{backend_name}' is in enabled list but marked as disabled in config"
                )
        
        return self
    
    def get_enabled_backends(self) -> List[str]:
        """Get list of enabled backend names."""
        return [
            name for name in self.enabled 
            if self.backends.get(name, {}).get('enabled', True)
        ]
    
    def is_backend_enabled(self, backend_name: str) -> bool:
        """Check if a specific backend is enabled."""
        return (
            backend_name in self.enabled and 
            self.backends.get(backend_name, {}).get('enabled', True)
        )
    
    def get_backend_config(self, backend: Optional[str] = None) -> Dict[str, Any]:
        """Get configuration for a specific backend."""
        if backend:
            return self.backends.get(backend, {})
        
        # Return first enabled backend config as default
        for backend_name in self.enabled:
            if self.backends.get(backend_name, {}).get('enabled', True):
                return self.backends[backend_name]
        
        return {}
```

✅ **Key Changes**:

- Support for multiple enabled backends simultaneously
- Each backend can be independently enabled/disabled
- Clear naming: `civers_rest_api` instead of generic `http_api`
- Easy to add new backend types without modifying existing code

---

## Architecture Design - Multi-Backend Support

### Component Hierarchy

```
┌─────────────────────────────────────────────────────┐
│     MetadataExtractionService                       │
│  (Business Logic Layer)                             │
│                                                      │
│  - Extracts metadata                                │
│  - Creates output data structure                    │
│  - Delegates storage to StorageManager              │
└──────────────┬──────────────────────────────────────┘
               │
               │ Uses
               ▼
┌─────────────────────────────────────────────────────┐
│     StorageManager                                   │
│  (Coordinator + Registry)                           │
│                                                      │
│  - Reads configuration                              │
│  - Manages multiple storage backends                │
│  - Stores to ALL enabled backends                   │
│  - Aggregates results from all backends             │
│  - Strategy registry for extensibility              │
└──────────────┬──────────────────────────────────────┘
               │
               │ Creates & Coordinates
               ▼
┌─────────────────────────────────────────────────────┐
│     StorageStrategy (Abstract Interface)            │
│                                                      │
│  + async store_metadata(data, metadata) -> result   │
│  + get_storage_type() -> str                        │
│  + is_available() -> bool                           │
└──────────────┬──────────────────────────────────────┘
               │
               │ Implemented by
               │
    ┌──────────┴────────────┬────────────────┐
    │                       │                │
    ▼                       ▼                ▼
┌──────────────┐  ┌──────────────────┐  ┌──────────┐
│ LocalFile    │  │ CiversRestApi    │  │ S3       │
│ Strategy     │  │ Strategy         │  │ Strategy │
│              │  │                  │  │          │
│ - SaveLocal  │  │ - POST upload    │  │ - S3 SDK │
│ - Return     │  │ - Return remote  │  │ - Return │
│   path       │  │   snapshot_id    │  │   S3 URI │
└──────────────┘  └──────────────────┘  └──────────┘
```

### Multi-Backend Storage Flow

```
1. MetadataExtractionService generates metadata
                ↓
2. Calls StorageManager.store_metadata()
                ↓
3. StorageManager identifies enabled backends: ["local_file", "civers_rest_api"]
                ↓
4. For each enabled backend:
   ├─→ Create strategy instance (if not cached)
   ├─→ Call strategy.store_metadata()
   └─→ Collect result
                ↓
5. Aggregate all results
   ├─→ local_file: Success → /path/to/file.json
   └─→ civers_rest_api: Success → snapshot_id: snap_123
                ↓
6. Return MultiStorageResult with all outcomes
```

### Strategy Registry Pattern

To make adding new storage types easier:

```python
# storage_layer/strategy_registry.py

class StorageStrategyRegistry:
    """Registry for storage strategy implementations."""
    
    _strategies: Dict[str, Type[StorageStrategy]] = {}
    
    @classmethod
    def register(cls, name: str, strategy_class: Type[StorageStrategy]):
        """Register a storage strategy."""
        cls._strategies[name] = strategy_class
    
    @classmethod
    def get_strategy_class(cls, name: str) -> Type[StorageStrategy]:
        """Get strategy class by name."""
        if name not in cls._strategies:
            raise ValueError(f"Unknown storage strategy: {name}")
        return cls._strategies[name]
    
    @classmethod
    def list_available(cls) -> List[str]:
        """List all registered strategy names."""
        return list(cls._strategies.keys())

# Register built-in strategies
StorageStrategyRegistry.register("local_file", LocalFileStorageStrategy)
StorageStrategyRegistry.register("civers_rest_api", CiversRestApiStorageStrategy)

# Future strategies can be registered by plugins/extensions
# StorageStrategyRegistry.register("s3", S3StorageStrategy)
```

---

## Implementation Plan

### Phase 1: Core Storage Abstraction (High Priority)

#### Step 1.1: Create Storage Strategy Interface

**File**: `storage_layer/storage_strategy.py`

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class StorageResult:
    """Result of a single storage operation"""
    success: bool
    storage_type: str  # "local_file", "civers_rest_api", "s3", etc.
    storage_location: Optional[str] = None  # Local path, URL, or resource ID
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)  # Additional info
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

@dataclass 
class MultiStorageResult:
    """Aggregated result from multiple storage backends"""
    overall_success: bool  # True if AT LEAST ONE backend succeeded
    results: List[StorageResult]  # Individual backend results
    primary_location: Optional[str] = None  # Primary storage location (usually local_file)
    
    def get_result_by_type(self, storage_type: str) -> Optional[StorageResult]:
        """Get result for a specific storage backend"""
        for result in self.results:
            if result.storage_type == storage_type:
                return result
        return None
    
    def get_successful_backends(self) -> List[str]:
        """Get list of storage types that succeeded"""
        return [r.storage_type for r in self.results if r.success]
    
    def get_failed_backends(self) -> List[str]:
        """Get list of storage types that failed"""
        return [r.storage_type for r in self.results if not r.success]

class StorageStrategy(ABC):
    """Abstract interface for storage strategies"""
    
    @abstractmethod
    async def store_metadata(
        self,
        data: Dict[str, Any],
        request_id: str,
        url: str,
        filename: str
    ) -> StorageResult:
        """
        Store metadata JSON.
        
        Args:
            data: Metadata dictionary to store
            request_id: Request ID for tracking
            url: Original URL being processed
            filename: Suggested filename
            
        Returns:
            StorageResult with success status and location
        """
        pass
    
    @abstractmethod
    def get_storage_type(self) -> str:
        """Return the storage strategy type identifier"""
        pass
    
    @abstractmethod
    async def is_available(self) -> bool:
        """
        Check if this storage backend is available and ready.
        
        Returns:
            True if backend is available, False otherwise
        """
        pass
```

#### Step 1.2: Implement Local File Strategy (Default)

**File**: `storage_layer/local_file_storage_strategy.py`

```python
import os
import json
import aiofiles
import aiofiles.os
from datetime import datetime
from typing import Dict, Any
from configs.logging_config import get_logger
from .storage_strategy import StorageStrategy, StorageResult

class LocalFileStorageStrategy(StorageStrategy):
    """Local filesystem storage strategy (default, always available)"""
    
    def __init__(self, base_path: str = "output/metadata", create_subdirectories: bool = True):
        self.base_path = base_path
        self.create_subdirectories = create_subdirectories
        self.logger = get_logger(__name__)
    
    async def store_metadata(
        self,
        data: Dict[str, Any],
        request_id: str,
        url: str,
        filename: str
    ) -> StorageResult:
        """Store metadata to local filesystem"""
        try:
            # Ensure output directory exists
            await aiofiles.os.makedirs(self.base_path, exist_ok=True)
            
            # Generate filepath
            filepath = os.path.join(self.base_path, filename)
            
            # Write JSON file
            async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(data, indent=2, ensure_ascii=False, default=str))
            
            file_size = len(json.dumps(data))
            self.logger.info(f"✅ Stored metadata locally: {filepath} ({file_size} bytes)")
            
            return StorageResult(
                success=True,
                storage_type="local_file",
                storage_location=filepath,
                metadata={
                    "filepath": filepath,
                    "size_bytes": file_size,
                    "base_path": self.base_path
                }
            )
            
        except Exception as e:
            self.logger.error(f"❌ Failed to store metadata locally: {e}")
            return StorageResult(
                success=False,
                storage_type="local_file",
                error_message=str(e)
            )
    
    def get_storage_type(self) -> str:
        return "local_file"
    
    async def is_available(self) -> bool:
        """Local file storage is always available"""
        try:
            # Check if we can write to the base path
            await aiofiles.os.makedirs(self.base_path, exist_ok=True)
            return True
        except Exception as e:
            self.logger.warning(f"Local file storage not available: {e}")
            return False
```

#### Step 1.3: Implement CIVERS REST API Strategy

**File**: `storage_layer/civers_rest_api_storage_strategy.py`

```python
import json
from typing import Dict, Any
from configs.logging_config import get_logger
from .storage_strategy import StorageStrategy, StorageResult

# Conditional import for HTTP functionality
try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    import warnings
    warnings.warn("httpx not available - CIVERS REST API storage disabled")

class CiversRestApiStorageStrategy(StorageStrategy):
    """CIVERS REST API storage strategy for cloud uploads"""
    
    def __init__(
        self,
        upload_url: str,
        timeout_seconds: int = 30,
        retry_attempts: int = 3,
        verify_ssl: bool = True,
        auth: Dict[str, Any] = None
    ):
        if not HTTPX_AVAILABLE:
            raise ImportError("httpx required for CIVERS REST API storage. Install with: uv sync --extra http")
        
        self.upload_url = upload_url
        self.timeout_seconds = timeout_seconds
        self.retry_attempts = retry_attempts
        self.verify_ssl = verify_ssl
        self.auth = auth or {}
        self.logger = get_logger(__name__)
    
    async def store_metadata(
        self,
        data: Dict[str, Any],
        request_id: str,
        url: str,
        filename: str
    ) -> StorageResult:
        """Upload metadata to CIVERS REST API"""
        try:
            # Convert metadata dict to JSON bytes
            json_content = json.dumps(data, indent=2, ensure_ascii=False, default=str)
            json_bytes = json_content.encode('utf-8')
            
            # Prepare multipart form data
            # Use 'metadata.json' as the artifact type name
            files = {
                'files': ('metadata.json', json_bytes, 'application/json')
            }
            
            form_data = {
                'url': url,
                'request_id': request_id,
                'allow_existing': 'true'  # Allow adding to existing snapshots
            }
            
            # Prepare headers
            headers = {}
            if self.auth.get('enabled'):
                auth_type = self.auth.get('type', 'bearer')
                token = self.auth.get('token')
                if auth_type.lower() == 'bearer':
                    headers['Authorization'] = f'Bearer {token}'
                elif auth_type.lower() == 'api_key':
                    headers['X-API-Key'] = token
            
            # Upload with retries
            for attempt in range(1, self.retry_attempts + 1):
                try:
                    self.logger.info(
                        f"📤 Uploading metadata to CIVERS API (attempt {attempt}/{self.retry_attempts})"
                    )
                    
                    async with httpx.AsyncClient(
                        timeout=self.timeout_seconds,
                        verify=self.verify_ssl
                    ) as client:
                        response = await client.post(
                            self.upload_url,
                            data=form_data,
                            files=files,
                            headers=headers
                        )
                        response.raise_for_status()
                        
                        # Parse response
                        result_data = response.json()
                        
                        self.logger.info(f"✅ {result_data.get('message', 'Upload successful')}")
                        
                        return StorageResult(
                            success=True,
                            storage_type="civers_rest_api",
                            storage_location=result_data.get('snapshot_id'),
                            metadata={
                                "snapshot_id": result_data.get('snapshot_id'),
                                "artifacts_uploaded": result_data.get('artifacts_uploaded'),
                                "upload_url": self.upload_url,
                                "size_bytes": len(json_bytes)
                            }
                        )
                        
                except httpx.HTTPStatusError as e:
                    self.logger.warning(
                        f"Upload attempt {attempt} failed: HTTP {e.response.status_code}"
                    )
                    if attempt == self.retry_attempts:
                        raise
                    
                except httpx.RequestError as e:
                    self.logger.warning(f"Upload attempt {attempt} failed: {e}")
                    if attempt == self.retry_attempts:
                        raise
            
        except Exception as e:
            self.logger.error(f"❌ Failed to upload metadata via CIVERS REST API: {e}")
            return StorageResult(
                success=False,
                storage_type="civers_rest_api",
                error_message=str(e)
            )
    
    def get_storage_type(self) -> str:
        return "civers_rest_api"
    
    async def is_available(self) -> bool:
        """Check if CIVERS REST API is available"""
        if not HTTPX_AVAILABLE:
            return False
        
        try:
            # Simple health check - try to connect to the API
            async with httpx.AsyncClient(timeout=5.0, verify=self.verify_ssl) as client:
                # Try OPTIONS or HEAD request to check if endpoint exists
                response = await client.request("OPTIONS", self.upload_url)
                return response.status_code < 500  # 4xx is ok, 5xx is not
        except Exception as e:
            self.logger.debug(f"CIVERS REST API not available: {e}")
            return False
```

#### Step 1.4: Create Strategy Registry

**File**: `storage_layer/strategy_registry.py`

```python
from typing import Dict, Type
from .storage_strategy import StorageStrategy

class StorageStrategyRegistry:
    """
    Registry for storage strategy implementations.
    
    Makes it easy to add new storage backends without modifying existing code.
    """
    
    _strategies: Dict[str, Type[StorageStrategy]] = {}
    
    @classmethod
    def register(cls, name: str, strategy_class: Type[StorageStrategy]):
        """
        Register a storage strategy implementation.
        
        Args:
            name: Unique identifier for the strategy (e.g., "local_file", "civers_rest_api")
            strategy_class: StorageStrategy implementation class
        """
        cls._strategies[name] = strategy_class
    
    @classmethod
    def get_strategy_class(cls, name: str) -> Type[StorageStrategy]:
        """
        Get strategy class by name.
        
        Args:
            name: Strategy identifier
            
        Returns:
            StorageStrategy class
            
        Raises:
            ValueError: If strategy name is not registered
        """
        if name not in cls._strategies:
            available = cls.list_available()
            raise ValueError(
                f"Unknown storage strategy: '{name}'. "
                f"Available strategies: {available}"
            )
        return cls._strategies[name]
    
    @classmethod
    def list_available(cls) -> list[str]:
        """List all registered strategy names"""
        return list(cls._strategies.keys())
    
    @classmethod
    def is_registered(cls, name: str) -> bool:
        """Check if a strategy is registered"""
        return name in cls._strategies
```

**Registration in `__init__.py`**:

```python
# storage_layer/__init__.py
from .strategy_registry import StorageStrategyRegistry
from .local_file_storage_strategy import LocalFileStorageStrategy
from .civers_rest_api_storage_strategy import CiversRestApiStorageStrategy

# Register built-in strategies
StorageStrategyRegistry.register("local_file", LocalFileStorageStrategy)
StorageStrategyRegistry.register("civers_rest_api", CiversRestApiStorageStrategy)

# Future strategies can be registered here or by plugins:
# try:
#     from .s3_storage_strategy import S3StorageStrategy
#     StorageStrategyRegistry.register("s3", S3StorageStrategy)
# except ImportError:
#     pass  # S3 support not installed
```

#### Step 1.5: Create Storage Manager (Multi-Backend Coordinator)

**File**: `storage_layer/storage_manager.py`

```python
from typing import Dict, Any, List
from configs.models import StorageConfig
from configs.logging_config import get_logger
from .storage_strategy import StorageStrategy, StorageResult, MultiStorageResult
from .strategy_registry import StorageStrategyRegistry

class StorageManager:
    """
    Multi-backend storage coordinator.
    
    - Manages multiple storage backends simultaneously
    - Stores to ALL enabled backends
    - Aggregates results from all backends
    - Uses strategy registry for extensibility
    """
    
    def __init__(self, storage_config: StorageConfig):
        self.storage_config = storage_config
        self.logger = get_logger(__name__)
        self.strategies: Dict[str, StorageStrategy] = {}
        
        # Initialize all enabled strategies
        self._initialize_strategies()
    
    def _initialize_strategies(self):
        """Initialize storage strategies for all enabled backends"""
        enabled_backends = self.storage_config.get_enabled_backends()
        
        self.logger.info(f"Initializing storage backends: {enabled_backends}")
        
        for backend_name in enabled_backends:
            try:
                # Get backend configuration
                backend_config = self.storage_config.get_backend_config(backend_name)
                
                # Get strategy class from registry
                strategy_class = StorageStrategyRegistry.get_strategy_class(backend_name)
                
                # Create strategy instance with backend-specific config
                strategy = self._create_strategy_instance(
                    strategy_class, 
                    backend_name, 
                    backend_config
                )
                
                self.strategies[backend_name] = strategy
                self.logger.info(f"✅ Initialized storage backend: {backend_name}")
                
            except Exception as e:
                self.logger.error(f"❌ Failed to initialize storage backend '{backend_name}': {e}")
                # Continue with other backends even if one fails
    
    def _create_strategy_instance(
        self, 
        strategy_class: type, 
        backend_name: str,
        config: Dict[str, Any]
    ) -> StorageStrategy:
        """
        Create strategy instance with backend-specific configuration.
        
        Args:
            strategy_class: Strategy class to instantiate
            backend_name: Backend identifier
            config: Backend configuration dict
            
        Returns:
            Initialized StorageStrategy instance
        """
        # Map configuration keys to constructor parameters
        if backend_name == "local_file":
            return strategy_class(
                base_path=config.get("base_path", "output/metadata"),
                create_subdirectories=config.get("create_subdirectories", True)
            )
        
        elif backend_name == "civers_rest_api":
            return strategy_class(
                upload_url=config["upload_url"],
                timeout_seconds=config.get("timeout_seconds", 30),
                retry_attempts=config.get("retry_attempts", 3),
                verify_ssl=config.get("verify_ssl", True),
                auth=config.get("auth", {})
            )
        
        # Future backends can be added here
        # elif backend_name == "s3":
        #     return strategy_class(
        #         bucket=config["bucket"],
        #         region=config.get("region"),
        #         ...
        #     )
        
        else:
            # Fallback: try to instantiate with config dict
            return strategy_class(**config)
    
    async def store_metadata(
        self,
        data: Dict[str, Any],
        request_id: str,
        url: str,
        filename: str
    ) -> MultiStorageResult:
        """
        Store metadata using ALL enabled storage backends.
        
        Args:
            data: Metadata dictionary
            request_id: Request ID
            url: Original URL
            filename: Suggested filename
            
        Returns:
            MultiStorageResult with aggregated outcomes from all backends
        """
        results: List[StorageResult] = []
        
        self.logger.info(f"Storing metadata to {len(self.strategies)} backend(s): {list(self.strategies.keys())}")
        
        # Store to each enabled backend
        for backend_name, strategy in self.strategies.items():
            try:
                # Check if backend is available
                is_available = await strategy.is_available()
                if not is_available:
                    self.logger.warning(f"⚠️  Backend '{backend_name}' is not available, skipping")
                    results.append(StorageResult(
                        success=False,
                        storage_type=backend_name,
                        error_message="Backend not available"
                    ))
                    continue
                
                # Store metadata
                self.logger.debug(f"Storing to {backend_name}...")
                result = await strategy.store_metadata(data, request_id, url, filename)
                results.append(result)
                
                if result.success:
                    self.logger.info(f"✅ {backend_name}: {result.storage_location}")
                else:
                    self.logger.error(f"❌ {backend_name}: {result.error_message}")
                    
            except Exception as e:
                self.logger.error(f"❌ Unexpected error storing to '{backend_name}': {e}")
                results.append(StorageResult(
                    success=False,
                    storage_type=backend_name,
                    error_message=str(e)
                ))
        
        # Aggregate results
        successful_backends = [r for r in results if r.success]
        overall_success = len(successful_backends) > 0
        
        # Use local_file as primary location if available, otherwise first successful
        primary_location = None
        for result in results:
            if result.success:
                if result.storage_type == "local_file":
                    primary_location = result.storage_location
                    break
                elif primary_location is None:
                    primary_location = result.storage_location
        
        multi_result = MultiStorageResult(
            overall_success=overall_success,
            results=results,
            primary_location=primary_location
        )
        
        # Log summary
        if overall_success:
            successful = multi_result.get_successful_backends()
            self.logger.info(f"✅ Metadata stored successfully to: {successful}")
        else:
            self.logger.error(f"❌ All storage backends failed")
        
        if multi_result.get_failed_backends():
            failed = multi_result.get_failed_backends()
            self.logger.warning(f"⚠️  Failed backends: {failed}")
        
        return multi_result
    
    def get_enabled_backends(self) -> List[str]:
        """Get list of enabled backend names"""
        return list(self.strategies.keys())
    
    def get_backend_strategy(self, backend_name: str) -> StorageStrategy:
        """Get strategy instance for a specific backend"""
        return self.strategies.get(backend_name)
```

### Phase 2: Integration (Medium Priority)

#### Step 2.1: Update MetadataExtractionService

**File**: `metadata_extraction_services/metadata_extraction_service.py`

**Changes**:

```python
# Add import
from storage_layer.storage_manager import StorageManager

class MetadataExtractionService:
    def __init__(self, config_data_model: ConfigDataModel):
        # ... existing code ...
        
        # Initialize storage manager
        storage_config = config_data_model.app.get_storage_config()
        self.storage_manager = StorageManager(storage_config)
        self.logger.info(f"Storage backend: {self.storage_manager.get_storage_type()}")
    
    async def _generate_json_output(
        self, 
        result: ExtractionResult,
        mapping_result: MappingResult
    ) -> Optional[str]:
        """
        Generate and store metadata output using storage manager.
        """
        try:
            # Generate filename (keep existing logic)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            domain_name = result.domain_used.replace('.', '_') if result.domain_used else 'unknown'
            filename = f"metadata_{domain_name}_{result.request_id}_{timestamp}.json"
            
            # Prepare output data (keep existing logic)
            output_data = {
                "metadata_extraction_result": {...},
                "intermediate_metadata": {...},
                ...
            }
            
            # CHANGED: Use storage manager instead of direct file write
            storage_result = await self.storage_manager.store_metadata(
                data=output_data,
                request_id=result.request_id,
                url=getattr(result, 'source_url', 'unknown'),  # Need to track this
                filename=filename
            )
            
            if storage_result.success:
                self.logger.info(f"Metadata stored: {storage_result.storage_location}")
                return storage_result.storage_location
            else:
                self.logger.error(f"Storage failed: {storage_result.error_message}")
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to generate/store JSON output: {e}")
            return None
```

**Note**: Need to track `source_url` in ExtractionResult for HTTP API uploads.

#### Step 2.2: Update ExtractionResult Model

**File**: `metadata_extraction_services/extraction_result.py`

```python
@dataclass
class ExtractionResult:
    # ... existing fields ...
    source_url: Optional[str] = None  # ADD: Track original URL for uploads
```

#### Step 2.3: Update Kafka Event Models (Optional)

**File**: `transport_services/kafka/event_models.py`

```python
class MetadataExtractionCompletedEvent(BaseModel):
    # ... existing fields ...
    storage_type: Optional[str] = Field(None, description="Storage backend used (local_file, http_api)")
    storage_location: Optional[str] = Field(None, description="Storage location (path or URL)")
```

### Phase 3: Configuration Updates (Low Priority)

#### Step 3.1: Update app_config.yaml.example

```yaml
storage:
  backend: "local_file"  # Options: "local_file", "http_api"
  backends:
    # Local file storage (default)
    local_file:
      base_path: "output/metadata"
    
    # HTTP API storage (cloud upload)
    http_api:
      upload_url: "http://localhost:8000/api/upload"
      timeout_seconds: 30
      retry_attempts: 3
      verify_ssl: true
      # Optional authentication
      auth_enabled: false
      auth_token: null
```

#### Step 3.2: Update README.md

Add storage configuration section explaining both backends.

---

## File Structure

```
civers_metadata_extractor/
├── storage_layer/                          # NEW: Storage abstraction layer
│   ├── __init__.py                         # Strategy registry initialization
│   ├── storage_strategy.py                 # Abstract interface + result models
│   ├── strategy_registry.py                # Strategy registry for extensibility
│   ├── storage_manager.py                  # Multi-backend coordinator
│   ├── local_file_storage_strategy.py      # Local filesystem implementation
│   └── civers_rest_api_storage_strategy.py # CIVERS REST API implementation
├── metadata_extraction_services/
│   └── metadata_extraction_service.py      # MODIFIED: Use StorageManager
├── configs/
│   └── config_data_model.py                # MODIFIED: StorageConfig enhancements
└── app_config.yaml                          # MODIFIED: Multi-backend storage config
```

---

## Benefits

### Immediate Benefits

1. ✅ **Multi-Backend Support** - Store to multiple backends simultaneously
2. ✅ **Clean separation of concerns** - Storage logic isolated from business logic
3. ✅ **Highly testable** - Easy to mock/test each strategy independently
4. ✅ **Maintainable** - Changes to storage don't affect extraction logic
5. ✅ **Flexible configuration** - Enable/disable backends via YAML
6. ✅ **Graceful degradation** - Service continues if some backends fail

### Extensibility Benefits

1. 🚀 **Plugin architecture** - Add new backends without modifying existing code
2. 🚀 **Registry pattern** - `StorageStrategyRegistry.register("new_backend", NewStrategy)`
3. 🚀 **Easy to add**:
   - S3 storage: Just implement strategy and register
   - Azure Blob: Just implement strategy and register
   - Google Cloud Storage: Just implement strategy and register
   - Custom backends: Just implement strategy and register

### Operational Benefits

1. 📊 **Per-backend metrics** - Track success/failure rates for each backend
2. 📊 **Redundancy** - Data stored in multiple locations automatically
3. 📊 **Health monitoring** - `is_available()` checks for each backend
4. 📊 **Selective failures** - Service succeeds if ANY backend succeeds

### Example Extension: Adding S3 Support

```python
# 1. Implement strategy (storage_layer/s3_storage_strategy.py)
class S3StorageStrategy(StorageStrategy):
    def __init__(self, bucket, region, credentials):
        self.bucket = bucket
        # ... initialize boto3 client

# 2. Register in __init__.py
from .s3_storage_strategy import S3StorageStrategy
StorageStrategyRegistry.register("s3", S3StorageStrategy)

# 3. Add config in app_config.yaml
storage:
  enabled: ["local_file", "civers_rest_api", "s3"]
  backends:
    s3:
      enabled: true
      bucket: "civers-metadata"
      region: "eu-central-1"

# Done! No changes needed to StorageManager or service layer
```

---

## Testing Strategy

### Unit Tests

**File**: `tests/storage_layer/test_local_file_storage.py`

```python
@pytest.mark.asyncio
async def test_local_file_storage_success():
    """Test successful local file storage"""
    strategy = LocalFileStorageStrategy(base_path="test_output")
    result = await strategy.store_metadata(
        data={"test": "data"},
        request_id="test_123",
        url="https://example.com",
        filename="test_metadata.json"
    )
    assert result.success is True
    assert os.path.exists(result.storage_location)
```

**File**: `tests/storage_layer/test_http_api_storage.py`

```python
@pytest.mark.asyncio
@pytest.mark.skipif(not HTTPX_AVAILABLE, reason="httpx not installed")
async def test_http_api_storage_success(httpx_mock):
    """Test successful HTTP API upload"""
    httpx_mock.add_response(
        method="POST",
        url="http://test.com/upload",
        json={"success": True, "snapshot_id": "snap_123"}
    )
    
    strategy = HttpApiStorageStrategy(upload_url="http://test.com/upload")
    result = await strategy.store_metadata(...)
    assert result.success is True
```

**File**: `tests/storage_layer/test_storage_manager.py`

```python
def test_storage_manager_creates_correct_strategy():
    """Test strategy selection based on configuration"""
    # Test local file
    config = StorageConfig(backend="local_file", ...)
    manager = StorageManager(config)
    assert manager.get_storage_type() == "local_file"
    
    # Test HTTP API
    config = StorageConfig(backend="http_api", ...)
    manager = StorageManager(config)
    assert manager.get_storage_type() == "http_api"
```

### Integration Tests

**File**: `tests/integration/test_metadata_extraction_with_storage.py`

```python
@pytest.mark.asyncio
async def test_extraction_with_local_storage():
    """Test end-to-end extraction with local storage"""
    # Setup service with local storage config
    # Run extraction
    # Verify file created locally

@pytest.mark.asyncio
async def test_extraction_with_http_storage(storage_api_mock):
    """Test end-to-end extraction with HTTP upload"""
    # Setup service with HTTP storage config
    # Mock HTTP upload endpoint
    # Run extraction
    # Verify upload was called with correct data
```

---

## Migration Strategy

### Phase 1: Implement Storage Layer (Week 1)

1. Create storage_layer directory
2. Implement StorageStrategy interface
3. Implement LocalFileStorageStrategy (1:1 replacement of current logic)
4. Write unit tests for local storage

### Phase 2: Add HTTP API Support (Week 2)

1. Implement HttpApiStorageStrategy
2. Write unit tests with mocked HTTP
3. Integration tests with test API

### Phase 3: Service Integration (Week 3)

1. Update MetadataExtractionService to use StorageManager
2. Update ExtractionResult model
3. Update configuration examples
4. Update documentation

### Phase 4: Testing & Validation (Week 4)

1. Full integration testing
2. Performance testing (local vs HTTP)
3. Error handling validation
4. Documentation review

---

## Backward Compatibility

✅ **Default behavior unchanged**: `backend: "local_file"` maintains current functionality
✅ **No breaking changes**: Existing code continues to work
✅ **Optional HTTP**: `httpx` remains optional dependency (--extra http)
✅ **Configuration compatible**: StorageConfig already exists in config model

---

## Benefits

### Immediate Benefits

1. ✅ **Clean separation of concerns** - Storage logic isolated
2. ✅ **Testable** - Easy to mock/test each strategy
3. ✅ **Maintainable** - Changes to storage don't affect business logic
4. ✅ **Flexible** - Easy configuration switching

### Future Benefits

1. 🚀 **Extensible** - Add S3, Azure, GCS strategies easily
2. 🚀 **Scalable** - Support for distributed storage
3. 🚀 **Observable** - Metrics per storage backend
4. 🚀 **Resilient** - Retry logic, fallback strategies

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| HTTP API unavailable | Upload failures | Implement retry logic, fallback to local |
| Network latency | Slower processing | Async operations, timeout configuration |
| Breaking changes to upload API | Integration breaks | Version API, graceful degradation |
| Configuration errors | Service won't start | Validation at startup, clear error messages |

---

## Future Enhancements

### Post-MVP Features

1. **Hybrid Strategy**: Store locally AND upload to cloud
2. **Fallback Strategy**: Try HTTP, fallback to local on failure
3. **S3 Strategy**: Direct S3 uploads (no HTTP API)
4. **Compression**: Compress JSON before upload
5. **Batch Uploads**: Queue and batch multiple uploads
6. **Monitoring**: Metrics for storage operations

---

## Success Criteria

### Phase 1 (Core Implementation)

- [ ] All existing functionality works with LocalFileStorageStrategy
- [ ] Unit tests achieve >90% coverage
- [ ] Zero breaking changes to existing APIs

### Phase 2 (HTTP API)

- [ ] Successful upload to test HTTP API
- [ ] Proper error handling and retries
- [ ] Integration tests passing

### Phase 3 (Production Ready)

- [ ] Documentation complete
- [ ] Configuration examples provided
- [ ] Performance acceptable (<100ms overhead)
- [ ] All tests passing

---

## Conclusion

This storage layer implementation provides a clean, extensible architecture for managing metadata persistence. The Strategy pattern allows seamless switching between local and cloud storage while maintaining backward compatibility. The implementation follows SOLID principles and provides a foundation for future storage enhancements.

**Recommended approach**: Incremental implementation starting with Phase 1 (local strategy) to ensure no regression, then adding HTTP API support in Phase 2.
