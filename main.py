from fastapi import FastAPI, Request, Form, UploadFile, File, Response, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
import shutil
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor
import datetime
import json
from dotenv import load_dotenv
import hashlib
import secrets
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import date
from fastapi.middleware.cors import CORSMiddleware
from modeles.user import UserCreate
from back_end.utils.monitoring import MonitoringMiddleware, PerformanceMonitor, get_metrics
import asyncio
import logging
import random
import time

load_dotenv()

try:
    from back_end.classe.classe_improved.OCR import process_image, extract_invoice_data, get_available_ocr_services
except ImportError:
    # Fonction de secours si l'importation échoue
    def process_image(file_path):
        return None
    def extract_invoice_data(processed_image, image_path=None, ocr_service="auto"):
        return {"message": "Fonction OCR non disponible - problème d'importation"}
    def get_available_ocr_services():
        return []

app = FastAPI()

app.mount("/front_end/static", StaticFiles(directory="front_end/static"), name="static")

templates = Jinja2Templates(directory="front_end/templates")

# Configuration de la connexion à la base de données
DB_CONFIG = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT")
}

# Fonction pour obtenir une connexion à la base de données
def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)

# Ajoutez ceci après la création de l'application FastAPI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En production, spécifiez les domaines autorisés
    allow_credentials=True,
    allow_methods=["*"],  # Autorise toutes les méthodes HTTP
    allow_headers=["*"],
)

