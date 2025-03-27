document.addEventListener('DOMContentLoaded', function() {
    // Récupérer l'email de l'utilisateur du localStorage
    const userEmail = localStorage.getItem('userEmail');
    
    // Permettre l'accès à la page même sans connexion
    // if (!userEmail) {
    //     window.location.href = '/login';
    //     return;
    // }

    // Fonction pour formater la date
    function formatDate(dateStr) {
        if (!dateStr) return 'N/A';
        const date = new Date(dateStr);
        return date.toLocaleDateString('fr-FR');
    }

    // Fonction pour formater le prix
    function formatPrice(price) {
        if (!price) return '0,00 €';
        return new Intl.NumberFormat('fr-FR', {
            style: 'currency',
            currency: 'EUR',
            minimumFractionDigits: 2
        }).format(price);
    }

    // Fonction pour créer une ligne de facture
    function createFactureRow(facture) {
        return `
            <tr>
                <td>${formatDate(facture.date_facture)}</td>
                <td>${facture.nom_facture || 'Sans nom'}</td>
                <td>${facture.nom_personne || 'Non spécifié'}</td>
                <td class="text-end">${formatPrice(facture.total_facture)}</td>
                <td>
                    <button class="btn btn-sm btn-info" onclick="showDetails('${facture.nom_facture}')">
                        <i class="fas fa-eye"></i> Détails
                    </button>
                </td>
            </tr>
        `;
    }

    // Fonction pour calculer le total d'une ligne
    function calculateLineTotal(article) {
        return (article.quantite || 0) * (article.prix || 0);
    }

    // Fonction pour afficher les détails d'une facture
    window.showDetails = function(nomFacture) {
        const facture = facturesData.find(f => f.nom_facture === nomFacture);
        if (!facture) return;

        const articlesHtml = facture.articles
            .filter(article => article) // Filtrer les articles null
            .map(article => `
                <tr>
                    <td>${article.nom_article || 'Non spécifié'}</td>
                    <td class="text-center">${article.quantite || 0}</td>
                    <td class="text-end">${formatPrice(article.prix)}</td>
                    <td class="text-end">${formatPrice(calculateLineTotal(article))}</td>
                </tr>
            `).join('');

        const modalContent = `
            <div class="modal-header">
                <h5 class="modal-title">Détails de la facture</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
                <div class="row mb-3">
                    <div class="col-md-6">
                        <p><strong>N° Facture:</strong> ${facture.nom_facture}</p>
                        <p><strong>Date:</strong> ${formatDate(facture.date_facture)}</p>
                    </div>
                    <div class="col-md-6">
                        <p><strong>Client:</strong> ${facture.nom_personne}</p>
                        <p><strong>Email:</strong> ${facture.email_personne}</p>
                    </div>
                </div>

                <div class="table-responsive">
                    <table class="table table-striped">
                        <thead>
                            <tr>
                                <th>Produit</th>
                                <th class="text-center">Quantité</th>
                                <th class="text-end">Prix unitaire</th>
                                <th class="text-end">Total</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${articlesHtml}
                        </tbody>
                        <tfoot>
                            <tr>
                                <td colspan="3" class="text-end"><strong>Total TTC</strong></td>
                                <td class="text-end"><strong>${formatPrice(facture.total_facture)}</strong></td>
                            </tr>
                        </tfoot>
                    </table>
                </div>
            </div>
        `;

        const modalEl = document.getElementById('detailsModal');
        modalEl.querySelector('.modal-content').innerHTML = modalContent;
        const modal = new bootstrap.Modal(modalEl);
        modal.show();
    };

    // Charger les factures
    let facturesData = [];
    
    // Vérifier si l'utilisateur est connecté avant de charger les factures
    if (userEmail) {
        fetch(`/api/factures/${userEmail}`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    facturesData = data.factures;
                    const tbody = document.querySelector('tbody');
                    tbody.innerHTML = facturesData
                        .map(facture => createFactureRow(facture))
                        .join('');
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
        // Afficher un message si l'utilisateur n'est pas connecté
        const notLoggedInMessage = document.createElement('div');
        notLoggedInMessage.className = 'alert alert-info';
        notLoggedInMessage.textContent = 'Veuillez vous connecter pour voir votre historique de factures.';
        document.querySelector('.table-responsive').before(notLoggedInMessage);
        
        // Cacher le tableau si l'utilisateur n'est pas connecté
        document.querySelector('.table-responsive').style.display = 'none';
    }
});
