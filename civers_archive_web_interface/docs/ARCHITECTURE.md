# Civers Web Interface - System Architecture Documentation

## System Overview

The Civers Web Interface is a FastAPI-based web application designed for browsing and replaying archived versions of websites. The system uses a modular architecture with clear separation between different parts: storage, API, presentation, and configuration layers. It includes proper error handling and extensible design patterns.

### Core Design Philosophy

- **Separation of Concerns**: Clean boundaries between storage, API, presentation, and configuration layers
- **Dependency Injection**: Central state management through FastAPI's application state
- **Configuration-Driven**: YAML-based configuration with environment variable overrides
- **Provider Pattern**: Extensible storage architecture supporting multiple backends
- **Middleware Pipeline**: Layered request processing with specialized error handling
- **Type Safety**: Pydantic models throughout the system for data validation

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend Layer                           │
├─────────────────────────────────────────────────────────────────┤
│  Jinja2 Templates + Alpine.js + Tailwind CSS + Design System   │
│  • Mobile-first responsive design                              │
│  • Component-based architecture                                │
│  • Progressive enhancement                                      │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Middleware Pipeline                        │
├─────────────────────────────────────────────────────────────────┤
│  CorrelationIdMiddleware → SecurityHeadersMiddleware            │
│                         → ErrorDispatcherMiddleware            │
│  • Request tracing and correlation                             │
│  • Security headers and CSP policies                           │
│  • Error routing based on request type (API vs Pages)          │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                        API Layer                                │
├─────────────────────────────────────────────────────────────────┤
│  FastAPI Routers (URLs, Snapshots, Artifacts, Pages)          │
│  • RESTful endpoints with pagination                           │
│  • Security validation and input sanitization                  │
│  • Pydantic models for type safety                            │
│  • Consistent response formatting                              │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Business Logic Layer                       │
├─────────────────────────────────────────────────────────────────┤
│  StorageService (Caching + Business Logic)                     │
│  • TTL-based caching for performance                           │
│  • Business rule enforcement                                   │
│  • Provider abstraction                                        │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Storage Layer                              │
├─────────────────────────────────────────────────────────────────┤
│  StorageProviderInterface → FilesystemStorageProvider          │
│  • Provider pattern for extensibility                          │
│  • Three-level directory hierarchy scanning                    │
│  • Metadata parsing and artifact discovery                     │
│  • Future: S3, Database providers                              │
└─────────────────────────────────────────────────────────────────┘
```

## Component Interaction Flow

### Application Startup Sequence

```
1. Environment Loading (.env files)
   ↓
2. Logging Configuration (JSON format, correlation IDs)
   ↓
3. Configuration Loading (YAML + environment overrides)
   ↓
4. Storage Provider Creation (Factory pattern)
   ↓
5. Storage Service Creation (Wraps provider with caching)
   ↓
6. FastAPI Application State Injection
   ↓
7. Middleware Pipeline Setup
   ↓
8. Router Registration
   ↓
9. Application Ready
```

### Request Processing Flow

```
HTTP Request
    ↓
CorrelationIdMiddleware (assigns unique request ID)
    ↓
SecurityHeadersMiddleware (adds CSP, security headers)
    ↓
ErrorDispatcherMiddleware (routes to API or Page handler)
    ↓
FastAPI Router (matches endpoint)
    ↓
Route Handler (validates input, accesses storage)
    ↓
StorageService (cached data access)
    ↓
StorageProvider (filesystem operations)
    ↓
Pydantic Models (data validation and serialization)
    ↓
Response (JSON for API, HTML for pages)
```

## Key Architectural Patterns

### 1. Provider Pattern (Storage Layer)

**Purpose**: Abstract storage backends to support multiple implementations

**Implementation**:
```python
# Abstract interface
class StorageProviderInterface(ABC):
    @abstractmethod
    def get_all_urls(self) -> Dict[str, ArchivedUrl]: ...

# Concrete implementation
class FilesystemStorageProvider(StorageProviderInterface):
    def get_all_urls(self) -> Dict[str, ArchivedUrl]:
        # Filesystem-specific implementation
