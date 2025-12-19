# Frontend Documentation

## Overview

The frontend uses Jinja2 templating, Alpine.js for interactions, Tailwind CSS for styling, and a custom design system. It follows mobile-first responsive design with accessibility features and clean separation of concerns.

### Design principles:
1. **Component modularity**: Reusable templates and JavaScript components
2. **Progressive enhancement**: Works without JavaScript, enhanced with Alpine.js
3. **Responsive design**: Mobile-first approach with touch-friendly interfaces

## Template System

### Template structure:

```
templates/
├── base.html              # Master template with layout
├── url_archive.html       # Archive listing page
├── replay.html           # Snapshot replay page
├── 404.html             # Error page
└── components/          # Reusable components
    ├── nav.html         # Navigation header
    ├── footer.html      # Footer component
    ├── breadcrumbs.html # Breadcrumb navigation
    ├── wacz_replay.html # WACZ viewer component
    └── singlefile_viewer.html # SingleFile HTML viewer
```

### Base template:

The **base.html** template provides the foundation:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="{% block meta_description %}...{% endblock %}">
    <title>{% block title %}{{ title or "Civers Archive Web Interface" }}{% endblock %}</title>

    <!-- External Dependencies -->
    <script src="https://cdn.tailwindcss.com"></script>
    <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>

    <!-- Custom Styles -->
    <link rel="stylesheet" href="{{ url_for('static', path='/css/styles.css') }}">
    <link rel="stylesheet" href="{{ url_for('static', path='/css/responsive.css') }}">
    <link rel="stylesheet" href="{{ url_for('static', path='/css/components.css') }}">
</head>
<body class="bg-gray-50 min-h-screen flex flex-col" x-data="{ toastMessage: '', showToast: false, mobileMenuOpen: false }">
```

Key features:
- **Alpine.js root data**: Global state management for toasts and mobile menu
- **Accessibility**: Skip links, proper ARIA labels, semantic HTML
- **SEO optimization**: Dynamic meta descriptions and titles
- **Progressive loading**: Deferred Alpine.js loading

### Component Templates and Reusability

#### Navigation Component (`templates/components/nav.html`)

```html
<header class="nav-component" role="banner">
    <nav class="container" role="navigation" aria-label="Main navigation">
        <div class="flex justify-between items-center h-16">
            <!-- Logo with Archive icon -->
            <div class="flex items-center">
                <h1 class="text-xl font-semibold">
                    <a href="/" class="nav-logo text-primary hover:text-primary focus-ring rounded-sm px-1">
                        <span class="flex items-center">
                            <svg class="w-6 h-6 mr-2 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4"/>
                            </svg>
                            Civers Archive
                        </span>
                    </a>
                </h1>
            </div>

            <!-- Responsive Navigation -->
            <div class="desktop-nav hidden md:block">
                <div class="ml-10 flex items-baseline space-x-4">
                    <a href="/" class="btn btn-ghost text-sm">Home</a>
                    <a href="/docs" class="btn btn-ghost text-sm">API Docs</a>
                    <a href="/health" class="btn btn-ghost text-sm">Health</a>
                </div>
            </div>

            <!-- Mobile Menu Toggle with Alpine.js -->
            <div class="mobile-menu-button md:hidden">
                <button @click="mobileMenuOpen = !mobileMenuOpen" type="button" class="btn btn-ghost">
                    <svg x-show="!mobileMenuOpen" class="block h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
                    </svg>
                    <svg x-show="mobileMenuOpen" class="block h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                </button>
            </div>
        </div>
    </nav>
</header>
```

#### WACZ Replay Component (`templates/components/wacz_replay.html`)

```html
<div class="wacz-replay-container">
    <!-- Controls Bar -->
    <div class="card-header flex items-center justify-between">
        <div class="flex items-center space-x-3">
            <button onclick="toggleWACZFullscreen()" class="btn btn-ghost btn-sm" title="Toggle fullscreen">
                <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 8V4m0 0h4m-4 0l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 1v4m0 0h-4m4 0l-5-5" />
                </svg>
            </button>
            <div class="text-sm text-gray">Web Archive Replay</div>
        </div>
    </div>

    <!-- ReplayWeb.page Integration -->
    <div class="relative">
        <replay-web-page
            source="/api/artifacts/serve?snapshot_id={{ snapshot_id }}&type=archive.wacz"
            url="{{ archived_url.original_url if archived_url else '' }}"
            coll="archive"
            loading="lazy"
            replayBase="/static/lib/replaywebpage/"
            style="width: 100%; height: 600px; border: 1px solid #e5e7eb;"
            id="wacz-component-{{ snapshot_id }}">
        </replay-web-page>
    </div>
