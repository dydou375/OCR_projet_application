from fastapi import FastAPI, Request, Form, UploadFile, File, Response, Depends, HTTPException
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
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from fastapi.middleware.cors import CORSMiddleware
from modeles.user import UserCreate
import asyncio
import logging
import random
import time
import urllib.parse

from back_end.classe.extract_qr_code import extract_data_qrcode
from back_end.utils.monitoring import MonitoringMiddleware, PerformanceMonitor, get_metrics
from back_end.classe.classe_improved.OCR import process_image, extract_invoice_data, get_available_ocr_services



load_dotenv()



app = FastAPI(title="Mon API OCR",
    description="API pour la reconnaissance de texte avec OCR",
    version="1.0",
    contact={
        "name": "Dylan",
        "url": "https://example.com/contact",
        "email": "dylan.chevallier@gmail.com",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },)

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

# Modèles Pydantic pour les requêtes et réponses

class InvoiceItem(BaseModel):
    name: str
    quantity: int
    unit_price: float

class Invoice(BaseModel):
    filename: str
    data: Dict[str, Any] = Field(
        ...,
        example={
            "email": "client@example.com",
            "client": "Nom du client",
            "address": "Adresse du client",
            "invoice_number": "INV-12345",
            "issue_date": "2023-10-01",
            "total": 100.0,
            "items": [
                {"name": "Article 1", "quantity": 2, "unit_price": 25.0},
                {"name": "Article 2", "quantity": 1, "unit_price": 50.0}
            ]
        }
    )

class InvoiceResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None

class OCRServiceResponse(BaseModel):
    success: bool
    services: List[str]

class UserRegistrationResponse(BaseModel):
    success: bool
    message: str

@app.get("/", response_class=HTMLResponse, tags=["Accueil"])
async def index(request: Request):
    return templates.TemplateResponse("acceuil.html", {"request": request})

