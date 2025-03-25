// Variables globales
let selectedFiles = []; // Tableau pour stocker plusieurs fichiers
let invoiceData = null;
let currentInvoiceIndex = 0; // Index de la facture actuellement affichée

// Initialisation lorsque le DOM est chargé
document.addEventListener('DOMContentLoaded', function() {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const scanButton = document.getElementById('scanButton');
    const fileInfo = document.getElementById('fileInfo');
    
    // Configuration du glisser-déposer
    dropZone.addEventListener('dragover', function(e) {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });
    
    dropZone.addEventListener('dragleave', function() {
        dropZone.classList.remove('dragover');
    });
    
    dropZone.addEventListener('drop', function(e) {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        
        if (e.dataTransfer.files.length) {
            handleFileSelection(e.dataTransfer.files);
        }
    });
    
    // Gestion de la sélection de fichier via le bouton
    fileInput.addEventListener('change', function() {
        if (fileInput.files.length) {
            handleFileSelection(fileInput.files);
        }
    });
    
    // Gestion du bouton de scan
    scanButton.addEventListener('click', function() {
        if (selectedFiles.length > 0) {
            scanInvoices();
        }
    });
});

// Gestion de la sélection de fichiers
function handleFileSelection(files) {
    const fileInfo = document.getElementById('fileInfo');
    const scanButton = document.getElementById('scanButton');
    
    // Réinitialiser la liste des fichiers sélectionnés
    selectedFiles = [];
    
    // Vérifier chaque fichier
    let fileListHtml = '<div class="alert alert-info"><strong>Fichiers sélectionnés:</strong><ul>';
    let allFilesValid = true;
    
    for (let i = 0; i < files.length; i++) {
        const file = files[i];
        // Vérifier le type de fichier
        const acceptedTypes = ['image/jpeg', 'image/png', 'application/pdf'];
        if (!acceptedTypes.includes(file.type)) {
            fileListHtml += `<li class="text-danger">${file.name} - Format non supporté</li>`;
            allFilesValid = false;
        } else {
            selectedFiles.push(file);
            fileListHtml += `<li>${file.name} - ${formatFileSize(file.size)}</li>`;
        }
    }
    
    fileListHtml += '</ul></div>';
    
    if (selectedFiles.length === 0) {
        fileInfo.innerHTML = '<div class="alert alert-danger">Aucun fichier valide sélectionné. Veuillez sélectionner des images JPG, PNG ou des PDF.</div>';
        scanButton.disabled = true;
    } else {
        fileInfo.innerHTML = fileListHtml;
        if (!allFilesValid) {
            fileInfo.innerHTML += '<div class="alert alert-warning">Certains fichiers ont été ignorés car leur format n\'est pas supporté.</div>';
        }
        scanButton.disabled = false;
        
        // Afficher le nombre de fichiers à analyser
        scanButton.textContent = `Scanner ${selectedFiles.length} facture${selectedFiles.length > 1 ? 's' : ''}`;
    }
}

// Formatage de la taille du fichier
function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' octets';
    else if (bytes < 1048576) return (bytes / 1024).toFixed(2) + ' Ko';
    else return (bytes / 1048576).toFixed(2) + ' Mo';
}

// Analyse des factures
function scanInvoices() {
    const loadingSpinner = document.getElementById('loadingSpinner');
    const resultContainer = document.getElementById('resultContainer');
    const invoiceDataContainer = document.getElementById('invoice-data-container');
    
    // Afficher le spinner de chargement
    loadingSpinner.classList.remove('d-none');
    resultContainer.innerHTML = '';
    invoiceDataContainer.innerHTML = '';
    
    // Créer un conteneur pour les résultats de toutes les factures
    resultContainer.innerHTML = `
        <div class="card mb-4">
            <div class="card-header">
                <h4>Résultats de l'analyse (0/${selectedFiles.length})</h4>
            </div>
            <div class="card-body" id="invoices-results">
                <div class="progress mb-3">
                    <div class="progress-bar" role="progressbar" style="width: 0%;" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100">0%</div>
                </div>
                <div id="invoices-list"></div>
            </div>
        </div>
    `;
    
    // Traiter chaque facture séquentiellement
    processNextInvoice(0, selectedFiles.length);
}