```

**Benefits**:
- Easy switching between storage backends
- Testability through mock providers
- Future extensibility (S3, Database)

### 2. Service Layer Pattern (Business Logic)

**Purpose**: Separate business logic from storage implementation

**Implementation**:
```python
class StorageService:
    def __init__(self, provider: StorageProviderInterface, cache_ttl: int):
        self.provider = provider
        self.cache_ttl = cache_ttl
        # Caching and business logic
```

**Benefits**:
- Centralized caching logic
- Business rule enforcement
- Clean API surface for consumers

### 3. Factory Pattern (Component Creation)

**Purpose**: Centralized creation logic with configuration-driven instantiation

**Implementation**:
```python
def create_storage_service(app_config: AppConfig) -> StorageService:
    provider = create_storage_provider(app_config)
    return StorageService(provider, app_config.storage.cache.ttl_seconds)
```

**Benefits**:
- Configuration-driven component creation
- Dependency injection support
- Easy testing with mock configurations

### 4. Middleware Composition (Request Processing)

**Purpose**: Layered request processing where each middleware has a single responsibility

**Implementation**:
```python
# Single dispatcher middleware
class ErrorDispatcherMiddleware:
    def __init__(self):
        self.api_handler = APIErrorHandler()
        self.page_handler = PageErrorHandler()

    async def dispatch(self, request, call_next):
        # Route to appropriate handler based on path
```

**Benefits**:
- One path check instead of multiple middleware layers
- Clean separation between API and page error handling
- Components can be easily extracted if needed

### 5. Configuration as Code (Type-Safe Config)

**Purpose**: YAML-based configuration with environment overrides

**Implementation**:
```python
class AppConfig(BaseModel):
    storage: StorageConfig = Field(default_factory=StorageConfig)
    validation: ValidationConfig = Field(default_factory=ValidationConfig)
```

**Benefits**:
- Type safety with Pydantic validation
- Environment-specific overrides
- Version-controlled configuration

## Data Flow Architecture

### Storage → API → Frontend Flow

```
1. Filesystem Scanning
   archives/domain/path/req_id_timestamp/
   ├── metadata.json
   ├── archive.wacz
   ├── screenshot.png
   └── singlefile.html

2. Provider Processing
   FilesystemStorageProvider.get_all_urls()
   ├── Directory traversal
   ├── Metadata parsing
   └── Artifact discovery

3. Service Layer Caching
   StorageService.get_all_urls()
   ├── Cache check (TTL-based)
   ├── Provider delegation
   └── Cache update

4. API Endpoints
   GET /api/urls
   ├── Pagination logic
   ├── Filtering/sorting
   └── Response serialization

5. Frontend Rendering
   Templates + Alpine.js
   ├── Server-side rendering
   ├── Client-side enhancement
   └── User interaction
```

### Error Handling Flow

The system handles errors at two different levels:

**1. Application-Level Exceptions** (handled by FastAPI):
```
FastAPI Routing Error (404, validation errors)
    ↓
Application Exception Handler (custom_validation_exception_handler)
    ↓
