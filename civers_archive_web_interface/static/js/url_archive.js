/**
 * Alpine.js component for URL Archive page functionality
 * Handles snapshot loading, sorting, filtering, and pagination
 */

function urlArchive(urlId) {
    return {
        // State
        urlId: urlId,
        loading: true,
        error: null,
        snapshots: [],

        // Pagination
        currentPage: 1,
        totalPages: 0,
        totalCount: 0,
        limit: 50,

        // Sorting and filtering
        sortBy: 'timestamp',

        /**
         * Initialize the component
         */
        init() {
            console.log('Initializing URL Archive for:', this.urlId);
            this.loadSnapshots();
        },

        /**
         * Load snapshots from the API
         */
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

                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({}));
                    throw new Error(errorData.message || `HTTP ${response.status}: ${response.statusText}`);
                }

                const data = await response.json();

                if (!data.success) {
                    throw new Error(data.message || 'Failed to load snapshots');
                }

                // Transform the API response to match template expectations
                this.snapshots = (data.data || []).map(snapshot => ({
                    ...snapshot,
                    artifacts: this.transformArtifacts(snapshot.available_artifacts || [])
                }));
                this.totalPages = data.pagination?.total_pages || 0;
                this.totalCount = data.pagination?.total_count || 0;

                console.log(`Loaded ${this.snapshots.length} snapshots (page ${this.currentPage}/${this.totalPages})`);

                // Show success toast
                if (typeof showToast === 'function') {
                    showToast(`Loaded ${this.snapshots.length} snapshots`);
                }

            } catch (error) {
                console.error('Error loading snapshots:', error);
                this.error = error.message || 'Failed to load snapshots';
                this.snapshots = [];
                this.totalPages = 0;
                this.totalCount = 0;
            } finally {
                this.loading = false;
            }
        },

        /**
         * Go to specific page
         */
        async goToPage(page) {
            if (page === this.currentPage || page < 1 || page > this.totalPages) {
                return;
            }

            this.currentPage = page;
            await this.loadSnapshots();

            // Scroll to top of content
            document.getElementById('main-content')?.scrollIntoView({ behavior: 'smooth' });
        },

        /**
         * Go to previous page
         */
        async previousPage() {
            if (this.currentPage > 1) {
                await this.goToPage(this.currentPage - 1);
            }
        },

        /**
         * Go to next page
         */
        async nextPage() {
            if (this.currentPage < this.totalPages) {
                await this.goToPage(this.currentPage + 1);
            }
        },

        /**
         * Generate page numbers for pagination
         */
        getPageNumbers() {
            const current = this.currentPage;
            const total = this.totalPages;
            const delta = 2; // Show 2 pages on each side of current

            if (total <= 7) {
                // Show all pages if total is small
                return Array.from({ length: total }, (_, i) => i + 1);
            }

            const pages = [];

            // Always show first page
            pages.push(1);

            if (current - delta > 2) {
                pages.push('...');
            }

            // Show pages around current
            const start = Math.max(2, current - delta);
            const end = Math.min(total - 1, current + delta);

            for (let i = start; i <= end; i++) {
                pages.push(i);
            }

            if (current + delta < total - 1) {
                pages.push('...');
            }

            // Always show last page if it's different from first
            if (total > 1) {
                pages.push(total);
            }

            return pages;
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
                    month: 'short',
                    day: 'numeric'
                });
            } catch (error) {
                console.warn('Invalid timestamp:', timestamp);
                return timestamp;
            }
        },

        /**
         * Format time for display
         */
        formatTime(timestamp) {
            if (!timestamp) return '';

            try {
                const date = new Date(timestamp);
                return date.toLocaleTimeString('en-US', {
                    hour: '2-digit',
                    minute: '2-digit',
                    second: '2-digit'
                });
            } catch (error) {
                console.warn('Invalid timestamp:', timestamp);
                return '';
            }
        },

        /**
         * Transform available_artifacts array to artifacts objects.
         * Only returns artifacts that actually EXIST (filters out non-existent ones).
         */
        transformArtifacts(availableArtifacts) {
            // Map actual artifact filenames to display names
            const filenameToDisplayType = {
                'archive.wacz': 'wacz',
                'archive.warc': 'warc',
                'singlefile.html': 'singlefile',
                'screenshot.png': 'screenshot',
                'metadata.json': 'metadata',
                'dom-snapshot.html': 'dom-snapshot',
                'archive_generator_metadata.json': 'gen-metadata'
                // Note: 'document.html' removed as it's rarely used and confuses users
            };

            // Only return artifacts that actually exist
            return availableArtifacts
                .filter(artifact => filenameToDisplayType[artifact] !== undefined)
                .map(artifact => ({
                    type: filenameToDisplayType[artifact],
                    exists: true  // All returned artifacts exist
                }));
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
        }
    };
}

// Make function available globally for Alpine.js
window.urlArchive = urlArchive;