// Traiter la facture suivante
function processNextInvoice(index, total) {
    if (index >= total) {
        // Toutes les factures ont été traitées
        document.getElementById('loadingSpinner').classList.add('d-none');
        updateProgressBar(100, total, total);
        
        // Ajouter un bouton pour enregistrer toutes les factures dans la base de données
        const invoicesList = document.getElementById('invoices-list');
        const saveAllButton = document.createElement('div');
        saveAllButton.className = 'text-center mt-4';
        saveAllButton.innerHTML = `
            <button id="saveAllToDbButton" class="btn btn-lg btn-primary">
                Enregistrer toutes les factures dans la base de données
            </button>
        `;
        
        invoicesList.appendChild(saveAllButton);
        
        // Ajouter un écouteur d'événement au bouton
        document.getElementById('saveAllToDbButton').addEventListener('click', saveAllInvoicesToDatabase);
        
        return;
    }
    
    const file = selectedFiles[index];
    const invoicesList = document.getElementById('invoices-list');
    const ocrService = document.getElementById('ocr-service').value;
    
    // Mettre à jour la barre de progression
    updateProgressBar(Math.round((index / total) * 100), index, total);
    
    // Créer un élément pour cette facture
    const invoiceElement = document.createElement('div');
    invoiceElement.className = 'invoice-result mb-3';
    invoiceElement.id = `invoice-result-${index}`;
    invoiceElement.innerHTML = `
        <div class="card">
            <div class="card-header d-flex justify-content-between align-items-center">
                <h5 class="mb-0">${file.name}</h5>
                <div class="spinner-border spinner-border-sm" role="status">
                    <span class="visually-hidden">Chargement...</span>
                </div>
            </div>
            <div class="card-body">
                <p>Analyse en cours...</p>
            </div>
        </div>
    `;
    invoicesList.appendChild(invoiceElement);
    
    // Créer un FormData pour l'envoi du fichier
    const formData = new FormData();
    formData.append('file', file);
    formData.append('ocr_service', ocrService);
    
    // Envoyer la requête au serveur
    fetch('/api/scan-invoice', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        // Mettre à jour l'élément de la facture
        const invoiceResult = document.getElementById(`invoice-result-${index}`);
        const cardHeader = invoiceResult.querySelector('.card-header');
        const cardBody = invoiceResult.querySelector('.card-body');
        
        // Supprimer le spinner
        cardHeader.querySelector('.spinner-border').remove();
        
        if (data.success) {
            // Ajouter un bouton pour afficher les détails
            cardHeader.innerHTML += `
                <button class="btn btn-sm btn-primary view-invoice-btn" data-index="${index}">
                    Voir les détails
                </button>
            `;
            
            // Stocker les données pour une utilisation ultérieure
            selectedFiles[index].data = data.data;
            
            // Afficher un résumé des données
            cardBody.innerHTML = `
                <p><strong>Numéro de facture:</strong> ${data.data.invoice_number || 'Non détecté'}</p>
                <p><strong>Date:</strong> ${data.data.issue_date || 'Non détectée'}</p>
                <p><strong>Client:</strong> ${data.data.client || 'Non détecté'}</p>
                <p><strong>Total:</strong> ${data.data.total ? data.data.total.toFixed(2) + ' €' : 'Non détecté'}</p>
            `;
            
            // Ajouter un écouteur d'événement pour le bouton de détails
            invoiceResult.querySelector('.view-invoice-btn').addEventListener('click', function() {
                displayInvoiceData(data.data, index);
            });
        } else {
            // Afficher l'erreur
            cardHeader.innerHTML += `
                <span class="badge bg-danger">Échec</span>
            `;
            
            cardBody.innerHTML = `
                <div class="alert alert-danger">
                    ${data.error || "Une erreur s'est produite lors de l'analyse de la facture."}
                </div>
            `;
        }
        
        // Traiter la facture suivante
        processNextInvoice(index + 1, total);
    })
    .catch(error => {
        // Mettre à jour l'élément de la facture en cas d'erreur
        const invoiceResult = document.getElementById(`invoice-result-${index}`);
        const cardHeader = invoiceResult.querySelector('.card-header');
        const cardBody = invoiceResult.querySelector('.card-body');
        
        // Supprimer le spinner
        cardHeader.querySelector('.spinner-border').remove();
        
        // Afficher l'erreur
        cardHeader.innerHTML += `
            <span class="badge bg-danger">Erreur</span>
        `;
        
        cardBody.innerHTML = `
            <div class="alert alert-danger">
                Impossible de communiquer avec le serveur: ${error.message}
            </div>
        `;
        
        // Traiter la facture suivante
        processNextInvoice(index + 1, total);
    });
}