Routes to appropriate handler based on path (/api/* vs pages)
```

**2. Business Logic Exceptions** (handled by ErrorDispatcherMiddleware):
```
Business Logic Exception (ResourceNotFoundError, ValidationError)
    ↓
ErrorDispatcherMiddleware catches during request processing
    ↓
Path-based routing (/api/* vs pages)
    ↓
Specialized Handler (APIErrorHandler vs PageErrorHandler)
    ↓
Formatted Response (JSON with ErrorResponse vs HTML template)
    ↓
Correlation ID Tracking + Structured Logging
```

The ErrorDispatcherMiddleware doesn't handle ALL errors - it specifically handles exceptions that occur during request processing after routing has succeeded. FastAPI's built-in routing errors and validation errors are handled separately at the application level.

## Security Architecture

### Multi-Layer Security Approach

1. **Input Validation Layer**
   - Pydantic model validation
   - Custom security validators
   - Path traversal protection
   - Regex pattern matching

2. **Middleware Security Layer**
   - Content Security Policy (route-specific)
   - Security headers (XSS, clickjacking protection)
   - HTTPS enforcement
   - Permission policies

3. **Storage Security Layer**
   - Storage boundary validation
   - File extension whitelisting
   - Path resolution and containment
   - Audit logging

4. **Response Security Layer**
   - Content-Type validation
   - Content-Disposition controls
   - Error information filtering
   - Correlation ID tracking

### Content Security Policy Implementation

**Route-Specific Policies**:
- **API Endpoints** (`/api/*`): Strict `default-src 'none'`
- **Artifact Serving**: Permissive for SingleFile HTML content
- **Documentation**: Allows CDN resources for Swagger UI
- **Web Pages**: Balanced policy with Tailwind CSS and Alpine.js

## Technology Stack Integration

### Core Framework Stack
```python
# Web Framework
FastAPI          # Modern async web framework
Uvicorn          # ASGI server with hot-reload
Pydantic         # Data validation and settings

# Request Processing
asgi-correlation-id  # Request tracing
Jinja2              # Template engine
python-multipart    # File upload support

# Configuration
PyYAML              # YAML configuration
python-dotenv       # Environment variables
```

### Frontend Technology Stack
```javascript
// Core Frontend
Alpine.js        # Reactive components
Tailwind CSS     # Utility-first styling
Jinja2          # Server-side templating

// Archive Replay
ReplayWeb.page   # WACZ file replay
Service Workers  # WACZ processing
```

### Development and Deployment
```yaml
# Development Tools
pytest           # Testing framework
httpx           # HTTP client testing
Docker          # Containerization
docker-compose  # Development orchestration
```

## Deployment Architecture

### Container-Based Deployment

```dockerfile
# Multi-stage Dockerfile
FROM python:3.11-slim as base
# Production-optimized image
COPY . /app
RUN pip install -r requirements.txt
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0"]
```

### Environment Configuration

```yaml
# Production Environment
environment:
  - LOG_LEVEL=INFO
  - JSON_LOGGING=true
  - CIVERS_STORAGE_PATH=/archives
  - CIVERS_CACHE_TTL_SECONDS=300

# Development Environment
environment:
  - LOG_LEVEL=DEBUG
  - JSON_LOGGING=true
  - DEBUG=true
```

### Health Monitoring

- **Health Endpoint**: `/health` for load balancer checks
- **Metrics Endpoint**: Cache statistics and performance data
- **Structured Logging**: JSON logs with correlation IDs
- **Error Tracking**: Comprehensive error handling and reporting

## Extension Points

### Adding New Storage Providers

1. **Implement Provider Interface**
   ```python
   class S3StorageProvider(StorageProviderInterface):
       def get_all_urls(self) -> Dict[str, ArchivedUrl]:
           # S3-specific implementation
   ```

2. **Add Configuration Model**
   ```python
   class S3Config(BaseModel):
       bucket: str
       region: str
       access_key_id: str
       secret_access_key: str
   ```

3. **Update Factory Function**
   ```python
   def create_storage_provider(config):
       if config.storage.type == 's3':
           return S3StorageProvider(config.storage.s3)
   ```

### Adding New API Endpoints

1. **Create Router Module**
   ```python
   from fastapi import APIRouter
   router = APIRouter(prefix="/api", tags=["NewFeature"])
   ```

2. **Define Pydantic Models**
   ```python
   class NewFeatureRequest(BaseModel):
       # Request validation

   class NewFeatureResponse(BaseModel):
       # Response formatting
   ```

3. **Register Router**
   ```python
   app.include_router(new_feature_router)
   ```

### Adding New Frontend Components

1. **Create Template Component**
   ```html
   <!-- templates/components/new_component.html -->
   <div class="new-component">
       <!-- Component markup -->
   </div>
   ```

2. **Add Alpine.js Functionality**
   ```javascript
   function newComponent() {
       return {
           // Component state and methods
       };
   }
   ```

3. **Style with Design System**
   ```css
   .new-component {
       /* Use design system variables */
   }
   ```

## Summary

The Civers Web Interface shows a well-organized system that balances:

- **Simplicity**: Clean, understandable code organization
- **Extensibility**: Provider patterns and configuration-driven design
- **Security**: Multi-layer protection with proper validation
- **Maintainability**: Strong type safety and clear separation of concerns

The architecture provides a solid foundation for the current MVP while keeping options open for future enhancements.