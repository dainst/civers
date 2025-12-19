/**
 * Service worker for ReplayWeb.page WACZ processing
 *
 * This service worker handles WACZ file processing and replay functionality
 * by importing the ReplayWeb.page service worker implementation.
 *
 * It also bypasses SingleFile HTML requests to prevent interference.
 */

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