// Mettre à jour la barre de progression
function updateProgressBar(percentage, current, total) {
    const progressBar = document.querySelector('.progress-bar');
    const header = document.querySelector('.card-header h4');
    
    progressBar.style.width = percentage + '%';
    progressBar.setAttribute('aria-valuenow', percentage);
    progressBar.textContent = percentage + '%';
    
    header.textContent = `Résultats de l'analyse (${current}/${total})`;
}

// Afficher les données de la facture dans un formulaire modifiable
function displayInvoiceData(data, index) {
    const container = document.getElementById('invoice-data-container');
    currentInvoiceIndex = index;
    
    // Créer un formulaire pour afficher et modifier les données
    let html = `
        <div class="invoice-data">
            <div class="d-flex justify-content-between align-items-center mb-3">
                <h3>Données extraites de la facture</h3>
                <span class="badge bg-primary">${selectedFiles[index].name}</span>
            </div>
            <form id="invoice-form">
                <div class="form-group mb-3">
                    <label for="invoice-number">Numéro de facture:</label>
                    <input type="text" id="invoice-number" name="invoice_number" value="${data.invoice_number || ''}" class="form-control">
                </div>
                
                <div class="form-group mb-3">
                    <label for="issue-date">Date d'émission:</label>
                    <input type="date" id="issue-date" name="issue_date" value="${data.issue_date || ''}" class="form-control">
                </div>
                
                <div class="form-group mb-3">
                    <label for="client-name">Client:</label>
                    <input type="text" id="client-name" name="client" value="${data.client || ''}" class="form-control">
                </div>
                
                <div class="form-group mb-3">
                    <label for="client-email">Email:</label>
                    <input type="email" id="client-email" name="email" value="${data.email || ''}" class="form-control">
                </div>
                
                <div class="form-group mb-3">
                    <label for="client-address">Adresse:</label>
                    <textarea id="client-address" name="address" class="form-control" rows="3">${data.address || ''}</textarea>
                </div>
                
                <h4 class="mt-4">Articles</h4>
                <div id="items-container">
    `;
    
    // Ajouter les articles
    if (data.items && data.items.length > 0) {
        data.items.forEach((item, index) => {
            html += `
                <div class="item-row" data-index="${index}">
                    <div class="form-group mb-2">
                        <label for="item-name-${index}">Article:</label>
                        <input type="text" id="item-name-${index}" name="items[${index}][name]" value="${item.name || ''}" class="form-control">
                    </div>
                    
                    <div class="form-row mb-2">
                        <div class="form-group col-md-4">
                            <label for="item-quantity-${index}">Quantité:</label>
                            <input type="number" id="item-quantity-${index}" name="items[${index}][quantity]" value="${item.quantity || 0}" class="form-control item-quantity" data-index="${index}">
                        </div>
                        
                        <div class="form-group col-md-4">
                            <label for="item-price-${index}">Prix unitaire (€):</label>
                            <input type="number" step="0.01" id="item-price-${index}" name="items[${index}][unit_price]" value="${item.unit_price || 0}" class="form-control item-price" data-index="${index}">
                        </div>
                        
                        <div class="form-group col-md-4">
                            <label for="item-total-${index}">Total (€):</label>
                            <input type="number" step="0.01" id="item-total-${index}" name="items[${index}][total_price]" value="${item.total_price || 0}" class="form-control item-total" readonly>
                        </div>
                    </div>
                    
                    <button type="button" class="btn btn-danger btn-sm remove-item mb-3" data-index="${index}">Supprimer</button>
                    <hr>
                </div>
            `;
        });
    } else {
        html += `<p>Aucun article trouvé</p>`;
    }
    
    html += `
                </div>
                
                <button type="button" id="add-item-btn" class="btn btn-secondary mt-3">Ajouter un article</button>
                
                <div class="form-group mt-4">
                    <label for="total-amount">Montant total (€):</label>
                    <input type="number" step="0.01" id="total-amount" name="total" value="${data.total || 0}" class="form-control">
                </div>
                
                <div class="form-group mt-4">
                    <button type="button" id="save-invoice-btn" class="btn btn-primary">Enregistrer</button>
                    <button type="button" id="cancel-btn" class="btn btn-secondary ms-2">Annuler</button>
                </div>
            </form>
            
            <div class="mt-4">
                <h4>Informations OCR</h4>
                <p><strong>Service utilisé:</strong> ${data.ocr_service?.service || 'Non spécifié'}</p>
                <p><strong>Temps de traitement:</strong> ${data.processing_time ? (data.processing_time.toFixed(2) + ' secondes') : 'Non spécifié'}</p>
                <p><strong>Confiance:</strong> ${data.ocr_service?.confidence ? ((data.ocr_service.confidence * 100).toFixed(2) + '%') : 'Non spécifié'}</p>
            </div>
        </div>
    `;
    
    container.innerHTML = html;
    
    // Ajouter les écouteurs d'événements
    setupEventListeners();
}