</div>
```

### Jinja2 Integration with FastAPI

The templates are rendered through FastAPI's template engine:

```python
# From app/routes/pages.py
@router.get("/archive/{url_id}", response_class=HTMLResponse)
async def archive_page(request: Request, url_id: str):
    context = {
        "request": request,
        "title": f"Archive: {archived_url.original_url}",
        "url_id": url_id,
        "original_url": str(archived_url.original_url),
        "snapshot_count": archived_url.snapshot_count,
        "date_range": archived_url.date_range
    }
    return templates.TemplateResponse("url_archive.html", context)
```

## CSS Architecture

### File Organization and Design System

```
static/css/
├── styles.css        # Core design system and components
├── responsive.css    # Responsive design utilities
└── components.css    # Component-specific enhancements
```

### Design System Implementation (`static/css/styles.css`)

The CSS architecture uses **CSS Custom Properties** for a comprehensive design token system:

```css
:root {
  /* Primary Color Palette */
  --color-primary-50: #eff6ff;
  --color-primary-600: #2563eb;
  --color-primary-700: #1d4ed8;

  /* Typography Scale */
  --font-family-primary: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto;
  --font-size-xs: 0.75rem;    /* 12px */
  --font-size-sm: 0.875rem;   /* 14px */
  --font-size-base: 1rem;     /* 16px */
  --font-size-lg: 1.125rem;   /* 18px */

  /* Spacing Scale */
  --spacing-1: 0.25rem;   /* 4px */
  --spacing-2: 0.5rem;    /* 8px */
  --spacing-4: 1rem;      /* 16px */
  --spacing-6: 1.5rem;    /* 24px */

  /* Transitions */
  --transition-fast: 150ms ease-in-out;
  --transition-base: 200ms ease-in-out;
}
```

### Component-Based Styling

#### Button System
```css
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-2) var(--spacing-4);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  border-radius: var(--radius-md);
  transition: all var(--transition-fast);
}

.btn-primary {
  background-color: var(--color-primary-600);
  color: white;
  border-color: var(--color-primary-600);
}

.btn-primary:hover {
  background-color: var(--color-primary-700);
}
```

#### Card System
```css
.card {
  background-color: white;
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--color-gray-200);
  overflow: hidden;
}

.card-header {
  padding: var(--spacing-6);
  border-bottom: 1px solid var(--color-gray-200);
}

.card-body {
  padding: var(--spacing-6);
}
```

### Responsive Design Patterns (`static/css/responsive.css`)

Mobile-first approach with systematic breakpoints:

```css
/* Mobile: 0-639px */
.container {
  padding-left: var(--spacing-4);
  padding-right: var(--spacing-4);
}

