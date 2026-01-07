/**
 * Archive Form Alpine.js Component
 * Handles form validation, submission and feedback for archive requests.
 */

document.addEventListener('alpine:init', () => {
    Alpine.data('archiveForm', (initialDomains = []) => ({
        formData: {
            url: '',
            domain: ''
        },
        domains: initialDomains,
        submitting: false,
        error: null,

        get isValid() {
            if (!this.formData.url || !this.formData.domain) return false;

            const url = this.formData.url.trim();
            if (!url.startsWith('http://') && !url.startsWith('https://')) return false;

            return true;
        },

        async submitForm() {
            if (!this.isValid) return;

            this.submitting = true;
            this.error = null;

            try {
                const response = await fetch('/api/archive-request', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        url: this.formData.url.trim(),
                        domain: this.formData.domain
                    })
                });

                const data = await response.json();

                if (response.ok) {
                    // Success! Show toast and redirect to status page
                    if (window.showToast) {
                        window.showToast('Archive request submitted successfully!');
                    }

                    // Redirect to the status tracking page
                    // The status page will be implemented in a future task
                    setTimeout(() => {
                        window.location.href = `/status/${data.request_id}`;
                    }, 1000);
                } else {
                    // Handle validation errors or server errors
                    if (data.detail && Array.isArray(data.detail)) {
                        this.error = data.detail[0].msg || 'Validation error';
                    } else {
                        this.error = data.detail || 'Failed to submit request';
                    }
                }
            } catch (err) {
                this.error = 'Network error. Please try again later.';
                console.error('Submission error:', err);
            } finally {
                this.submitting = false;
            }
        }
    }));
});
