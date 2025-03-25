document.addEventListener('DOMContentLoaded', function() {
    console.log("Script d'inscription chargé");
    const registerForm = document.getElementById('register-form');
    
    if (!registerForm) {
        console.error("Le formulaire d'inscription n'a pas été trouvé");
        return;
    }
    
    console.log("Formulaire trouvé, ajout de l'écouteur d'événements");
    
    registerForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        console.log("Formulaire soumis");
        
        const formData = {
            nom: document.getElementById('nom').value,
            prenom: document.getElementById('prenom').value,
            date_naissance: document.getElementById('date_naissance').value,
            email: document.getElementById('email').value,
            password: document.getElementById('password').value
        };
        
        console.log("Données du formulaire:", formData);
        
        try {
            console.log("Envoi de la requête à /api/register");
            const response = await fetch('/api/register', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(formData)
            });
            
            console.log("Réponse reçue:", response.status, response.statusText);
            
            const data = await response.json();
            console.log("Données reçues:", data);
            
            if (!response.ok) {
                throw new Error(data.message || data.error || 'Une erreur est survenue lors de l\'inscription');
            }
            
            // Redirection en cas de succès
            console.log("Inscription réussie, redirection vers /login");
            window.location.href = '/login?registered=true';
            
        } catch (error) {
            console.error("Erreur:", error);
            // Afficher l'erreur dans le toast
            const errorToastBody = document.getElementById('error-toast-body');
            if (errorToastBody) {
                errorToastBody.textContent = error.message;
                const errorToast = new bootstrap.Toast(document.getElementById('error-toast'));
                errorToast.show();
            } else {
                alert("Erreur: " + error.message);
            }
        }
    });
});