/* Tablet: 640px+ */
@media (min-width: 640px) {
  .container {
    padding-left: var(--spacing-6);
    padding-right: var(--spacing-6);
  }

  .grid-responsive {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

/* Desktop: 768px+ */
@media (min-width: 768px) {
  .nav-component .mobile-menu-button {
    display: none;
  }

  .nav-component .desktop-nav {
    display: block;
  }
}

/* Large Desktop: 1024px+ */
@media (min-width: 1024px) {
  .grid-responsive {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}
```

### Accessibility and UX Enhancements (`static/css/components.css`)

```css
/* Focus Enhancement */
.focus-ring:focus {
  @apply ring-2 ring-blue-500 ring-offset-2;
}

/* High Contrast Support */
@media (prefers-contrast: high) {
  .text-gray-500,
  .text-gray-600 {
    @apply text-black;
  }
}

/* Reduced Motion Support */
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}

/* Touch Device Optimizations */
@media (hover: none) and (pointer: coarse) {
  .btn {
    min-height: 44px;
    padding: var(--spacing-3) var(--spacing-4);
  }
}
```

## JavaScript Components

### Alpine.js Integration and Usage Patterns

The frontend uses **Alpine.js** for reactive interactivity with a component-based approach:

#### URL Archive Component (`static/js/url_archive.js`)

```javascript
function urlArchive(urlId) {
    return {
        // State Management
        urlId: urlId,
        loading: true,
        error: null,
        snapshots: [],
        currentPage: 1,
        totalPages: 0,
        limit: 50,
        sortBy: 'timestamp',

        // Lifecycle
        init() {
            console.log('Initializing URL Archive for:', this.urlId);
            this.loadSnapshots();
        },

        // API Integration
        async loadSnapshots() {
            this.loading = true;
            this.error = null;

            try {
                const params = new URLSearchParams({
                    page: this.currentPage.toString(),
                    limit: this.limit.toString(),
                    sort: this.sortBy
                });

                const response = await fetch(`/api/urls/${this.urlId}/snapshots?${params}`);
                const data = await response.json();

                this.snapshots = (data.data || []).map(snapshot => ({
                    ...snapshot,
                    artifacts: this.transformArtifacts(snapshot.available_artifacts || [])
                }));

                this.totalPages = data.pagination?.total_pages || 0;
                this.totalCount = data.pagination?.total_count || 0;
            } catch (error) {
                this.error = error.message;
                this.snapshots = [];
            } finally {
                this.loading = false;
            }
        },

        // Pagination
        async goToPage(page) {
            if (page === this.currentPage || page < 1 || page > this.totalPages) return;
            this.currentPage = page;
            await this.loadSnapshots();
            document.getElementById('main-content')?.scrollIntoView({ behavior: 'smooth' });
        },

        // Download Functionality
        async downloadArtifact(snapshotId, artifactType) {
            const typeMapping = {
                'wacz': 'archive.wacz',
                'singlefile': 'singlefile.html',
                'screenshot': 'screenshot.png',
                'metadata': 'metadata.json'
            };

            const actualType = typeMapping[artifactType] || artifactType;
            const url = `/api/artifacts/serve?snapshot_id=${encodeURIComponent(snapshotId)}&type=${encodeURIComponent(actualType)}`;

            const link = document.createElement('a');
            link.href = url;
            link.download = '';
            link.style.display = 'none';

            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }
    };
}
```

#### SingleFile Viewer Component (`static/js/singlefile_viewer.js`)

```javascript
function singleFileViewer(snapshotId) {
    return {
        // State
        snapshotId: snapshotId,
        loading: true,
        error: null,
        isFullscreen: false,
        iframeSrc: `/api/artifacts/serve?snapshot_id=${encodeURIComponent(snapshotId)}&type=singlefile.html`,

        // Lifecycle Management
        init() {
            this.fullscreenHandler = () => this.onFullscreenChange();
            document.addEventListener('fullscreenchange', this.fullscreenHandler);
        },

        // Event Handlers
        onIframeLoad() {
            this.loading = false;
            this.error = null;
        },

        onIframeError() {
            this.loading = false;
            this.error = 'Failed to load SingleFile content';
        },

        // Fullscreen Management
        async toggleFullscreen() {
            try {
                if (this.isFullscreen) {
                    await document.exitFullscreen();
                } else {
                    const container = document.querySelector('.singlefile-container');
                    if (container) {
                        await container.requestFullscreen();
                    }
                }
            } catch (error) {
                console.warn('Fullscreen not supported:', error);
            }
        },

        // Cleanup
        destroy() {
            if (this.fullscreenHandler) {
                document.removeEventListener('fullscreenchange', this.fullscreenHandler);
                this.fullscreenHandler = null;
            }
        }
    };
}
```

### Client-Side Functionality

#### Toast Notification System
The base template includes a sophisticated toast system:

```html
<div x-show="showToast"
     x-transition:enter="transform ease-out duration-300 transition"
     x-transition:enter-start="translate-y-2 opacity-0 sm:translate-y-0 sm:translate-x-2"
     x-transition:enter-end="translate-y-0 opacity-100 sm:translate-x-0"
     class="fixed inset-0 flex items-end justify-center px-4 py-6 pointer-events-none sm:p-6 sm:items-start sm:justify-end z-50">
    <div class="max-w-sm w-full bg-white shadow-lg rounded-lg pointer-events-auto">
        <div class="p-4">
            <div class="flex items-start">
                <svg class="h-6 w-6 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <div class="ml-3 w-0 flex-1 pt-0.5">
                    <p class="text-sm font-medium text-gray-900" x-text="toastMessage"></p>
                </div>
            </div>
        </div>
    </div>
</div>

<script>
function showToast(message) {
    const body = document.querySelector('body');
    if (body.__x) {
        body.__x.$data.toastMessage = message;
        body.__x.$data.showToast = true;
        setTimeout(() => {
            body.__x.$data.showToast = false;
        }, 5000);
    }
}
</script>
```

## Page Routes

### Route Definitions and URL Patterns (`app/routes/pages.py`)

```python
@router.get("/", response_class=HTMLResponse)
async def home_page(request: Request):
    """Render the home page."""
    context = {
        "request": request,
        "title": "Civers Archive Web Interface"
    }
    return templates.TemplateResponse("base.html", context)

@router.get("/archive/{url_id}", response_class=HTMLResponse)
async def archive_page(request: Request, url_id: str):
    """Render archive page for a specific URL with snapshots."""
    storage_service = request.app.state.storage_service
    archived_url = storage_service.get_url_by_id(url_id)

    if not archived_url:
        raise HTTPException(status_code=404, detail=f"Archive not found for URL ID: {url_id}")

    context = {
        "request": request,
        "title": f"Archive: {archived_url.original_url}",
        "url_id": url_id,
        "original_url": str(archived_url.original_url),
        "snapshot_count": archived_url.snapshot_count,
        "date_range": archived_url.date_range
    }

    return templates.TemplateResponse("url_archive.html", context)

@router.get("/replay/{snapshot_id}", response_class=HTMLResponse)
async def replay_page(request: Request, snapshot_id: str, view_type: str = Query(None)):
    """Render replay page for snapshot with WACZ/SingleFile view toggle."""
    storage_service = request.app.state.storage_service
    snapshot = storage_service.get_snapshot_by_id(snapshot_id)

    if not snapshot:
        raise HTTPException(status_code=404, detail=f"Snapshot not found: {snapshot_id}")

    # Determine available view types
    available_views = []
    if snapshot.has_wacz:
        available_views.append('wacz')
    if snapshot.has_singlefile:
        available_views.append('singlefile')

    # Set default view
    if not view_type and available_views:
        view_type = 'wacz' if 'wacz' in available_views else available_views[0]

    context = {
        "request": request,
        "snapshot_id": snapshot_id,
        "snapshot": {
            "snapshot_id": snapshot.snapshot_id,
            "timestamp": snapshot.timestamp.isoformat(),
            "title": snapshot.title,
            "status_code": snapshot.status_code,
            "available_artifacts": snapshot.available_artifacts
        },
        "current_view": view_type,
        "available_views": available_views
    }

    return templates.TemplateResponse("replay.html", context)
```

### Template Rendering and Data Passing

The routes follow a consistent pattern:
1. **Input validation** - Check URL/snapshot ID exists
2. **Data retrieval** - Fetch from storage service
3. **Context preparation** - Transform data for template
4. **Template rendering** - Return HTML response

## Static Asset Management

### Asset Organization and Serving

```
static/
├── css/                 # Stylesheets
│   ├── styles.css       # Core design system
│   ├── responsive.css   # Responsive utilities
│   └── components.css   # Component enhancements
├── js/                  # JavaScript components
│   ├── app.js           # Main application utilities
│   ├── url_archive.js   # Archive page component
│   ├── replay.js        # Replay page component
│   └── singlefile_viewer.js # SingleFile viewer
├── lib/                 # Third-party libraries
│   ├── alpine.min.js    # Alpine.js framework
│   └── replaywebpage/   # ReplayWeb.page for WACZ
│       ├── ui.js        # UI components
│       └── sw.js        # Service worker
└── replay-sw.js         # Custom service worker
```

### Third-Party Library Integration

#### Alpine.js Integration
- **CDN loading**: `https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js`
- **Deferred loading**: Loads after DOM parsing
- **Global availability**: Components accessible via `window.functionName`

#### ReplayWeb.page Integration
- **Custom web components**: `<replay-web-page>` element
- **Service worker**: WACZ file processing and replay
- **Dynamic loading**: Only loaded when WACZ view is active

#### Service Worker Architecture (`static/replay-sw.js`)

```javascript
// Add fetch event listener BEFORE importing ReplayWeb.page SW
self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);

    // Bypass SingleFile HTML requests - let them pass through directly
    if (url.pathname.includes('/api/artifacts/serve') &&
        url.searchParams.get('type') === 'singlefile.html') {
        console.log('Service worker bypassing SingleFile request:', url.href);
        return; // Don't intercept, let request pass through normally
    }

    // For all other requests, continue to ReplayWeb.page processing
});

