/**
 * CiVers Widget - Self-Contained Version
 * 
 * A centrally-hosted widget for external websites to archive their content 
 * using the CiVers infrastructure.
 * 
 * Usage:
 *   <script src="http://localhost:8000/widget/civers-widget.js"
 *           data-api-url="http://localhost:8000"
 *           async></script>
 */

(function () {
    'use strict';

    // Get configuration from script tag data attributes
    // Note: document.currentScript can be null when loaded with async attribute
    let currentScript = document.currentScript;

    // If async loaded, try to find the script element
    if (!currentScript) {
        const scripts = document.querySelectorAll('script[src*="civers-widget.js"]');
        if (scripts.length > 0) {
            currentScript = scripts[scripts.length - 1]; // Get the last matching script
            console.log('🏛️ CiVers: Script loaded asynchronously, found script element');
        }
    }

    // Extract config, with fallbacks if script element not found
    const config = {
        apiUrl: currentScript?.dataset?.apiUrl || 'http://localhost:8000',
        widgetTarget: currentScript?.dataset?.widgetTarget || '#civers-widget-root',
        position: currentScript?.dataset?.position || 'bottom-right',
        theme: currentScript?.dataset?.theme || 'light',
        autoDetectUrl: currentScript?.dataset?.autoDetectUrl !== 'false'
    };

    console.log('🏛️ CiVers Widget: Configuration loaded', config);

    // Track last URL for SPA navigation detection
    let lastUrl = location.href;
    let widgetInstance = null;
    let alpineLoaded = false;

    /**
     * Initialize or update the widget
     */
    function initializeWidget() {
        const currentUrl = location.href;

        if (widgetInstance && currentUrl !== lastUrl) {
            // URL changed - update widget context
            console.log('🏛️ CiVers: URL changed, updating widget:', lastUrl, '→', currentUrl);
            widgetInstance.url = currentUrl;

            // In SPAs, the title might change slightly after the URL
            setTimeout(() => {
                widgetInstance.title = document.title;
            }, 100);

            widgetInstance.checkStatus();
            lastUrl = currentUrl;
            return;
        }

        if (widgetInstance) {
            // Already initialized
            return;
        }

        // First time initialization
        setupWidget();
        lastUrl = currentUrl;
    }

    /**
     * Set up the widget DOM and Alpine.js integration
     */
    function setupWidget() {
        // Wait for DOM to be ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => setupWidget());
            return;
        }

        // Create or find the widget container
        let container = document.querySelector(config.widgetTarget);
        if (!container) {
            container = document.createElement('div');
            container.id = config.widgetTarget.replace('#', '');
            document.body.appendChild(container);
        }

        // Use Shadow DOM for style isolation
        let root = container;
        if (container.attachShadow) {
            if (!container.shadowRoot) {
                root = container.attachShadow({ mode: 'open' });
            } else {
                root = container.shadowRoot;
            }
        }

        // Inject widget HTML structure
        root.innerHTML = `
            <div x-data="civersWidget({
                baseUrl: '${config.apiUrl}',
                url: window.location.href,
                domain: window.location.hostname
            })" class="civers-widget-overlay" :class="{ 'minimized': !expanded, 'expanded': expanded }">
                <link rel="stylesheet" href="${config.apiUrl}/widget/civers-widget.css">
                
                <style>[x-cloak] { display: none !important; }</style>
                
                <!-- Minimized State -->
                <div x-show="!expanded" x-cloak>
                    <div class="widget-minimized-icon" @click="toggle()" title="Expand CiVers Archive Widget">
                        <div class="widget-icon">🏛️</div>
                        <div class="widget-badge" x-show="entityData.has_archives" x-text="entityData.archive_count"></div>
                    </div>
                </div>

                <!-- Expanded State -->
                <div x-show="expanded" class="civers-widget">
                    <div class="widget-header">
                        <span class="flex items-center gap-2">
                            🏛️ CiVers Archive
                            <template x-if="isArchiving && !workflowActive">
                                <div class="small-progress-spinner" title="Archiving in progress..."></div>
                            </template>
                        </span>
                        <div class="widget-controls">
                            <button @click="toggle()" class="widget-control-btn" title="Minimize">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 12H4" />
                                </svg>
                            </button>
                        </div>
                    </div>

                    <div class="widget-body">
                        <div class="mb-4">
                            <span class="text-xs uppercase tracking-wider text-gray-500 font-bold">Archaeological Object</span>
                            <h3 class="text-sm font-bold text-gray-900" x-text="title"></h3>
                            <p class="text-xs text-gray-600 truncate" x-text="url" :title="url"></p>
                        </div>

                        <hr class="my-4">

                        <template x-if="!entityData.has_archives">
                            <div>
                                <p class="text-xs text-gray-700 mb-4">This object has <strong>not been archived</strong> yet.</p>
                                <button @click="archiveNow()" :disabled="isArchiving" class="archive-button">
                                    <span x-show="!isArchiving">📦 Archive This Object</span>
                                    <span x-show="isArchiving">⏳ Archiving...</span>
                                </button>
                                <template x-if="isArchiving && !workflowActive">
                                    <p class="text-[10px] text-indigo-600 font-bold mt-2 animate-pulse" @click="workflowActive = true" style="cursor: pointer">⚡ View Progress</p>
                                </template>
                            </div>
                        </template>

                        <template x-if="entityData.has_archives">
                            <div>
                                <div class="flex items-center justify-between mb-4">
                                    <span class="archive-count-badge" x-text="entityData.archive_count + ' snapshots'"></span>
                                    <button @click="viewAll()" class="text-xs text-indigo-600 font-bold hover:underline">View All</button>
                                </div>

                                <div class="archive-timeline space-y-4 max-h-48 overflow-y-auto pr-2">
                                    <template x-for="(archive, idx) in entityData.archives" :key="idx">
                                        <div class="flex gap-3 p-2 hover:bg-gray-50 rounded cursor-pointer transition-colors" @click="viewReplay(archive.snapshot_id)">
                                            <div class="w-2 h-2 rounded-full mt-1.5" :class="idx === 0 ? 'bg-green-500' : 'bg-gray-300'"></div>
                                            <div class="flex-1 min-w-0">
                                                <p class="text-xs font-bold text-gray-800" x-text="formatDate(archive.timestamp)"></p>
                                                <p class="text-[10px] text-indigo-500 font-mono truncate" x-text="archive.snapshot_id"></p>
                                            </div>
                                        </div>
                                    </template>
                                </div>

                                <div class="mt-6 flex flex-col gap-2">
                                    <button @click="archiveNow()" class="archive-again-button">Create New Snapshot</button>
                                    <button @click="generateCitation()" class="btn-outline">📋 Citation</button>
                                    <template x-if="isArchiving && !workflowActive">
                                        <p class="text-[10px] text-indigo-600 font-bold mt-1 text-center animate-pulse" @click="workflowActive = true" style="cursor: pointer">⚡ Archiving in progress... Click to view.</p>
                                    </template>
                                </div>
                            </div>
                        </template>
                    </div>
                </div>

                <!-- Progress Modal -->
                <div x-show="workflowActive" class="widget-progress-modal" x-cloak>
                    <div class="widget-progress-content">
                        <div class="flex justify-between items-center mb-4 border-b pb-2">
                            <h3 class="text-lg font-bold">Archiving Status</h3>
                            <button @click="workflowActive = false" class="modal-close-btn">
                                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                                </svg>
                            </button>
                        </div>

                        <div class="mb-6">
                            <div class="progress-container">
                                <div class="progress-bar" :style="'width: ' + progress + '%'"></div>
                            </div>
                            <div class="flex justify-between items-center mt-2">
                                <span class="text-xs font-bold text-gray-500" x-text="progress + '%'"></span>
                                <span class="text-xs font-bold text-indigo-600" x-text="currentStep"></span>
                            </div>
                        </div>

                        <div class="space-y-3" x-show="archiveStatus === 'running' || archiveStatus === 'idle'">
                            <template x-for="step in workflowSteps" :key="step.id">
                                <div class="step-item" :class="{
                                    'completed': step.status === 'completed',
                                    'in-progress': step.status === 'in_progress',
                                    'pending': step.status === 'pending'
                                }">
                                    <div class="step-icon">
                                        <template x-if="step.status === 'completed'">
                                            <svg class="w-4 h-4 text-green-600" fill="currentColor" viewBox="0 0 20 20">
                                                <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"></path>
                                            </svg>
                                        </template>
                                        <template x-if="step.status === 'in_progress'">
                                            <div class="w-3 h-3 bg-blue-500 rounded-full animate-pulse"></div>
                                        </template>
                                        <template x-if="step.status === 'failed'">
                                            <svg class="w-4 h-4 text-red-600" fill="currentColor" viewBox="0 0 20 20">
                                                <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
                                            </svg>
                                        </template>
                                        <template x-if="step.status === 'pending'">
                                            <div class="w-2 h-2 bg-gray-300 rounded-full"></div>
                                        </template>
                                    </div>
                                    <span class="step-label" x-text="step.display"></span>
                                </div>
                            </template>
                        </div>

                        <!-- Success Result -->
                        <template x-if="archiveStatus === 'success'">
                            <div class="archive-result-success">
                                <p class="font-bold flex items-center gap-2">✅ Success!</p>
                                <p class="text-sm mt-1">Archive created successfully. You can now view it in the repository.</p>
                                <a href="#" class="btn-view-replay" @click.prevent="viewReplay(lastSnapshotId)">View Replay</a>
                                <button @click="workflowActive = false" class="btn-outline mt-3 w-full">Dismiss</button>
                            </div>
                        </template>

                        <!-- Error Result -->
                        <template x-if="archiveStatus === 'failed'">
                            <div class="archive-result-failed">
                                <p class="font-bold flex items-center gap-2">❌ Failed</p>
                                <p class="text-sm mt-1">Archiving failed. This might be due to a timeout or backend error.</p>
                                <button @click="workflowActive = false" class="btn-outline mt-3 w-full">Close</button>
                            </div>
                        </template>
                    </div>
                </div>
            </div>
        `;

        // Load Alpine.js if not already loaded
        if (!window.Alpine && !alpineLoaded) {
            alpineLoaded = true;
            const alpineScript = document.createElement('script');
            alpineScript.src = 'https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js';
            alpineScript.defer = true;
            alpineScript.onload = () => {
                console.log('🏛️ CiVers: Alpine.js script loaded');
                // Store reference to widget instance
                setTimeout(() => {
                    if (!window.Alpine) {
                        console.error('🏛️ CiVers: Alpine.js not found even after load');
                        return;
                    }
                    const searchRoot = container.shadowRoot || container;

                    // Manually initialize Alpine for the shadow root
                    if (searchRoot instanceof ShadowRoot) {
                        console.log('🏛️ CiVers: Initializing Alpine for Shadow Root');
                        window.Alpine.initTree(searchRoot);
                    }

                    const widgetEl = searchRoot.querySelector('[x-data]');
                    if (widgetEl && widgetEl.__x) {
                        widgetInstance = widgetEl.__x.$data;
                        console.log('🏛️ CiVers: Widget instance captured');
                    } else {
                        // Fallback: search for Alpine component data
                        console.warn('🏛️ CiVers: Could not find widget instance, retrying...');
                    }
                }, 200);
            };
            document.head.appendChild(alpineScript);
        } else if (window.Alpine) {
            // Alpine already exists, initialize immediately
            console.log('🏛️ CiVers: Alpine.js already on page, using existing instance');
            setTimeout(() => {
                const searchRoot = container.shadowRoot || container;
                if (searchRoot instanceof ShadowRoot) {
                    window.Alpine.initTree(searchRoot);
                }
                const widgetEl = searchRoot.querySelector('[x-data]');
                if (widgetEl && widgetEl.__x) {
                    widgetInstance = widgetEl.__x.$data;
                    console.log('🏛️ CiVers: Found widget instance (pre-existing Alpine)');
                }
            }, 100);
        }

        // Set up SPA navigation detection
        setupNavigationDetection();

        console.log('🏛️ CiVers Widget initialized for:', config.apiUrl);
    }

    /**
     * Set up automatic SPA navigation detection
     */
    function setupNavigationDetection() {
        // Strategy 1: History API interception (covers 95% of SPAs)
        const originalPushState = history.pushState;
        history.pushState = function () {
            originalPushState.apply(history, arguments);
            initializeWidget();
        };

        const originalReplaceState = history.replaceState;
        history.replaceState = function () {
            originalReplaceState.apply(history, arguments);
            initializeWidget();
        };

        // Strategy 2: Popstate event (browser back/forward)
        window.addEventListener('popstate', () => {
            initializeWidget();
        });

        // Strategy 3: Polling fallback (for edge cases)
        setInterval(() => {
            if (location.href !== lastUrl) {
                initializeWidget();
            }
        }, 500);
    }

    // Start initialization
    initializeWidget();

    // Expose widget API globally (optional)
    window.CiVersWidget = {
        refresh: initializeWidget,
        getInstance: () => widgetInstance
    };

})();

