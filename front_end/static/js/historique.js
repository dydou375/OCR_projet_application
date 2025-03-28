document.addEventListener('DOMContentLoaded', function() {
    console.log("Script chargé");

    const userEmail = localStorage.getItem('userEmail');

    function formatDate(dateStr) {
        if (!dateStr) return 'N/A';
        const date = new Date(dateStr);
        return date.toLocaleDateString('fr-FR');
    }

    function formatPrice(price) {
        if (!price) return '0,00 €';
        return new Intl.NumberFormat('fr-FR', {
            style: 'currency',
            currency: 'EUR',
            minimumFractionDigits: 2
        }).format(price);
    }

    function createFactureRow(facture) {
        return `
            <tr>
                <td>${formatDate(facture.date_facture)}</td>
                <td>${facture.nom_facture || 'Sans nom'}</td>
                <td>${facture.nom_personne || 'Non spécifié'}</td>
                <td class="text-end">${formatPrice(facture.total_facture)}</td>
                <td class="text-center">
                    <button class="btn btn-sm btn-info" onclick="showDetails(${facture.id})">
                        <i class="fas fa-eye"></i> Détails
                    </button>
                </td>
            </tr>
        `;
    }

    window.showDetails = function(factureId) {
        console.log("ID de la facture:", factureId);

        fetch(`/facture/${factureId}`)
            .then(response => response.json())
            .then(data => {
                console.log("Réponse du serveur:", data);

                if (data.success) {
                    const facture = data.facture_details[0];
                    console.log("Facture récupérée:", facture);

                    if (!facture) {
                        console.error("Aucune facture trouvée.");
                        return;
                    }

                    // Vérifiez si les articles existent
                    if (!facture.articles) {
                        console.error("Aucun article trouvé pour cette facture.");
                        return;
                    }

                    // Traiter les articles
                    const articlesHtml = facture.articles
                        .filter(article => article) // Filtrer les articles null
                        .map(article => `
                            <tr>
                                <td>${article.nom_article || 'Non spécifié'}</td>
                                <td class="text-center">${article.quantite || 0}</td>
                                <td class="text-end">${formatPrice(article.prix)}</td>
                                <td class="text-end">${formatPrice(article.quantite * article.prix)}</td>
                            </tr>
                        `).join('');

                    document.getElementById('articlesTableBody').innerHTML = articlesHtml;

                    const modalEl = document.getElementById('detailsModal');
                    const modal = new bootstrap.Modal(modalEl);
                    modal.show();
                } else {
                    console.error('Erreur lors de la récupération des détails de la facture:', data.error);
                }
            })
            .catch(error => {
                console.error('Erreur:', error);
            });
    };

    if (userEmail) {
        const encodedEmail = encodeURIComponent(userEmail);

        fetch(`/api/factures/${encodedEmail}`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    const facturesData = data.factures;
                    const tbody = document.querySelector('tbody');
                    tbody.innerHTML = facturesData.map(facture => createFactureRow(facture)).join('');
                } else {
                    throw new Error(data.error || 'Erreur lors du chargement des factures');
                }
            })
            .catch(error => {
                console.error('Erreur:', error);
                const errorMessage = document.createElement('div');
                errorMessage.className = 'alert alert-danger';
                errorMessage.textContent = 'Erreur lors du chargement des factures: ' + error.message;
                document.querySelector('.table-responsive').before(errorMessage);
            });
    } else {
        const notLoggedInMessage = document.createElement('div');
        notLoggedInMessage.className = 'alert alert-info';
        notLoggedInMessage.textContent = 'Veuillez vous connecter pour voir votre historique de factures.';
        document.querySelector('.table-responsive').before(notLoggedInMessage);
        document.querySelector('.table-responsive').style.display = 'none';
    }
});