// Import the ReplayWeb.page service worker
importScripts('/static/lib/replaywebpage/sw.js');
```

## Design System

### Color Scheme and Typography

#### Color Palette
- **Primary Blue**: `#2563eb` (blue-600) with full spectrum from 50-900
- **Gray Scale**: Neutral grays from `#f9fafb` (gray-50) to `#111827` (gray-900)
- **Semantic Colors**: Success (green), Warning (yellow), Error (red)

#### Typography Scale
- **Font Family**: System font stack prioritizing readability
- **Scale**: 8-step type scale from 12px (xs) to 36px (4xl)
- **Weight**: Normal (400), Medium (500), Semibold (600), Bold (700)

### Component Patterns and Styling

#### Badge System
```css
.badge {
  display: inline-flex;
  align-items: center;
  padding: var(--spacing-1) var(--spacing-2);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-medium);
  border-radius: var(--radius-full);
  text-transform: uppercase;
}

.badge-success {
  background-color: var(--color-success-100);
  color: var(--color-success-700);
}
```

#### Loading States
```css
.loading-spinner {
  display: inline-block;
  width: 1.5rem;
  height: 1.5rem;
  border: 2px solid var(--color-gray-200);
  border-radius: 50%;
  border-top-color: var(--color-primary-600);
  animation: spin 1s ease-in-out infinite;
}

.loading-skeleton {
  background: linear-gradient(90deg, var(--color-gray-200) 25%, var(--color-gray-100) 50%, var(--color-gray-200) 75%);
  background-size: 200% 100%;
  animation: loading-shimmer 1.5s infinite;
}
```