// Widget logic function (to be called by Alpine.js)
function civersWidget(config) {
    return {
        // Configuration
        baseUrl: config.baseUrl || '',
        url: config.url || window.location.href,
        domain: config.domain || window.location.hostname,

        // UI State
        expanded: false,
        isArchiving: false,
        workflowActive: false,
        archiveStatus: 'idle', // 'idle', 'running', 'success', 'failed'
        progress: 0,
        currentStep: '',

        // Data State
        title: document.title,
        lastSnapshotId: null,
        entityData: {
            has_archives: false,
            archive_count: 0,
            archives: [],
            ...config.initialData
        },

        // workflowSteps will be populated dynamically from the backend
        workflowSteps: [],

        /**
         * Initialize the widget
         */
        init() {
            // SPAs like Arachne change title after the component mounts
            setTimeout(() => {
                this.title = document.title;
            }, 500);

            console.log('🏛️ CiVers Widget Initialized for:', this.url, 'Title:', this.title);
            this.checkStatus();
        },

        /**
         * Generate a filesystem-safe ID from the URL
         */
        generateUrlId(url) {
            try {
                const parsed = new URL(url);
                const domain = parsed.hostname;
                let path = parsed.pathname;

                // Normalize domain: dots and hyphens to underscores
                const normDomain = domain.replace(/\./g, '_').replace(/-/g, '_');

                // Normalize path: same as backend's normalize_path
                path = path.replace(/^\/+|\/+$/g, ''); // strip leading/trailing slashes
                if (!path) {
                    path = 'home';
                } else {
                    // Replace special characters with underscores, handle hyphens, remove repeats
                    path = path.replace(/[^a-zA-Z0-9_-]/g, '_').replace(/-/g, '_').replace(/_+/g, '_').toLowerCase();
                }

                return `${normDomain}_${path}`;
            } catch (e) {
                console.error('Failed to parse URL:', url, e);
                return 'unknown';
            }
        },

        /**
         * Check archive status for this URL
         */
        async checkStatus() {
            const urlId = this.generateUrlId(this.url);
            try {
                const response = await fetch(`${this.baseUrl}/api/url/${urlId}`);
                if (response.ok) {
                    const data = await response.json();
                    this.entityData = {
                        has_archives: data.snapshots && data.snapshots.length > 0,
                        archive_count: data.snapshots ? data.snapshots.length : 0,
                        archives: (data.snapshots || []).map(s => ({
                            snapshot_id: s.snapshot_id,
                            timestamp: s.timestamp,
                            doi: s.snapshot_id
                        }))
                    };
                } else {
                    this.entityData.has_archives = false;
                    this.entityData.archive_count = 0;
                    this.entityData.archives = [];
                }
            } catch (error) {
                console.error('CiVers: Failed to check status:', error);
            }
        },

        /**
         * Trigger the archiving process
         */
        async archiveNow() {
            if (this.isArchiving) return;

            this.isArchiving = true;
            this.workflowActive = true;
            this.archiveStatus = 'running';
            this.progress = 0;
            this.resetSteps();

            try {
                // 1. Submit request to backend
                const response = await fetch(`${this.baseUrl}/api/archive-request`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        url: this.url,
                        domain: 'default'  // Use 'default' domain for widget requests
                    })
                });

                if (!response.ok) throw new Error('Failed to submit archive request');

                const result = await response.json();
                const requestId = result.request_id;

                // Populate steps and set initial UI state from the submission response
                this.updateWorkflow(result);
                this.progress = 5;

                // 2. Start polling for status
                this.pollStatus(requestId);

            } catch (error) {
                console.error('CiVers: Archiving failed:', error);
                alert('Failed to start archiving. Please check backend connection.');
                this.isArchiving = false;
                this.workflowActive = false;
            }
        },

        /**
         * Poll the backend for progress updates
         */
        async pollStatus(requestId) {
            const pollInterval = setInterval(async () => {
                try {
                    const response = await fetch(`${this.baseUrl}/api/request-status/${requestId}`);
                    if (!response.ok) return;

                    const data = await response.json();
                    this.updateWorkflow(data);

                    if (data.status === 'completed' || data.status === 'failed') {
                        clearInterval(pollInterval);
                        this.finalizeWorkflow(data);
                    }
                } catch (error) {
                    console.error('CiVers: Polling error:', error);
                }
            }, 2000);
        },

        /**
         * Update the UI based on polling data
         */
        updateWorkflow(data) {
            // Update workflow steps if provided by backend
            if (data.workflow_steps && data.workflow_steps.length > 0) {
                // If we don't have steps yet, or they changed, initialize them
                if (this.workflowSteps.length === 0) {
                    this.workflowSteps = data.workflow_steps.map(s => ({
                        ...s,
                        status: 'pending'
                    }));
                }
            }

            const completedSteps = data.completed_steps || [];
            const currentStepId = data.current_step;
            const status = data.status;

            this.workflowSteps.forEach(step => {
                if (completedSteps.includes(step.id)) {
                    step.status = 'completed';
                } else if (step.id === currentStepId) {
                    step.status = 'in_progress';
                } else {
                    // It's either pending or failed (if the whole workflow failed at this step)
                    if (status === 'failed' && step.id === currentStepId) {
                        step.status = 'failed';
                    } else if (!completedSteps.includes(step.id)) {
                        step.status = 'pending';
                    }
                }
            });

            // Map backend status to user-friendly text
            const statusMap = {
                'submitted': 'Request Queued',
                'pending': 'Preparing Workflow',
                'in_progress': 'Archiving...',
                'completed': 'Success!',
                'failed': 'Failed'
            };

            this.currentStep = statusMap[status] || status || 'Processing...';

            if (this.workflowSteps.length > 0) {
                // Calculate progress: each completed step adds its portion
                const stepWeight = 100 / this.workflowSteps.length;
                const progressFromSteps = completedSteps.length * stepWeight;

                // If a step is in progress, add half its weight for visual movement
                const inProgressBonus = currentStepId ? stepWeight / 2 : 0;

                this.progress = Math.min(Math.round(progressFromSteps + inProgressBonus), 99);
            } else {
                // Fallback progress if no steps identified yet
                if (status === 'in_progress') this.progress = 50;
            }

            if (status === 'completed') this.progress = 100;
            if (status === 'failed') this.progress = Math.max(this.progress, 1);
        },

        /**
         * Handle workflow completion or failure
         */
        finalizeWorkflow(data) {
            this.progress = data.status === 'completed' ? 100 : this.progress;
            this.archiveStatus = data.status === 'completed' ? 'success' : 'failed';
            this.lastSnapshotId = data.snapshot_id || null;

            setTimeout(() => {
                // Keep modal open, but allow it to be dismissed manually
                if (data.status === 'completed') {
                    this.isArchiving = false;
                    this.checkStatus(); // Refresh snapshots list
                } else {
                    this.isArchiving = false;
                }
            }, 500);
        },

        /**
         * Generate citation for the latest snapshot
         */
        generateCitation() {
            if (!this.entityData.has_archives || this.entityData.archives.length === 0) return;

            const latest = this.entityData.archives[0];
            const date = new Date(latest.timestamp).toLocaleDateString();
            const url = this.url;

            const citation = `CiVers Archival Record. (Archived: ${date}). "${url}". Snapshot ID: ${latest.snapshot_id}. Retrieved from CiVers Archive.`;

            this.copyToClipboard(citation);
            alert(`✅ Citation copied to clipboard!\n\n${citation}`);
            console.log('🏛️ CiVers Citation:', citation);
        },

        viewAll() {
            const urlId = this.generateUrlId(this.url);
            const cleanBaseUrl = this.baseUrl.replace(/\/+$/, '');
            const targetUrl = `${cleanBaseUrl}/archive/${urlId}`;
            console.log('🏛️ CiVers: Redirecting to Archive View:', targetUrl);
            window.open(targetUrl, '_blank');
        },

        viewReplay(snapshotId) {
            const cleanBaseUrl = this.baseUrl.replace(/\/+$/, '');
            const targetUrl = `${cleanBaseUrl}/replay/${snapshotId}`;
            console.log('🏛️ CiVers: Redirecting to Replay View:', targetUrl);
            window.open(targetUrl, '_blank');
        },

        resetSteps() {
            this.workflowSteps.forEach(s => s.status = 'pending');
            this.currentStep = 'Initializing...';
        },

        formatDate(ts) {
            if (!ts) return '';
            return new Date(ts).toLocaleDateString('en-US', {
                year: 'numeric',
                month: 'short',
                day: 'numeric'
            });
        },

        copyToClipboard(text) {
            navigator.clipboard.writeText(text);
        },

        toggle() {
            this.expanded = !this.expanded;
        }
    };
}
