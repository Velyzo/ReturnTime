function showNotification(message) {
    const notification = document.getElementById('notification');
    notification.innerText = message;
    notification.classList.add('show');

    setTimeout(() => {
        notification.classList.remove('show');
    }, 3000);
}

document.getElementById('archive-form').addEventListener('submit', function(event) {
    event.preventDefault();

    const url = document.getElementById('url').value;

    if (!url) {
        showNotification("Please enter a URL to archive.");
        return;
    }

    const formData = new FormData();
    formData.append("url", url);

    fetch('/archive', {
        method: 'POST',
        body: formData,
    })
    .then(response => {
        if (response.ok) {
            return response.json();
        } else {
            throw new Error('Failed to archive the website');
        }
    })
    .then(data => {
        if (data && data.message) {
            showNotification(data.message);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showNotification('An error occurred while archiving the website.');
    });
});