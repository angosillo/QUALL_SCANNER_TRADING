// MOMO Scanner Web — minimal client-side helpers

document.addEventListener('DOMContentLoaded', () => {
    // Symbol filter on scan detail
    const filterInput = document.getElementById('symbol-filter');
    if (filterInput) {
        filterInput.addEventListener('input', (e) => {
            const query = e.target.value.toLowerCase();
            document.querySelectorAll('.result-row').forEach(row => {
                const sym = row.dataset.symbol?.toLowerCase() || '';
                row.style.display = sym.includes(query) ? '' : 'none';
            });
        });
    }
});

function confirmDelete(name) {
    return confirm('¿Eliminar la watchlist "' + name + '"? Esta acción no se puede deshacer.');
}