// Configurer les écouteurs d'événements pour le formulaire
function setupEventListeners() {
    // Mettre à jour les totaux des articles lorsque la quantité ou le prix change
    document.querySelectorAll('.item-quantity, .item-price').forEach(input => {
        input.addEventListener('change', updateItemTotal);
    });
    
    // Bouton pour ajouter un nouvel article
    document.getElementById('add-item-btn').addEventListener('click', addNewItem);
    
    // Boutons pour supprimer des articles
    document.querySelectorAll('.remove-item').forEach(button => {
        button.addEventListener('click', removeItem);
    });
    
    // Bouton pour enregistrer les données
    document.getElementById('save-invoice-btn').addEventListener('click', saveInvoiceData);
    
    // Bouton pour annuler
    document.getElementById('cancel-btn').addEventListener('click', cancelInvoiceEdit);
}

// Mettre à jour le total d'un article
function updateItemTotal(event) {
    const index = event.target.dataset.index;
    const quantityInput = document.getElementById(`item-quantity-${index}`);
    const priceInput = document.getElementById(`item-price-${index}`);
    const totalInput = document.getElementById(`item-total-${index}`);
    
    const quantity = parseFloat(quantityInput.value) || 0;
    const price = parseFloat(priceInput.value) || 0;
    const total = quantity * price;
    
    totalInput.value = total.toFixed(2);
    
    // Mettre à jour le total global
    updateGlobalTotal();
}

// Mettre à jour le total global
function updateGlobalTotal() {
    const totalInputs = document.querySelectorAll('.item-total');
    let globalTotal = 0;
    
    totalInputs.forEach(input => {
        globalTotal += parseFloat(input.value) || 0;
    });
    
    document.getElementById('total-amount').value = globalTotal.toFixed(2);
}

