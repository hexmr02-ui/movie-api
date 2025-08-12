document.addEventListener('DOMContentLoaded', () => {
    const forms = {
        'src-form': 'src-response',
        'search-form': 'search-response',
        'download-links-form': 'download-links-response',
        'final-links-form': 'final-links-response'
    };

    for (const [formId, responseId] of Object.entries(forms)) {
        const form = document.getElementById(formId);
        if (form) {
            form.addEventListener('submit', async (event) => {
                event.preventDefault();
                const formData = new FormData(form);
                const params = new URLSearchParams(formData);
                const endpoint = `/api/${formId.split('-')[0]}`;
                const url = `${endpoint}?${params.toString()}`;
                
                const responseContainer = document.getElementById(responseId);
                responseContainer.textContent = 'Loading...';

                try {
                    const response = await fetch(url);
                    const data = await response.json();
                    responseContainer.textContent = JSON.stringify(data, null, 2);
                } catch (error) {
                    responseContainer.textContent = `Error: ${error.message}`;
                }
            });
        }
    }
});
