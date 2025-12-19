// Main JavaScript file for Civers Archive Web Interface

// Alpine.js components and utilities will be added here as needed

// Utility functions
const CiversApp = {
    // Show toast notification
    showToast: function(message, type = 'info') {
        // Simple toast implementation - will be enhanced later
        console.log(`[${type.toUpperCase()}] ${message}`);
    },
    
    // Format date for display
    formatDate: function(dateString) {
        const date = new Date(dateString);
        return date.toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    },
    
    // Format file size
    formatFileSize: function(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
};

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    console.log('Civers Archive Web Interface initialized');
});