@app.get("/login", response_class=HTMLResponse, tags=["Authentification"])
async def index(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/inscription", response_class=HTMLResponse, tags=["Authentification"])
async def index(request: Request):
    return templates.TemplateResponse("inscription.html", {"request": request})

@app.get("/logout", response_class=HTMLResponse, tags=["Authentification"])
async def index(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/d-list", response_class=HTMLResponse, tags=["Accueil"])
async def index(request: Request):
    return templates.TemplateResponse("d-list.html", {"request": request})

@app.get("/scanner", response_class=HTMLResponse, tags=["Accueil"])
async def index(request: Request):
    return templates.TemplateResponse("scanner.html", {"request": request})

@app.get("/historique", response_class=HTMLResponse, tags=["Accueil"])
async def index(request: Request):
    return templates.TemplateResponse("historique.html", {"request": request})

@app.get("/facture/details/{facture_id}", response_class=HTMLResponse, tags=["Accueil"])
async def facture_details_page(request: Request, facture_id: int):
    return templates.TemplateResponse("details_facture.html", {"request": request, "facture_id": facture_id})

@app.post("/api/scan-invoice", response_model=InvoiceResponse, tags=["Accueil"])
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
        # Extraire les données du QR code
        qr_data = extract_data_qrcode(str(file_path))
        
        if qr_data:
            print("Données QR code extraites:", qr_data)
        
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
        
        # Fusionner les données du QR code avec les données de la facture
        if invoice_data:
            if qr_data:
                invoice_data.update(qr_data)
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
        os.remove(file_path)  # Décommentez si vous voulez supprimer le fichier après traitement
        pass

@app.get("/api/ocr-services", response_model=OCRServiceResponse, tags=["OCR Analyse"])
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

@app.post("/api/save-invoices-to-database", response_model=InvoiceResponse)
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

@app.post("/api/save-invoice-data", tags=["Database"])
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

@app.post("/api/register", response_model=UserRegistrationResponse, tags=["Authentification"])
async def register_user(user_data: UserCreate):
    """
    Endpoint pour l'inscription d'un nouvel utilisateur.
    
    Args:
        user_data: Données de l'utilisateur à enregistrer
        
    Returns:
        Confirmation de l'inscription
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

@app.post("/api/register-simple", tags=["Authentification"])
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
@app.post("/auth/jwt/login", tags=["Authentification"])
async def jwt_login(request: Request):
    try:
        # Récupérer les données de la requête
        if request.headers.get("content-type") and "application/json" in request.headers.get("content-type"):
            data = await request.json()
        else:
            form_data = await request.form()
            data = dict(form_data)
        
        email = data.get("username", data.get("email"))
        password = data.get("password")

        if not email or not password:
            raise HTTPException(status_code=400, detail="Email et mot de passe requis")

        # Connexion à la base de données
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Requête pour récupérer les données utilisateur
        query = """
        SELECT a.email, a.mot_de_passe, u.nom_personne, u.genre, u.adresse, u.date_anniversaire
        FROM dylan.authentification a
        JOIN dylan.utilisateur u ON a.email = u.email_personne
        WHERE a.email = %s
        """
        cursor.execute(query, (email,))
        user = cursor.fetchone()

        if not user or password != user['mot_de_passe']:
            raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")

        # Créer un token d'accès (à remplacer par une vraie génération de JWT)
        access_token = "votre_token_jwt"

        # Réponse avec les données utilisateur réelles
        return JSONResponse(
            content={
                "access_token": access_token,
                "token_type": "bearer",
                "user": {
                    "email": user['email'],
                    "nom": user['nom_personne'],
                    "genre": user['genre'],
                    "adresse": user['adresse'],
                    "is_active": user.get('est_actif', True),
                    "is_verified": user.get('is_verified', True)
                }
            }
        )
    except Exception as e:
        print(f"Erreur dans jwt_login: {str(e)}")
        return JSONResponse(
            content={"success": False, "error": str(e)},
            status_code=500
        )
    finally:
        cursor.close()
        conn.close()
        

# Ajouter un endpoint pour consulter les métriques
@app.get("/metrics", tags=["Monitoring"])
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
@app.get("/logs", tags=["Monitoring"])
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
@app.get("/monitoring", response_class=HTMLResponse, tags=["Monitoring"])
async def monitoring_dashboard(request: Request):
    """Page de dashboard pour le monitoring"""
    return templates.TemplateResponse("dashboard.html", {"request": request})
    
@app.get("/api/factures/{email}", tags=["Details Facture"])
async def get_factures(request: Request, email: str):
    """
    Endpoint pour récupérer toutes les factures d'un utilisateur
    """
    try:
        # Décoder l'email
        decoded_email = urllib.parse.unquote(email)
        # Connexion à la base de données
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Requête pour récupérer les factures de l'utilisateur
        query = """
        SELECT f.nom_facture, f.date_facture, f.total_facture, u.nom_personne
        FROM dylan.facture f
        JOIN dylan.utilisateur u ON f.email_personne = u.email_personne
        WHERE u.email_personne = %s
        """
        cursor.execute(query, (decoded_email,))
        factures = cursor.fetchall()
        
        for facture in factures:
            if isinstance(facture['date_facture'], datetime.date):
                facture['date_facture'] = facture['date_facture'].strftime('%Y-%m-%d')

        return JSONResponse(content={"success": True, "factures": factures})
    except Exception as e:
        print(f"Erreur dans get_factures: {str(e)}")
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)
    finally:
        cursor.close()
        conn.close()

@app.get("/api/facture/{facture_id}", tags=["Details Facture"])
async def get_facture_details(facture_id: int):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        query = """
        SELECT f.nom_facture, f.date_facture, f.total_facture, u.nom_personne, a.nom_article, a.quantite, a.prix
        FROM dylan.facture f
        JOIN dylan.utilisateur u ON f.email_personne = u.email_personne
        LEFT JOIN dylan.article a ON f.id = a.facture_id
        WHERE f.id = %s
        """
        cursor.execute(query, (facture_id,))
        facture_details = cursor.fetchall()

        print("Détails de la facture récupérés:", facture_details)

        for detail in facture_details:
            if isinstance(detail['date_facture'], datetime.date):
                detail['date_facture'] = detail['date_facture'].isoformat()

        facture = {
            "nom_facture": facture_details[0]['nom_facture'],
            "date_facture": facture_details[0]['date_facture'],
            "total_facture": facture_details[0]['total_facture'],
            "nom_personne": facture_details[0]['nom_personne'],
            "articles": [
                {
                    "nom_article": detail['nom_article'],
                    "quantite": detail['quantite'],
                    "prix": detail['prix']
                } for detail in facture_details if detail['nom_article'] is not None
            ]
        }

        return JSONResponse(content={"success": True, "facture_details": [facture]})
    except Exception as e:
        print(f"Erreur dans get_facture_details: {str(e)}")
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)
    finally:
        cursor.close()
        conn.close()

        