// Ajouter un nouvel article
function addNewItem() {
    const itemsContainer = document.getElementById('items-container');
    const itemCount = document.querySelectorAll('.item-row').length;
    
    const newItemHtml = `
        <div class="item-row" data-index="${itemCount}">
            <div class="form-group mb-2">
                <label for="item-name-${itemCount}">Article:</label>
                <input type="text" id="item-name-${itemCount}" name="items[${itemCount}][name]" class="form-control">
            </div>
            
            <div class="form-row mb-2">
                <div class="form-group col-md-4">
                    <label for="item-quantity-${itemCount}">Quantité:</label>
                    <input type="number" id="item-quantity-${itemCount}" name="items[${itemCount}][quantity]" value="1" class="form-control item-quantity" data-index="${itemCount}">
                </div>
                
                <div class="form-group col-md-4">
                    <label for="item-price-${itemCount}">Prix unitaire (€):</label>
                    <input type="number" step="0.01" id="item-price-${itemCount}" name="items[${itemCount}][unit_price]" value="0" class="form-control item-price" data-index="${itemCount}">
                </div>
                
                <div class="form-group col-md-4">
                    <label for="item-total-${itemCount}">Total (€):</label>
                    <input type="number" step="0.01" id="item-total-${itemCount}" name="items[${itemCount}][total_price]" value="0" class="form-control item-total" readonly>
                </div>
            </div>
            
            <button type="button" class="btn btn-danger btn-sm remove-item mb-3" data-index="${itemCount}">Supprimer</button>
            <hr>
        </div>
    `;
    
    // Ajouter le nouvel article au conteneur
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = newItemHtml;
    itemsContainer.appendChild(tempDiv.firstElementChild);
    
    // Ajouter les écouteurs d'événements
    document.querySelectorAll(`.item-quantity[data-index="${itemCount}"], .item-price[data-index="${itemCount}"]`).forEach(input => {
        input.addEventListener('change', updateItemTotal);
    });
    
    document.querySelector(`.remove-item[data-index="${itemCount}"]`).addEventListener('click', removeItem);
    
    // Mettre à jour le total
    updateItemTotal({target: {dataset: {index: itemCount}}});
}

// Supprimer un article
function removeItem(event) {
    const index = event.target.dataset.index;
    const itemRow = document.querySelector(`.item-row[data-index="${index}"]`);
    
    if (itemRow) {
        itemRow.remove();
        updateGlobalTotal();
    }
}

// Enregistrer les données de la facture
function saveInvoiceData() {
    const form = document.getElementById('invoice-form');
    
    // Créer un objet pour stocker les données du formulaire
    const formData = {
        invoice_number: document.getElementById('invoice-number').value,
        issue_date: document.getElementById('issue-date').value,
        client: document.getElementById('client-name').value,
        email: document.getElementById('client-email').value,
        address: document.getElementById('client-address').value,
        total: parseFloat(document.getElementById('total-amount').value) || 0,
        items: []
    };
    
    // Récupérer les articles
    const itemRows = document.querySelectorAll('.item-row');
    itemRows.forEach(row => {
        const index = row.dataset.index;
        
        formData.items.push({
            name: document.getElementById(`item-name-${index}`).value,
            quantity: parseInt(document.getElementById(`item-quantity-${index}`).value) || 0,
            unit_price: parseFloat(document.getElementById(`item-price-${index}`).value) || 0,
            total_price: parseFloat(document.getElementById(`item-total-${index}`).value) || 0
        });
    });
    
    // Envoyer les données au serveur
    fetch('/api/save-invoice-data', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(formData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Mettre à jour les données de la facture dans le tableau selectedFiles
            if (selectedFiles[currentInvoiceIndex]) {
                selectedFiles[currentInvoiceIndex].data = formData;
                
                // Mettre à jour le résumé de la facture dans la liste
                updateInvoiceSummary(currentInvoiceIndex, formData);
            }
            
            // Afficher un message de succès temporaire
            const successAlert = document.createElement('div');
            successAlert.className = 'alert alert-success alert-dismissible fade show';
            successAlert.innerHTML = `
                <strong>Succès!</strong> Les données de la facture ont été enregistrées.
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            `;
            
            const resultContainer = document.getElementById('resultContainer');
            // Insérer l'alerte au début du conteneur de résultats
            if (resultContainer.firstChild) {
                resultContainer.insertBefore(successAlert, resultContainer.firstChild);
            } else {
                resultContainer.appendChild(successAlert);
            }
            
            // Fermer l'alerte après 3 secondes
            setTimeout(() => {
                if (successAlert.parentNode) {
                    successAlert.parentNode.removeChild(successAlert);
                }
            }, 3000);
            
            // Masquer le formulaire et revenir à la liste des factures
            document.getElementById('invoice-data-container').innerHTML = '';
            
            // S'assurer que la liste des factures est visible
            const invoicesResults = document.getElementById('invoices-results');
            if (invoicesResults) {
                invoicesResults.scrollIntoView({ behavior: 'smooth' });
            }
        } else {
            // Afficher un message d'erreur
            const errorAlert = document.createElement('div');
            errorAlert.className = 'alert alert-danger';
            errorAlert.innerHTML = `
                <h4>Erreur lors de l'enregistrement</h4>
                <p>${data.error || "Une erreur s'est produite lors de l'enregistrement des données."}</p>
            `;
            
            const resultContainer = document.getElementById('resultContainer');
            resultContainer.innerHTML = '';
            resultContainer.appendChild(errorAlert);
        }
    })
    .catch(error => {
        // Afficher l'erreur
        const errorAlert = document.createElement('div');
        errorAlert.className = 'alert alert-danger';
        errorAlert.innerHTML = `
            <h4>Erreur de connexion</h4>
            <p>Impossible de communiquer avec le serveur: ${error.message}</p>
        `;
        
        const resultContainer = document.getElementById('resultContainer');
        resultContainer.innerHTML = '';
        resultContainer.appendChild(errorAlert);
    });
}

