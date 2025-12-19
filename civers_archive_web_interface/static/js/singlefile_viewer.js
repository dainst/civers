/**
 * SingleFile Viewer Component
 * Handles iframe display of SingleFile HTML archives
 */

function singleFileViewer(snapshotId) {
    return {
        // Component state
        snapshotId: snapshotId,
        loading: true,
        error: null,
        isFullscreen: false,
        iframeSrc: `/api/artifacts/serve?snapshot_id=${encodeURIComponent(snapshotId)}&type=singlefile.html`,

        // Event listener references for cleanup
        fullscreenHandler: null,

        /**
         * Initialize the SingleFile viewer
         */
        init() {
            // Store handler references for cleanup
            this.fullscreenHandler = () => this.onFullscreenChange();
            document.addEventListener('fullscreenchange', this.fullscreenHandler);
        },

        /**
         * Handle iframe load success
         */
        onIframeLoad() {
            this.loading = false;
            this.error = null;
        },

        /**
         * Handle iframe load error
         */
        onIframeError() {
            this.loading = false;
            this.error = 'Failed to load SingleFile content';
        },

        /**
         * Retry loading the SingleFile content
         */
        retryLoad() {
            this.loading = true;
            this.error = null;

            // Add timestamp to force reload
            const separator = this.iframeSrc.includes('?') ? '&' : '?';
            const iframe = document.getElementById(`singlefile-frame-${this.snapshotId}`);
            if (iframe) {
                iframe.src = `${this.iframeSrc}${separator}_t=${Date.now()}`;
            }
        },

        /**
         * Toggle fullscreen mode
         */
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

        /**
         * Handle fullscreen change events
         */
        onFullscreenChange() {
            this.isFullscreen = !!document.fullscreenElement;
        },

        /**
         * Download SingleFile artifact
         */
        downloadSingleFile() {
            const url = `/api/artifacts/serve?snapshot_id=${encodeURIComponent(this.snapshotId)}&type=singlefile.html`;
            const link = document.createElement('a');
            link.href = url;
            link.download = `${this.snapshotId}_singlefile.html`;
            link.style.display = 'none';

            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        },

        /**
         * Cleanup event listeners when component is destroyed
         */
        destroy() {
            if (this.fullscreenHandler) {
                document.removeEventListener('fullscreenchange', this.fullscreenHandler);
                this.fullscreenHandler = null;
            }
        }
    };
}

// Make function available globally for Alpine.js
window.singleFileViewer = singleFileViewer;