/**
 * Alpine.js component for Replay page functionality
 * Handles view switching, content loading, and artifact downloads
 */

function replayPage(snapshotId, initialView, availableViews) {
    return {
        // State
        snapshotId: snapshotId,
        currentView: initialView,
        availableViews: availableViews,
        loading: false,
        error: null,

        /**
         * Initialize the component
         */
        init() {
            console.log('Initializing Replay page for snapshot:', this.snapshotId);
            console.log('Available views:', this.availableViews);
            console.log('Initial view:', this.currentView);

            // Set default view if none provided
            if (!this.currentView && this.availableViews.length > 0) {
                if (this.availableViews.includes('wacz')) {
                    this.currentView = 'wacz';
                } else if (this.availableViews.includes('warc')) {
                    this.currentView = 'warc';
                } else {
                    this.currentView = this.availableViews[0];
                }
            }

            // WACZ library and service worker are loaded via server-side template rendering
        },

        /**
         * Switch between different view types by redirecting to the replay endpoint
         */
        switchView(viewType) {
            if (viewType === this.currentView || !this.availableViews.includes(viewType)) {
                return;
            }

            console.log(`Switching view from ${this.currentView} to ${viewType}`);

            // Navigate to the replay endpoint with the new view_type parameter
            const url = new URL(window.location);
            url.searchParams.set('view_type', viewType);
            window.location.href = url.toString();
        },

        /**
         * Download an artifact
         */
        async downloadArtifact(snapshotId, artifactType) {
            try {
                console.log(`Downloading ${artifactType} for snapshot:`, snapshotId);

                // Map display type back to actual artifact type for API
                const typeMapping = {
                    'wacz': 'archive.wacz',
                    'warc': 'archive.warc',
                    'singlefile': 'singlefile.html',
                    'screenshot': 'screenshot.png',
                    'metadata': 'metadata.json',
                    'dom-snapshot': 'dom-snapshot.html',
                    'gen-metadata': 'archive_generator_metadata.json',
                    'document': 'document.html'
                };

                const actualType = typeMapping[artifactType] || artifactType;
                const url = `/api/artifacts/serve?snapshot_id=${encodeURIComponent(snapshotId)}&type=${encodeURIComponent(actualType)}`;

                // Create a temporary link and click it to trigger download
                const link = document.createElement('a');
                link.href = url;
                link.download = ''; // Let browser determine filename
                link.style.display = 'none';

                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);

                // Show success toast
                if (typeof showToast === 'function') {
                    showToast(`Downloading ${artifactType.toUpperCase()} file...`);
                }

            } catch (error) {
                console.error('Download error:', error);

                if (typeof showToast === 'function') {
                    showToast(`Failed to download ${artifactType} file`);
                }
            }
        },

        /**
         * Format date for display
         */
        formatDate(timestamp) {
            if (!timestamp) return '';

            try {
                const date = new Date(timestamp);
                return date.toLocaleDateString('en-US', {
                    year: 'numeric',
                    month: 'long',
                    day: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit',
                    timeZoneName: 'short'
                });
            } catch (error) {
                console.warn('Invalid timestamp:', timestamp);
                return timestamp;
            }
        },

        /**
         * Get CSS classes for status code badge
         */
        getStatusBadgeClass(statusCode) {
            if (!statusCode) return 'bg-gray-100 text-gray-800';

            if (statusCode >= 200 && statusCode < 300) {
                return 'bg-green-100 text-green-800';
            } else if (statusCode >= 300 && statusCode < 400) {
                return 'bg-yellow-100 text-yellow-800';
            } else if (statusCode >= 400 && statusCode < 500) {
                return 'bg-red-100 text-red-800';
            } else if (statusCode >= 500) {
                return 'bg-purple-100 text-purple-800';
            } else {
                return 'bg-gray-100 text-gray-800';
            }
        },

        /**
         * Navigate back to archive list
         */
        navigateToArchive(urlId) {
            if (urlId) {
                window.location.href = `/archive/${urlId}`;
            } else {
                window.history.back();
            }
        },

    };
}

// Make function available globally for Alpine.js
window.replayPage = replayPage;