// Mettre à jour le résumé d'une facture dans la liste
function updateInvoiceSummary(index, data) {
    const invoiceResult = document.getElementById(`invoice-result-${index}`);
    if (!invoiceResult) return;
    
    const cardBody = invoiceResult.querySelector('.card-body');
    if (!cardBody) return;
    
    // Mettre à jour le résumé avec les nouvelles données
    cardBody.innerHTML = `
        <p><strong>Numéro de facture:</strong> ${data.invoice_number || 'Non détecté'}</p>
        <p><strong>Date:</strong> ${data.issue_date || 'Non détectée'}</p>
        <p><strong>Client:</strong> ${data.client || 'Non détecté'}</p>
        <p><strong>Total:</strong> ${data.total ? data.total.toFixed(2) + ' €' : 'Non détecté'}</p>
        <p class="text-success"><small><i>Modifié</i></small></p>
    `;
}

// Annuler les modifications et revenir à la liste des factures
function cancelInvoiceEdit() {
    // Masquer le formulaire
    document.getElementById('invoice-data-container').innerHTML = '';
    
    // S'assurer que la liste des factures est visible
    const invoicesResults = document.getElementById('invoices-results');
    if (invoicesResults) {
        invoicesResults.scrollIntoView({ behavior: 'smooth' });
    }
}