### Responsive Design Implementation

#### Mobile-First Strategy
1. **Base styles**: Optimized for mobile (320px+)
2. **Progressive enhancement**: Add complexity at larger breakpoints
3. **Touch optimization**: 44px minimum touch targets
4. **Performance**: Conditional loading based on screen size

#### Breakpoint System
- **Mobile**: 0-639px
- **Tablet**: 640px-1023px
- **Desktop**: 1024px+

#### Component Adaptations
- **Navigation**: Hamburger menu on mobile, horizontal on desktop
- **Tables**: Card view on mobile, table view on desktop
- **Forms**: Stacked on mobile, inline on desktop
- **Grid**: 1 column mobile → 2 columns tablet → 4 columns desktop

## Integration Between Frontend and Backend

### API Integration Patterns

The frontend integrates seamlessly with the FastAPI backend through:

1. **Template Context**: Server-side data injection into templates
2. **AJAX Requests**: Client-side API calls for dynamic content
3. **Asset Serving**: Direct artifact serving through `/api/artifacts/serve`
4. **Service Workers**: WACZ processing and caching

### Data Flow Architecture

```
FastAPI Routes → Storage Service → Template Context → Jinja2 → HTML
     ↓                                      ↓
Alpine.js Components ← JavaScript APIs ← Client State
     ↓                                      ↓
User Interactions → API Requests → Backend Services
```

## Summary

The Civers Web Interface demonstrates modern frontend architecture best practices with a focus on **accessibility**, **performance**, and **maintainability**. The component-based approach enables efficient development and consistent user experiences across all device types.