document.addEventListener('DOMContentLoaded', function () {
    const loginForm = document.getElementById('login-form');
    const errorToast = document.getElementById('error-toast');
    const errorToastBody = document.getElementById('error-toast-body');
    const errorToastInstance = bootstrap.Toast.getOrCreateInstance(errorToast);
    
    // Vérifier si l'utilisateur vient de s'inscrire
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('registered') === 'true') {
        const successToast = document.getElementById('success-toast');
        const successToastBody = document.getElementById('success-toast-body');
        if (successToast && successToastBody) {
            successToastBody.textContent = "Inscription réussie ! Vous pouvez maintenant vous connecter.";
            bootstrap.Toast.getOrCreateInstance(successToast).show();
        }
    }

    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const email = document.getElementById('email').value.trim().toLowerCase();
        const password = document.getElementById('password').value;
        
        try {
            console.log("Tentative de connexion avec:", email);
            
            const response = await fetch('/auth/jwt/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded'
                },
                body: new URLSearchParams({
                    username: email,
                    password: password
                })
            });

            const data = await response.json();
            console.log("Réponse reçue:", data);
            
            if (response.ok) {
                // Stocker le token d'accès
                localStorage.setItem('access_token', data.access_token);
                console.log("Token d'accès stocké:", data.access_token);
                
                // Stocker les données utilisateur
                localStorage.setItem('userData', JSON.stringify(data.user));
                console.log("Données utilisateur stockées:", data.user);
                
                // Stocker l'email de l'utilisateur
                localStorage.setItem('userEmail', data.user.email);
                console.log("Email de l'utilisateur stocké:", data.user.email);
                
                // Vérifier si un changement de mot de passe est requis
                if (data.require_password_change) {
                    // Rediriger vers la page de changement de mot de passe
                    window.location.href = '/change-password?email=' + encodeURIComponent(email);
                } else {
                    // Rediriger vers la page d'accueil
                    window.location.href = '/';
                }
            } else {
                // Afficher le message d'erreur
                errorToastBody.textContent = data.message || "Erreur de connexion";
                errorToastInstance.show();
            }
        } catch (error) {
            console.error("Erreur lors de la connexion:", error);
            errorToastBody.textContent = "Erreur de connexion au serveur";
            errorToastInstance.show();
        }
    });
});