// Envoyer toutes les factures à la base de données
function saveAllInvoicesToDatabase() {
    const loadingSpinner = document.getElementById('loadingSpinner');
    const resultContainer = document.getElementById('resultContainer');
    
    // Vérifier s'il y a des factures à enregistrer
    const invoicesWithData = selectedFiles.filter(file => file.data);
    
    if (invoicesWithData.length === 0) {
        // Afficher un message d'erreur si aucune facture n'a été analysée
        const errorAlert = document.createElement('div');
        errorAlert.className = 'alert alert-warning';
        errorAlert.innerHTML = `
            <h4>Aucune donnée à enregistrer</h4>
            <p>Veuillez d'abord analyser au moins une facture.</p>
        `;
        
        resultContainer.prepend(errorAlert);
        
        // Supprimer l'alerte après 3 secondes
        setTimeout(() => {
            if (errorAlert.parentNode) {
                errorAlert.parentNode.removeChild(errorAlert);
            }
        }, 3000);
        
        return;
    }
    
    // Afficher le spinner de chargement
    loadingSpinner.classList.remove('d-none');
    
    // Préparer les données à envoyer
    const invoicesData = invoicesWithData.map(file => {
        return {
            filename: file.name,
            data: file.data
        };
    });
    
    // Envoyer les données au serveur
    fetch('/api/save-invoices-to-database', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ invoices: invoicesData })
    })
    .then(response => response.json())
    .then(data => {
        // Masquer le spinner
        loadingSpinner.classList.add('d-none');
        
        if (data.success) {
            // Afficher un message de succès
            const successAlert = document.createElement('div');
            successAlert.className = 'alert alert-success';
            successAlert.innerHTML = `
                <h4>Données enregistrées avec succès!</h4>
                <p>${data.message || `${invoicesWithData.length} facture(s) enregistrée(s) dans la base de données.`}</p>
            `;
            
            resultContainer.prepend(successAlert);
            
            // Ajouter un badge "Enregistré" à chaque facture
            invoicesWithData.forEach((file, index) => {
                const invoiceResult = document.getElementById(`invoice-result-${index}`);
                if (invoiceResult) {
                    const cardHeader = invoiceResult.querySelector('.card-header');
                    if (cardHeader) {
                        // Vérifier si le badge existe déjà
                        if (!cardHeader.querySelector('.badge-saved')) {
                            const savedBadge = document.createElement('span');
                            savedBadge.className = 'badge bg-success ms-2 badge-saved';
                            savedBadge.textContent = 'Enregistré';
                            cardHeader.appendChild(savedBadge);
                        }
                    }
                }
            });
            
            // Rediriger vers la page de gestion des factures après 2 secondes
            setTimeout(() => {
                // Décommenter la ligne suivante pour rediriger vers une autre page
                // window.location.href = '/invoices';
                
                // Ou simplement supprimer l'alerte
                if (successAlert.parentNode) {
                    successAlert.parentNode.removeChild(successAlert);
                }
            }, 3000);
        } else {
            // Afficher un message d'erreur
            const errorAlert = document.createElement('div');
            errorAlert.className = 'alert alert-danger';
            errorAlert.innerHTML = `
                <h4>Erreur lors de l'enregistrement</h4>
                <p>${data.error || "Une erreur s'est produite lors de l'enregistrement des données."}</p>
            `;
            
            resultContainer.prepend(errorAlert);
            
            // Supprimer l'alerte après 5 secondes
            setTimeout(() => {
                if (errorAlert.parentNode) {
                    errorAlert.parentNode.removeChild(errorAlert);
                }
            }, 5000);
        }
    })
    .catch(error => {
        // Masquer le spinner et le message de chargement
        loadingSpinner.classList.add('d-none');
        if (loadingMessage.parentNode) {
            loadingMessage.parentNode.removeChild(loadingMessage);
        }
        
        // Afficher une erreur détaillée
        const errorAlert = document.createElement('div');
        errorAlert.className = 'alert alert-danger';
        
        // Essayer d'obtenir plus de détails sur l'erreur
        let errorDetails = error.message;
        if (error.response) {
            try {
                // Essayer de parser la réponse JSON
                error.response.json().then(data => {
                    errorDetails = data.error || errorDetails;
                    updateErrorMessage(errorDetails);
                }).catch(() => {
                    // Si ce n'est pas du JSON, utiliser le texte brut
                    error.response.text().then(text => {
                        errorDetails = text || errorDetails;
                        updateErrorMessage(errorDetails);
                    });
                });
            } catch (e) {
                console.error("Impossible de lire les détails de l'erreur:", e);
            }
        }
        
        function updateErrorMessage(details) {
            errorAlert.innerHTML = `
                <h4><i class="fas fa-exclamation-circle me-2"></i> Erreur de serveur</h4>
                <p>Une erreur s'est produite lors de l'enregistrement dans la base de données:</p>
                <div class="bg-light p-2 mb-2 rounded">
                    <code>${details}</code>
                </div>
                <p class="mb-0">Veuillez contacter l'administrateur système avec ces informations.</p>
            `;
        }
        
        // Message initial en attendant plus de détails
        updateErrorMessage(errorDetails);
        
        resultContainer.prepend(errorAlert);
        
        // Faire défiler jusqu'au message d'erreur
        errorAlert.scrollIntoView({ behavior: 'smooth' });
        
        // Ne pas supprimer automatiquement l'erreur pour permettre à l'utilisateur de la lire
    });
}