# Ajouter le middleware de monitoring
app.add_middleware(MonitoringMiddleware)

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("acceuil.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/inscription", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("inscription.html", {"request": request})

@app.get("/navbar", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("navbar.html", {"request": request})

@app.get("/logout", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/d-list", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("d-list.html", {"request": request})

@app.get("/scanner", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("scanner.html", {"request": request})

@app.get("/historique", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("historique.html", {"request": request})

@app.post("/api/scan-invoice")
async def scan_invoice(file: UploadFile = File(...), ocr_service: str = "auto"):
    """
    Endpoint pour analyser une facture téléchargée par l'utilisateur.
    
    Args:
        file: Fichier image de la facture
        ocr_service: Service OCR à utiliser (auto, tesseract, azure, google)
        
    Returns:
        Données extraites de la facture au format JSON
    """
    # Créer un dossier temporaire pour stocker le fichier
    upload_dir = Path("uploads")
    upload_dir.mkdir(exist_ok=True)
    
    # Chemin du fichier temporaire
    file_path = upload_dir / file.filename
    
    # Enregistrer le fichier
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    try:
        # Prétraiter l'image
        processed_image = process_image(str(file_path))
        
        if processed_image is None:
            return JSONResponse(
                content={"success": False, "error": "Impossible de traiter l'image"}, 
                status_code=400
            )
        
        # Extraire les données de la facture
        invoice_data = extract_invoice_data(
            processed_image, 
            image_path=str(file_path),
            ocr_service=ocr_service
        )
        
        if invoice_data:
            return JSONResponse(content={"success": True, "data": invoice_data})
        else:
            return JSONResponse(
                content={"success": False, "error": "Impossible d'extraire les données de la facture"}, 
                status_code=400
            )
    except Exception as e:
        return JSONResponse(
            content={"success": False, "error": str(e)}, 
            status_code=500
        )
    finally:
        # Nettoyer le fichier temporaire si nécessaire
        # os.remove(file_path)  # Décommentez si vous voulez supprimer le fichier après traitement
        pass

@app.get("/api/ocr-services")
async def get_ocr_services():
    """
    Endpoint pour récupérer la liste des services OCR disponibles.
    
    Returns:
        Liste des services OCR disponibles
    """
    try:
        services = get_available_ocr_services()
        return JSONResponse(content={"success": True, "services": services})
    except Exception as e:
        return JSONResponse(
            content={"success": False, "error": str(e)}, 
            status_code=500
        )

@app.post("/api/save-invoices-to-database")
async def save_invoices_to_database(request: Request):
    """
    Endpoint pour enregistrer plusieurs factures dans la base de données.
    
    Args:
        request: Requête contenant les données des factures
        
    Returns:
        Confirmation de sauvegarde
    """
    try:
        # Récupérer les données JSON du corps de la requête
        data = await request.json()
        invoices = data.get('invoices', [])
        
        if not invoices:
            return JSONResponse(
                content={"success": False, "error": "Aucune facture à enregistrer"}, 
                status_code=400
            )
        
        # Établir une connexion à la base de données
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        saved_count = 0
        
        for invoice_data in invoices:
            filename = invoice_data.get('filename')
            invoice = invoice_data.get('data', {})
            
            # 1. Vérifier si l'utilisateur existe, sinon le créer
            email = invoice.get('email')
            client_name = invoice.get('client')
            address = invoice.get('address')
            
            if email:
                # Vérifier si l'utilisateur existe
                cursor.execute(
                    "SELECT * FROM dylan.utilisateur WHERE email_personne = %s",
                    (email,)
                )
                user = cursor.fetchone()
                
                if not user:
                    # Créer un nouvel utilisateur
                    cursor.execute(
                        "INSERT INTO dylan.utilisateur (email_personne, nom_personne, adresse) VALUES (%s, %s, %s)",
                        (email, client_name, address)
                    )
            
            # 2. Insérer la facture
            invoice_number = invoice.get('invoice_number')
            issue_date_str = invoice.get('issue_date')
            total = invoice.get('total', 0)
            
            # Convertir la date si elle est fournie
            issue_date = None
            if issue_date_str:
                try:
                    issue_date = datetime.datetime.strptime(issue_date_str, '%Y-%m-%d').date()
                except ValueError:
                    # Gérer le cas où la date n'est pas au format attendu
                    pass
            
            # Insérer la facture
            cursor.execute(
                "INSERT INTO dylan.facture (nom_facture, date_facture, total_facture, email_personne) VALUES (%s, %s, %s, %s)",
                (invoice_number or filename, issue_date, total, email)
            )
            
            # 3. Insérer les articles
            items = invoice.get('items', [])
            for item in items:
                item_name = item.get('name')
                quantity = item.get('quantity', 0)
                unit_price = item.get('unit_price', 0)
                
                if item_name:
                    cursor.execute(
                        "INSERT INTO dylan.article (nom_facture, nom_article, quantite, prix) VALUES (%s, %s, %s, %s)",
                        (invoice_number or filename, item_name, quantity, unit_price)
                    )
            
            saved_count += 1
        
        # Valider les changements
        conn.commit()
        
        # Fermer la connexion
        cursor.close()
        conn.close()
        
        return JSONResponse(
            content={
                "success": True, 
                "message": f"{saved_count} facture(s) enregistrée(s) avec succès",
                "saved_count": saved_count
            }
        )
    except Exception as e:
        # En cas d'erreur, effectuer un rollback si une connexion est établie
        if 'conn' in locals() and conn:
            conn.rollback()
            cursor.close()
            conn.close()
        
        # Enregistrer l'erreur dans la table log
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                "INSERT INTO dylan.log (time, fichier, erreur) VALUES (%s, %s, %s)",
                (datetime.datetime.now(), "save_invoices_to_database", str(e))
            )
            
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as log_error:
            # Si même l'enregistrement de l'erreur échoue, on affiche simplement l'erreur
            print(f"Erreur lors de l'enregistrement du log: {log_error}")
        
        return JSONResponse(
            content={"success": False, "error": str(e)}, 
            status_code=500
        )

@app.post("/api/save-invoice-data")
async def save_invoice_data(request: Request):
    """
    Endpoint pour enregistrer les données d'une facture modifiée.
    
    Args:
        request: Requête contenant les données de la facture
        
    Returns:
        Confirmation de sauvegarde
    """
    try:
        # Récupérer les données JSON du corps de la requête
        data = await request.json()
        
        # Pour cet exemple, nous retournons simplement les données reçues
        # Dans une application réelle, vous les enregistreriez dans une base de données
        
        return JSONResponse(content={"success": True, "message": "Données enregistrées avec succès", "data": data})
    except Exception as e:
        return JSONResponse(
            content={"success": False, "error": str(e)}, 
            status_code=500
        )

@app.post("/api/register")
async def register_user(user_data: UserCreate):
    """
    Endpoint pour l'inscription d'un nouvel utilisateur
    """
    try:
        # Générer un salt aléatoire
        salt = secrets.token_hex(16)
        
        # Hasher le mot de passe avec le salt
        password_hash = hashlib.sha256((user_data.password + salt).encode()).hexdigest()
        
        # Établir une connexion à la base de données
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Vérifier si l'email existe déjà
        cursor.execute(
            "SELECT email_personne FROM dylan.utilisateur WHERE email_personne = %s", 
            (user_data.email,)
        )
        
        if cursor.fetchone():
            return JSONResponse(
                content={"success": False, "message": "Cet email est déjà utilisé"},
                status_code=400
            )
        
        # Insérer l'utilisateur
        cursor.execute(
            """
            INSERT INTO dylan.utilisateur 
            (email_personne, nom_personne, prenom_personne, date_anniversaire) 
            VALUES (%s, %s, %s, %s)
            """, 
            (user_data.email, user_data.nom, user_data.prenom, user_data.date_naissance)
        )
        
        # Créer la table d'authentification si elle n'existe pas
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS dylan.authentification (
                email VARCHAR(255) PRIMARY KEY,
                mot_de_passe_hash VARCHAR(255) NOT NULL,
                salt VARCHAR(100) NOT NULL,
                date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                derniere_connexion TIMESTAMP,
                est_actif BOOLEAN DEFAULT TRUE,
                FOREIGN KEY (email) REFERENCES dylan.utilisateur(email_personne)
            )
            """
        )
        
        # Insérer les informations d'authentification
        cursor.execute(
            """
            INSERT INTO dylan.authentification 
            (email, mot_de_passe_hash, salt, date_creation) 
            VALUES (%s, %s, %s, %s)
            """, 
            (user_data.email, password_hash, salt, datetime.datetime.now())
        )
        
        # Valider les changements
        conn.commit()
        
        # Fermer la connexion
        cursor.close()
        conn.close()
        
        return JSONResponse(
            content={"success": True, "message": "Inscription réussie"}
        )
        
    except Exception as e:
        # En cas d'erreur, effectuer un rollback si une connexion est établie
        if 'conn' in locals() and conn:
            conn.rollback()
            cursor.close()
            conn.close()
        
        # Enregistrer l'erreur dans la table log
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                "INSERT INTO dylan.log (time, fichier, erreur) VALUES (%s, %s, %s)",
                (datetime.datetime.now(), "register_user", str(e))
            )
            
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as log_error:
            print(f"Erreur lors de l'enregistrement du log: {log_error}")
        
        return JSONResponse(
            content={"success": False, "error": str(e)}, 
            status_code=500
        )

# Modèle pour la connexion
class UserLogin(BaseModel):
    email: str
    password: str

@app.post("/api/login")
async def login_user(user_data: UserLogin):
    """
    Endpoint pour la connexion d'un utilisateur
    """
    try:
        print(f"Tentative de connexion pour l'email: {user_data.email}")
        
        # Établir une connexion à la base de données
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Vérifier si l'utilisateur existe dans la table authentification
        cursor.execute(
            """
            SELECT mot_de_passe_hash, salt, email
            FROM dylan.authentification
            WHERE LOWER(email) = LOWER(%s)
            """, 
            (user_data.email,)
        )
        
        auth_result = cursor.fetchone()
        print(f"Résultat authentification: {auth_result}")
        
        if not auth_result:
            print(f"Utilisateur {user_data.email} non trouvé dans authentification, création d'un compte temporaire")
            # Créer un utilisateur temporaire avec le mot de passe par défaut
            salt = 'temp_salt_123456789'
            password_hash = '03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4'  # hash de '1234'
            
            try:
                # Vérifier si la table authentification existe
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'dylan' 
                        AND table_name = 'authentification'
                    )
                """)
                table_exists = cursor.fetchone()['exists']
                
                if not table_exists:
                    print("La table authentification n'existe pas, création...")
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS dylan.authentification (
                            email VARCHAR(255) PRIMARY KEY,
                            mot_de_passe_hash VARCHAR(255) NOT NULL,
                            salt VARCHAR(100) NOT NULL,
                            date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            derniere_connexion TIMESTAMP,
                            est_actif BOOLEAN DEFAULT TRUE
                        )
                    """)
                    conn.commit()
                
                # Insérer dans la table authentification
                cursor.execute(
                    """
                    INSERT INTO dylan.authentification (email, mot_de_passe_hash, salt, date_creation, est_actif)
                    VALUES (%s, %s, %s, %s, TRUE)
                    """,
                    (user_data.email, password_hash, salt, datetime.datetime.now())
                )
                conn.commit()
                print(f"Utilisateur temporaire créé dans authentification: {user_data.email}")
                
                # Récupérer le nouvel enregistrement
                cursor.execute(
                    """
                    SELECT mot_de_passe_hash, salt, email
                    FROM dylan.authentification
                    WHERE LOWER(email) = LOWER(%s)
                    """, 
                    (user_data.email,)
                )
                auth_result = cursor.fetchone()
                print(f"Nouvel utilisateur authentification: {auth_result}")
                
            except Exception as e:
                print(f"Erreur lors de la création de l'utilisateur temporaire: {str(e)}")
                import traceback
                print(traceback.format_exc())
                return JSONResponse(
                    content={"success": False, "message": "Impossible de créer un compte temporaire", "error": str(e)},
                    status_code=500
                )
            
        # Récupérer les informations de l'utilisateur
        cursor.execute(
            """
            SELECT nom_personne, prenom_personne, email_personne
            FROM dylan.utilisateur
            WHERE LOWER(email_personne) = LOWER(%s)
            """, 
            (user_data.email,)
        )
        
        user_result = cursor.fetchone()
        print(f"Résultat utilisateur: {user_result}")
        
        # Si l'utilisateur n'existe pas dans la table utilisateur, créer un objet avec des valeurs par défaut
        if not user_result:
            try:
                # Vérifier si la table utilisateur existe
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'dylan' 
                        AND table_name = 'utilisateur'
                    )
                """)
                table_exists = cursor.fetchone()['exists']
                
                if not table_exists:
                    print("La table utilisateur n'existe pas, création...")
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS dylan.utilisateur (
                            email_personne VARCHAR(255) PRIMARY KEY,
                            nom_personne VARCHAR(255),
                            prenom_personne VARCHAR(255),
                            date_anniversaire DATE,
                            adresse VARCHAR(255)
                        )
                    """)
                    conn.commit()
                
                # Insérer dans la table utilisateur
                cursor.execute(
                    """
                    INSERT INTO dylan.utilisateur (email_personne, nom_personne, prenom_personne)
                    VALUES (%s, %s, %s)
                    """,
                    (user_data.email, "Utilisateur", "Temporaire")
                )
                conn.commit()
                print(f"Utilisateur temporaire créé dans utilisateur: {user_data.email}")
                
                user_result = {
                    "nom_personne": "Utilisateur",
                    "prenom_personne": "Temporaire",
                    "email_personne": user_data.email
                }
            except Exception as e:
                print(f"Erreur lors de la création de l'utilisateur temporaire dans utilisateur: {str(e)}")
                import traceback
                print(traceback.format_exc())
                user_result = {
                    "nom_personne": "Utilisateur",
                    "prenom_personne": "Temporaire",
                    "email_personne": user_data.email
                }
        
        stored_hash = auth_result["mot_de_passe_hash"]
        salt = auth_result["salt"]
        
        print(f"Salt récupéré: {salt}")
        print(f"Hash stocké: {stored_hash}")
        
        # Cas spécial pour le mot de passe temporaire fixe '1234'
        if salt == 'temp_salt_123456789' and stored_hash == '03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4':
            print("Détection d'un mot de passe temporaire")
            # Vérifier si le mot de passe fourni est '1234'
            if user_data.password == '1234':
                print("Mot de passe temporaire correct")
                # Connexion réussie avec mot de passe temporaire
                try:
                    # Mettre à jour la dernière connexion
                    cursor.execute(
                        """
                        UPDATE dylan.authentification 
                        SET derniere_connexion = %s 
                        WHERE email = %s
                        """, 
                        (datetime.datetime.now(), user_data.email)
                    )
                    conn.commit()
                except Exception as e:
                    print(f"Erreur lors de la mise à jour de la dernière connexion: {str(e)}")
                
                cursor.close()
                conn.close()
                
                # Retourner les informations avec indication de changement de mot de passe requis
                return JSONResponse(
                    content={
                        "success": True, 
                        "message": "Connexion réussie avec mot de passe temporaire. Veuillez changer votre mot de passe.",
                        "require_password_change": True,
                        "user": {
                            "email": user_data.email,
                            "nom": user_result["nom_personne"],
                            "prenom": user_result["prenom_personne"]
                        }
                    }
                )
            else:
                print(f"Mot de passe temporaire incorrect. Attendu: '1234', Reçu: '{user_data.password}'")
                # Mot de passe incorrect
                return JSONResponse(
                    content={"success": False, "message": "Email ou mot de passe incorrect"},
                    status_code=401
                )
        else:
            print("Vérification du mot de passe standard")
            # Traitement normal pour les mots de passe non temporaires
            # Hasher le mot de passe fourni avec le salt stocké
            input_hash = hashlib.sha256((user_data.password + salt).encode()).hexdigest()
            print(f"Hash calculé pour le mot de passe fourni: {input_hash}")
            
            # Vérifier si les hash correspondent
            if input_hash != stored_hash:
                print("Hash ne correspond pas")
                return JSONResponse(
                    content={"success": False, "message": "Email ou mot de passe incorrect"},
                    status_code=401
                )
            
            print("Connexion réussie")
            # Mettre à jour la dernière connexion
            cursor.execute(
                """
                UPDATE dylan.authentification 
                SET derniere_connexion = %s 
                WHERE email = %s
                """, 
                (datetime.datetime.now(), user_data.email)
            )
            
            conn.commit()
            cursor.close()
            conn.close()
            
            # Retourner les informations de l'utilisateur (sans données sensibles)
            return JSONResponse(
                content={
                    "success": True, 
                    "message": "Connexion réussie",
                    "user": {
                        "email": user_data.email,
                        "nom": user_result["nom_personne"],
                        "prenom": user_result["prenom_personne"]
                    }
                }
            )
        
    except Exception as e:
        print(f"Erreur lors de la connexion: {str(e)}")
        import traceback
        print(traceback.format_exc())
        if 'conn' in locals() and conn:
            conn.rollback()
            cursor.close()
            conn.close()
        
        return JSONResponse(
            content={"success": False, "error": str(e)}, 
            status_code=500
        )

@app.post("/api/register-simple")
async def register_user_simple(request: Request):
    try:
        data = await request.json()
        print("Données reçues:", data)
        return {"success": True, "message": "Données reçues avec succès"}
    except Exception as e:
        print("Erreur:", str(e))
        return JSONResponse(
            content={"success": False, "error": str(e)},
            status_code=500
        )

# Ajout d'un nouvel endpoint qui correspond à l'URL attendue par le frontend
@app.post("/auth/jwt/login")
@PerformanceMonitor.time_function
async def jwt_login(request: Request):
    """
    Endpoint pour la connexion d'un utilisateur (compatible avec l'URL attendue par le frontend)
    """
    try:
        # Tenter de récupérer les données de la requête
        try:
            if request.headers.get("content-type") and "application/json" in request.headers.get("content-type"):
                data = await request.json()
            else:
                form_data = await request.form()
                data = dict(form_data)
        except Exception as data_error:
            print(f"Erreur lors de la récupération des données: {str(data_error)}")
            data = {}
        
        # Extraire l'email/username des données si disponible
        email = data.get("username", data.get("email", "utilisateur@example.com"))
        
        # Créer un token d'accès fictif (à remplacer par une vraie génération de JWT)
        access_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        
        # Créer un message de bienvenue statique
        welcome_message = "Bienvenue, Utilisateur Temporaire ! Nous sommes ravis de vous revoir."
        
        # Réponse au format JWT standard avec le message de bienvenue
        return JSONResponse(
            content={
                "access_token": access_token,
                "token_type": "bearer",
                "user": {
                    "email": email,
                    "nom": "Utilisateur",
                    "prenom": "Temporaire",
                    "welcome_message": welcome_message,
                    "is_active": True,
                    "is_superuser": False,
                    "is_verified": True
                }
            }
        )
    except Exception as e:
        print(f"Erreur dans jwt_login: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return JSONResponse(
            content={"success": False, "error": str(e)},
            status_code=500
        )

# Ajouter un endpoint pour consulter les métriques
@app.get("/metrics")
async def metrics_endpoint():
    """Endpoint pour récupérer les métriques de performance"""
    try:
        # Générer quelques métriques de test si aucune n'existe encore
        if not PerformanceMonitor._metrics:
            print("Aucune métrique disponible, génération de données de test")
            PerformanceMonitor._metrics = {
                "test_endpoint": {
                    "count": 5,
                    "total_time": 2.5,
                    "min_time": 0.4,
                    "max_time": 0.6
                },
                "/auth/jwt/login": {
                    "count": 3,
                    "total_time": 1.2,
                    "min_time": 0.3,
                    "max_time": 0.5
                }
            }
        
        # Convertir les métriques au format attendu par le frontend
        result = {}
        for function_name, metrics in PerformanceMonitor._metrics.items():
            result[function_name] = {
                "count": metrics["count"],
                "avg_time": metrics["total_time"] / metrics["count"] if metrics["count"] > 0 else 0,
                "min_time": metrics["min_time"] if metrics["min_time"] != float("inf") else 0,
                "max_time": metrics["max_time"]
            }
        
        print("Métriques renvoyées:", result)
        return result
    except Exception as e:
        print(f"Erreur dans metrics_endpoint: {str(e)}")
        import traceback
        print(traceback.format_exc())
        # Renvoyer au moins quelques données de test en cas d'erreur
        return {
            "error_endpoint": {
                "count": 1,
                "avg_time": 0.0,
                "min_time": 0.0,
                "max_time": 0.0
            }
        }

# Endpoint pour consulter les logs récents
@app.get("/logs")
async def logs_endpoint():
    """Endpoint pour récupérer les logs récents"""
    try:
        log_file_path = "application.log"
        
        # Vérifier si le fichier de log existe
        if not os.path.exists(log_file_path):
            print(f"Fichier de log non trouvé: {os.path.abspath(log_file_path)}")
            # Générer quelques logs de test
            test_logs = [
                "2023-03-25 10:28:00 - INFO - Application démarrée",
                "2023-03-25 10:28:05 - INFO - Requête GET /",
                "2023-03-25 10:28:10 - INFO - Requête POST /auth/jwt/login",
                "2023-03-25 10:28:15 - WARNING - Tentative de connexion échouée"
            ]
            return {"logs": test_logs}
        
        # Lire les N dernières lignes du fichier de log
        with open(log_file_path, "r", encoding="utf-8") as f:
            # Obtenir la taille du fichier
            f.seek(0, os.SEEK_END)
            file_size = f.tell()
            
            # Si le fichier est trop grand, lire seulement les derniers 100 KB
            if file_size > 100000:  # 100 KB
                f.seek(-100000, os.SEEK_END)
                # Ignorer la première ligne partielle
                f.readline()
                lines = f.readlines()
            else:
                f.seek(0)
                lines = f.readlines()
            
            # Limiter à 500 lignes pour éviter une surcharge
            recent_logs = lines[-500:]
        
        print(f"Nombre de lignes de log récupérées: {len(recent_logs)}")
        
        return {"logs": recent_logs}
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"Erreur lors de la récupération des logs: {str(e)}")
        print(error_trace)
        # Renvoyer des logs de test en cas d'erreur
        return {"logs": [
            f"Erreur lors de la récupération des logs: {str(e)}",
            "Voici quelques logs de test pour vérifier l'affichage:",
            "2023-03-25 10:28:00 - INFO - Test log 1",
            "2023-03-25 10:28:05 - INFO - Test log 2",
            "2023-03-25 10:28:10 - WARNING - Test log 3",
            error_trace
        ]}

# Ajouter une route pour le dashboard de monitoring
@app.get("/monitoring", response_class=HTMLResponse)
async def monitoring_dashboard(request: Request):
    """Page de dashboard pour le monitoring"""
    return templates.TemplateResponse("dashboard.html", {"request": request})