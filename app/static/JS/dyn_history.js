function searchByDate() {
    const searchTerm = document.getElementById('searchBar').value.trim().toLowerCase();
    const cards = document.querySelectorAll('.card');
    const noResultsMessage = document.querySelector('.no-results');
    let visibleCards = 0;

    cards.forEach(card => {
        const timestamp = card.getAttribute('data-timestamp').toLowerCase();

        if (timestamp.includes(searchTerm)) {
            card.style.display = 'block';
            visibleCards++;
        } else {
            card.style.display = 'none';
        }
    });

    noResultsMessage.style.display = visibleCards === 0 ? 'block' : 'none';
}