// Fonction pour supprimer un fichier de la liste des fichiers sélectionnés
function removeSelectedFile(index) {
    console.log("Tentative de suppression du fichier sélectionné à l'index:", index);
    
    // Vérifier que l'index est valide
    if (index < 0 || index >= selectedFiles.length) {
        console.error("Index de fichier invalide:", index);
        return;
    }
    
    // Récupérer le nom du fichier pour l'afficher dans le message de confirmation
    const fileName = selectedFiles[index].name;
    
    // Supprimer le fichier de la liste
    selectedFiles.splice(index, 1);
    
    // Mettre à jour l'affichage des fichiers sélectionnés
    updateSelectedFilesList();
    
    // Si tous les fichiers ont été supprimés, masquer le bouton d'analyse
    if (selectedFiles.length === 0) {
        document.getElementById('scan-button').classList.add('d-none');
    }
    
    // Afficher un message de confirmation
    const alertContainer = document.createElement('div');
    alertContainer.className = 'alert alert-success alert-dismissible fade show mt-2';
    alertContainer.innerHTML = `
        <strong>Succès!</strong> Le fichier "${fileName}" a été retiré de la liste.
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    // Insérer l'alerte après le conteneur de fichiers sélectionnés
    const selectedFilesContainer = document.getElementById('selected-files-container');
    selectedFilesContainer.parentNode.insertBefore(alertContainer, selectedFilesContainer.nextSibling);
    
    // Supprimer l'alerte après 3 secondes
    setTimeout(() => {
        if (alertContainer.parentNode) {
            alertContainer.parentNode.removeChild(alertContainer);
        }
    }, 3000);
    
    console.log("Fichier supprimé avec succès:", fileName);
}

// Mettre à jour la fonction updateSelectedFilesList pour ajouter des boutons de suppression
function updateSelectedFilesList() {
    const container = document.getElementById('selected-files-container');
    
    if (selectedFiles.length === 0) {
        container.innerHTML = '<p class="text-muted">Aucun fichier sélectionné</p>';
        return;
    }
    
    let html = '<ul class="list-group">';
    
    selectedFiles.forEach((file, index) => {
        html += `
            <li class="list-group-item d-flex justify-content-between align-items-center">
                <span>
                    <i class="fas fa-file-pdf text-danger me-2"></i>
                    ${file.name}
                </span>
                <button type="button" class="btn btn-sm btn-outline-danger remove-selected-file-btn" data-index="${index}" title="Retirer ce fichier">
                    <i class="fas fa-times"></i>
                </button>
            </li>
        `;
    });
    
    html += '</ul>';
    container.innerHTML = html;
    
    // Ajouter des écouteurs d'événements aux boutons de suppression
    document.querySelectorAll('.remove-selected-file-btn').forEach(button => {
        button.addEventListener('click', function() {
            const index = parseInt(this.dataset.index);
            console.log("Bouton de suppression cliqué pour l'index:", index);
            removeSelectedFile(index);
        });
    });
}

// Modifier la fonction handleFileSelect pour utiliser updateSelectedFilesList
function handleFileSelect(event) {
    const files = event.target.files;
    
    if (files.length === 0) return;
    
    // Ajouter les fichiers à la liste
    for (let i = 0; i < files.length; i++) {
        const file = files[i];
        
        // Vérifier si le fichier est un PDF
        if (file.type !== 'application/pdf') {
            alert(`Le fichier "${file.name}" n'est pas un PDF. Seuls les fichiers PDF sont acceptés.`);
            continue;
        }
        
        // Vérifier si le fichier existe déjà dans la liste
        const fileExists = selectedFiles.some(existingFile => existingFile.name === file.name);
        if (fileExists) {
            alert(`Le fichier "${file.name}" a déjà été sélectionné.`);
            continue;
        }
        
        selectedFiles.push({
            name: file.name,
            file: file,
            data: null
        });
    }
    
    // Mettre à jour l'affichage des fichiers sélectionnés
    updateSelectedFilesList();
    
    // Afficher le bouton d'analyse si des fichiers ont été sélectionnés
    if (selectedFiles.length > 0) {
        document.getElementById('scan-button').classList.remove('d-none');
    }
    
    // Réinitialiser l'input file pour permettre de sélectionner à nouveau le même fichier
    event.target.value = '';
}