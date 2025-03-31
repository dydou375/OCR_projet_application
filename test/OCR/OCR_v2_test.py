import cv2
import pytesseract
import numpy as np
import os
from PIL import Image
from pyzbar.pyzbar import decode
import xml.etree.ElementTree as ET
import requests
import re
import csv
import json
import psycopg2
from dotenv import load_dotenv
import time

load_dotenv()
#-------------- Preprocessing image--------------

def preprocess_image(image_path):
    """Améliore l'image avant OCR avec des techniques avancées."""
    # Chargement de l'image
    image = cv2.imread(image_path)
    if image is None:
        print(f"Erreur : Impossible de charger l'image à partir de {image_path}")
        return None

    # Redimensionnement pour améliorer la précision (facteur d'échelle 1.5)
    scale_factor = 1.5
    width = int(image.shape[1] * scale_factor)
    height = int(image.shape[0] * scale_factor)
    image = cv2.resize(image, (width, height), interpolation=cv2.INTER_CUBIC)
    
    # Conversion en niveaux de gris
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Correction de l'inclinaison (deskewing)
    # Détection des bordures
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    # Utiliser la transformée de Hough pour détecter les lignes
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, 100, minLineLength=100, maxLineGap=10)
    if lines is not None:
        angles = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            if x2 - x1 != 0:  # Éviter division par zéro
                angle = np.arctan((y2 - y1) / (x2 - x1)) * 180 / np.pi
                if abs(angle) < 45:  # Ignorer les lignes très inclinées
                    angles.append(angle)
        if angles:
            median_angle = np.median(angles)
            if abs(median_angle) > 0.5:  # Si l'inclinaison est significative
                (h, w) = gray.shape
                center = (w // 2, h // 2)
                M = cv2.getRotationMatrix2D(center, median_angle, 1.0)
                gray = cv2.warpAffine(gray, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    
    # Réduction du bruit
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    
    # Amélioration du contraste par égalisation d'histogramme adaptative
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)
    
    # Filtre de netteté pour améliorer les contours
    kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
    sharp = cv2.filter2D(gray, -1, kernel)
    
    # Binarisation adaptative locale au lieu d'OTSU global
    binary = cv2.adaptiveThreshold(sharp, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                cv2.THRESH_BINARY, 11, 2)
    
    # Opérations morphologiques pour nettoyer l'image
    kernel = np.ones((1, 1), np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
    
    return binary

#-------------- Extract data text (json)--------------
def extract_invoice_data_to_json(image_path):
    """Extrait les données d'une facture via OCR et les retourne au format JSON."""
    # Prétraitement avancé de l'image
    processed_image = preprocess_image(image_path)
    if processed_image is None:
        return None

    # Configuration Tesseract améliorée
    custom_config = r'--oem 1 --psm 4 -l eng'
    
    # Réaliser OCR sur l'image améliorée
    raw_text = pytesseract.image_to_string(processed_image, config=custom_config)
    
    # Affichage du texte brut extrait
    print("🔍 Texte extrait après amélioration :\n", raw_text)

    # Dictionnaire pour stocker les résultats
    invoice_data = {
        "invoice_number": None,
        "issue_date": None,
        "client": None,
        "email": None,
        "address": None,
        "items": [],
        "total": None
    }

    # Nettoyage du texte brut
    # Normalisation des espaces et retours à la ligne
    raw_text = " ".join(raw_text.split())
    raw_text = raw_text.replace("\n\n", " ¶ ").replace("\n", " ")
    
    # Correction des erreurs fréquentes d'OCR
    corrections = {
        "Furo": "Euro", "Buro": "Euro", "Bure": "Euro", "Eure": "Euro",
        "Ernail": "Email", "Ernall": "Email", "Emai1": "Email", "Mali": "Email",
        "0rder": "Order", "lnvoice": "Invoice", "INV0ICE": "INVOICE",
        "B1ll": "Bill", "Bi11": "Bill", 
        "@gmai1.com": "@gmail.com", "@hotmai1.com": "@hotmail.com",
        "Ackiress": "Address", "Acdress": "Address", "Addre55": "Address"
    }
    
    for incorrect, correct in corrections.items():
        raw_text = raw_text.replace(incorrect, correct)
    
    # Reconstitution des retours à la ligne pour faciliter l'extraction
    raw_text = raw_text.replace(" ¶ ", "\n\n")

    # Extraction séquentielle des éléments de la facture
    sections = {}
    
    # 1. Extraire d'abord les informations de base
    invoice_match = re.search(r'INVOICE\s*[:#]?\s*([\w\/-]+)', raw_text, re.IGNORECASE)
    if invoice_match:
        invoice_data["invoice_number"] = invoice_match.group(1).strip()
        sections["invoice"] = (invoice_match.start(), invoice_match.end())
    
    date_match = re.search(r'(?:Issue|Date)[:\s]+(\d{4}[-/]\d{1,2}[-/]\d{1,2})', raw_text, re.IGNORECASE)
    if date_match:
        date_str = date_match.group(1)
        date_parts = re.split(r'[-/]', date_str)
        if len(date_parts) == 3:
            invoice_data["issue_date"] = f"{date_parts[0]}-{date_parts[1].zfill(2)}-{date_parts[2].zfill(2)}"
        sections["date"] = (date_match.start(), date_match.end())
    
    client_match = re.search(r'Bill to\s*(.+?)(?=\s*Email|\s*Address|\n)', raw_text, re.IGNORECASE)
    if client_match:
        invoice_data["client"] = client_match.group(1).strip()
        sections["client"] = (client_match.start(), client_match.end())
    
    email_match = re.search(r'Email[:\s]+\s*([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', raw_text, re.IGNORECASE)
    if email_match:
        invoice_data["email"] = email_match.group(1).strip().lower()
        sections["email"] = (email_match.start(), email_match.end())
    
    # 2. Extraire les articles et le total
    items_and_total = []
    seen_items = set()  # Pour éviter les doublons
    
    # Version améliorée de la regex pour les articles qui prend en compte différents formats
    item_matches = re.finditer(r'([A-Z][a-zA-Z\s\.\-\_\&]+?)\.?\s+(\d+)\s*x\s*([\d\.,]+)\s*(?:Euro|EUR|€)', raw_text)
    
    for match in item_matches:
        name, qty, price = match.groups()
        # Créer une clé unique pour cet article
        item_key = f"{name.strip()}_{qty}_{price}"
        
        # Vérifier si on a déjà traité cet article
        if item_key not in seen_items:
            seen_items.add(item_key)
            items_and_total.append((match.start(), match.end()))
            try:
                invoice_data["items"].append({
                    "name": name.strip(),
                    "quantity": int(qty),
                    "unit_price": float(price.replace(",", ".")),
                    "total_price": int(qty) * float(price.replace(",", "."))
                })
            except ValueError:
                print(f"Erreur lors de l'extraction de l'article: {match.group()}")
    
    total_match = re.search(r'TOTAL\s+([\d\.,]+)\s+(?:Euro|EUR|€)', raw_text)
    if total_match:
        invoice_data["total"] = float(total_match.group(1).replace(",", "."))
        items_and_total.append((total_match.start(), total_match.end()))
    
    # 3. Extraire l'adresse - elle doit se trouver entre l'email et les articles
    address_start = None
    address_end = None
    
    # Recherche de l'étiquette "Address"
    address_label_match = re.search(r'Address[:\s]+', raw_text, re.IGNORECASE)
    
    if address_label_match:
        address_start = address_label_match.end()
        
        # Trouver la fin de l'adresse (avant le premier article ou le total)
        if items_and_total:
            address_end = min(pos[0] for pos in items_and_total)
        else:
            # Si pas d'articles ni de total, prendre jusqu'à la fin
            address_end = len(raw_text)
        
        if address_start < address_end:
            address_text = raw_text[address_start:address_end].strip()
            # Nettoyer l'adresse
            address_text = re.sub(r'\s+', ' ', address_text)
            invoice_data["address"] = address_text
    
    # Vérification de la cohérence des données avant enregistrement
    if not invoice_data["invoice_number"]:
        print("⚠️ Attention: Numéro de facture non détecté!")
    
    if not invoice_data["email"] and email_match:
        print("⚠️ Attention: Format d'email incorrect détecté:", email_match.group(1))
    
    # Validation du total par rapport aux éléments
    calculated_total = sum(item["total_price"] for item in invoice_data["items"])
    if invoice_data["total"] and abs(calculated_total - invoice_data["total"]) > 0.01:
        print(f"⚠️ Incohérence dans le total: {invoice_data['total']} vs {calculated_total} calculé")

    print("✅ Données de la facture extraites avec succès.")
    
    # Validation du JSON avant retour
    try:
        # S'assurer que les données sont bien sérialisables
        test_json = json.dumps(invoice_data, ensure_ascii=False, indent=2)
        # Parser le JSON pour vérifier sa validité
        json.loads(test_json)
        return test_json
    except Exception as e:
        print(f"Erreur lors de la création du JSON: {e}")
        # Retourner une version simplifiée en cas d'erreur
        return json.dumps({"error": "Format JSON invalide", "message": str(e)})

#-------------- Creation des tables dans la base de données-----------
def create_tables():
    # Connexion à la base de données
    conn = psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT")
    )
    cur = conn.cursor()

    # Script SQL pour créer les tables dans un schéma spécifique
    create_table_query = """
    CREATE TABLE dylan.customer (
        id_client SERIAL PRIMARY KEY,
        nom VARCHAR(255),
        mail VARCHAR(255) UNIQUE,
        adresse TEXT,
        birthdate DATE,
        genre VARCHAR(50)
    );

    -- Table produit
    CREATE TABLE dylan.invoice_item (
        id_produit SERIAL PRIMARY KEY,
        nom VARCHAR(255),
        prix NUMERIC(10, 2)
    );

    -- Table facture
    CREATE TABLE dylan.invoice (
        id_facture SERIAL PRIMARY KEY,
        texte VARCHAR(255),
        date_facturation DATE,
        total NUMERIC(10, 2),
        id_client INTEGER REFERENCES dylan.customer(id_client)
    );

    -- Table achat (table de jonction)
    CREATE TABLE dylan.achat (
        id_produit INTEGER REFERENCES dylan.invoice_item(id_produit),
        id_client INTEGER REFERENCES dylan.customer(id_client),
        id_facture INTEGER REFERENCES dylan.invoice(id_facture),
        quantité INTEGER,
        PRIMARY KEY (id_produit, id_facture)
    );

    -- Table log
    CREATE TABLE dylan.log (
        id SERIAL PRIMARY KEY,
        time TIMESTAMP,
        fichier VARCHAR(255),
        erreur TEXT
    );
    """

    # Exécution du script SQL
    cur.execute(create_table_query)
    conn.commit()

    # Fermeture de la connexion
    cur.close()
    conn.close()

#-------------- Extract data text (base de données)--------------

def validate_date(date_str):
    """Valide et corrige une date au format YYYY-MM-DD."""
    if not date_str:
        return None
        
    try:
        # Vérifier le format
        if not re.match(r'^\d{4}-\d{1,2}-\d{1,2}$', date_str):
            return None
            
        # Extraire les composants
        year, month, day = map(int, date_str.split('-'))
        
        # Vérifier les plages valides
        if not (1900 <= year <= 2100):
            return None
        if not (1 <= month <= 12):
            # Correction du mois si hors limites
            month = min(12, max(1, month))
        if not (1 <= day <= 31):
            # Correction du jour si hors limites
            day = min(28, max(1, day))  # Utiliser 28 comme valeur sécurisée
            
        # Retourner la date corrigée
        return f"{year}-{month:02d}-{day:02d}"
    except Exception:
        return None

def extract_and_save_invoice_data_improved(image_path):
    """Extrait et enregistre les données améliorées d'une facture via OCR dans la base de données."""
    # Prétraitement amélioré de l'image
    processed_image = preprocess_image(image_path)
    if processed_image is None:
        return None

    # Configuration Tesseract améliorée
    custom_config = r'--oem 1 --psm 4 -l eng'
    
    # Réaliser OCR sur l'image améliorée
    raw_text = pytesseract.image_to_string(processed_image, config=custom_config)
    
    # Affichage du texte brut extrait
    print("🔍 Texte extrait après amélioration :\n", raw_text)

    # Dictionnaire pour stocker les résultats
    invoice_data = {
        "invoice_number": None,
        "issue_date": None,
        "client": None,
        "email": None,
        "address": None,
        "items": [],
        "total": None
    }

    # Nettoyage du texte brut
    # Normalisation des espaces et retours à la ligne
    raw_text = " ".join(raw_text.split())
    raw_text = raw_text.replace("\n\n", " ¶ ").replace("\n", " ")
    
    # Correction des erreurs fréquentes d'OCR
    corrections = {
        "Furo": "Euro", "Buro": "Euro", "Bure": "Euro", "Eure": "Euro",
        "Ernail": "Email", "Ernall": "Email", "Emai1": "Email", "Mali": "Email",
        "0rder": "Order", "lnvoice": "Invoice", "INV0ICE": "INVOICE",
        "B1ll": "Bill", "Bi11": "Bill", 
        "@gmai1.com": "@gmail.com", "@hotmai1.com": "@hotmail.com",
        "Ackiress": "Address", "Acdress": "Address", "Addre55": "Address"
    }
    
    for incorrect, correct in corrections.items():
        raw_text = raw_text.replace(incorrect, correct)
    
    # Reconstitution des retours à la ligne pour faciliter l'extraction
    raw_text = raw_text.replace(" ¶ ", "\n\n")

    # Extraction des informations clés avec regex améliorés
    invoice_match = re.search(r'INVOICE\s*[:#]?\s*([\w\/-]+)', raw_text, re.IGNORECASE)
    if invoice_match:
        invoice_data["invoice_number"] = invoice_match.group(1).strip()
    
    date_match = re.search(r'(?:Issue|Date)[:\s]+(\d{4}[-/]\d{1,2}[-/]\d{1,2})', raw_text, re.IGNORECASE)
    if date_match:
        date_str = date_match.group(1)
        date_parts = re.split(r'[-/]', date_str)
        if len(date_parts) == 3:
            invoice_data["issue_date"] = f"{date_parts[0]}-{date_parts[1].zfill(2)}-{date_parts[2].zfill(2)}"
    
    email_match = re.search(r'Email[:\s]+\s*([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', raw_text, re.IGNORECASE)
    if email_match:
        invoice_data["email"] = email_match.group(1).strip().lower()
    
    total_match = re.search(r'TOTAL\s+([\d\.,]+)\s+(?:Euro|EUR|€)', raw_text, re.IGNORECASE)
    if total_match:
        invoice_data["total"] = float(total_match.group(1).replace(",", "."))
    
    # Extraction des articles avec regex amélioré
    seen_items = set()  # Pour éviter les doublons
    item_matches = re.finditer(r'([A-Z][a-zA-Z\s\.\-\_\&]+?)\.?\s+(\d+)\s*x\s*([\d\.,]+)\s*(?:Euro|EUR|€)', raw_text)
    
    for match in item_matches:
        name, qty, price = match.groups()
        # Créer une clé unique pour cet article
        item_key = f"{name.strip()}_{qty}_{price}"
        
        # Vérifier si on a déjà traité cet article
        if item_key not in seen_items:
            seen_items.add(item_key)
            try:
                invoice_data["items"].append({
                    "name": name.strip(),
                    "quantity": int(qty),
                    "unit_price": float(price.replace(",", ".")),
                    "total_price": int(qty) * float(price.replace(",", "."))
                })
            except ValueError:
                print(f"Erreur lors de l'extraction de l'article: {match.group()}")
    
    # Extraction des informations personnelles avec regex amélioré
    client_match = re.search(r'Bill to\s*(.+?)(?=\s*Email|\s*Address|\n)', raw_text, re.IGNORECASE)
    if client_match:
        invoice_data["client"] = client_match.group(1).strip()
    
    address_label_match = re.search(r'Address[:\s]+', raw_text, re.IGNORECASE)
    if address_label_match:
        address_start = address_label_match.end()
        
        # Trouver la fin de l'adresse (avant le premier article ou le total)
        items_start = []
        item_matches = re.finditer(r'([A-Z][a-zA-Z\s\.\-\_\&]+?)\.?\s+(\d+)\s*x\s*([\d\.,]+)\s*(?:Euro|EUR|€)', raw_text)
        for match in item_matches:
            items_start.append(match.start())
        
        total_match = re.search(r'TOTAL\s+([\d\.,]+)\s+(?:Euro|EUR|€)', raw_text, re.IGNORECASE)
        if total_match:
            items_start.append(total_match.start())
        
        address_end = len(raw_text)
        if items_start:
            address_end = min(items_start)
        
        if address_start < address_end:
            address_text = raw_text[address_start:address_end].strip()
            # Nettoyer l'adresse
            address_text = re.sub(r'\s+', ' ', address_text)
            invoice_data["address"] = address_text
    
    # Vérification de la cohérence des données avant enregistrement
    if not invoice_data["invoice_number"]:
        print("⚠️ Attention: Numéro de facture non détecté!")
    
    # Validation du total par rapport aux éléments
    calculated_total = sum(item["total_price"] for item in invoice_data["items"])
    if invoice_data["total"] and abs(calculated_total - invoice_data["total"]) > 0.01:
        print(f"⚠️ Incohérence dans le total: {invoice_data['total']} vs {calculated_total} calculé")

    # Enregistrement des données améliorées dans la base de données
    save_invoice_data_to_db_improved(invoice_data)
    
    print("✅ Données de la facture extraites et enregistrées avec succès.")
    return invoice_data

def save_invoice_data_to_db_improved(invoice_data):
    """Enregistre les données de la facture dans la base de données."""
    # Connexion à la base de données
    conn = psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT")
    )
    cur = conn.cursor()

    try:
        # Validation de la date avant insertion
        valid_date = validate_date(invoice_data.get("issue_date"))
        if not valid_date:
            print(f"⚠️ Date invalide détectée: {invoice_data.get('issue_date')}. Utilisation de la date du jour.")
            # Utiliser la date du jour comme alternative
            valid_date = time.strftime("%Y-%m-%d")
            
        # Vérification et insertion/mise à jour des données du client
        customer_id = None
        
        # Vérifier si l'email existe avant de faire la requête
        if invoice_data.get("email"):
            cur.execute("""
                SELECT id_client FROM dylan.customer WHERE mail = %s
            """, (invoice_data["email"],))
            customer = cur.fetchone()
            
            if customer:
                customer_id = customer[0]
                print(f"Client existant trouvé avec l'ID: {customer_id}")
                # Mise à jour des informations du client existant
                cur.execute("""
                    UPDATE dylan.customer SET nom = %s, adresse = %s WHERE id_client = %s
                """, (invoice_data["client"], invoice_data["address"], customer_id))
                print("Informations du client mises à jour")
        
        # Si le client n'existe pas ou si l'email n'est pas disponible, créer un nouveau client
        if not customer_id:
            print("Création d'un nouveau client...")
            
            # Valider les données du client avant insertion
            client_name = invoice_data.get("client", "Client inconnu")
            client_email = invoice_data.get("email", f"inconnu_{int(time.time())}@placeholder.com")
            client_address = invoice_data.get("address", "Adresse inconnue")
            
            try:
                cur.execute("""
                    INSERT INTO dylan.customer (nom, mail, adresse)
                    VALUES (%s, %s, %s)
                    RETURNING id_client
                """, (client_name, client_email, client_address))
                customer_id = cur.fetchone()[0]
                print(f"Nouveau client créé avec l'ID: {customer_id}")
            except psycopg2.Error as e:
                # Gérer les erreurs potentielles lors de l'insertion
                print(f"Erreur lors de la création du client: {e}")
                # Créer une entrée de journal pour l'erreur
                cur.execute("""
                    INSERT INTO dylan.log (time, fichier, erreur)
                    VALUES (NOW(), 'save_invoice_data_to_db', %s)
                """, (f"Erreur création client: {e}",))
                conn.commit()
                # Créer un client générique pour pouvoir continuer
                cur.execute("""
                    INSERT INTO dylan.customer (nom, mail, adresse)
                    VALUES ('Client temporaire', 'temp_client@placeholder.com', 'À compléter')
                    RETURNING id_client
                """)
                customer_id = cur.fetchone()[0]
                print(f"Client temporaire créé avec l'ID: {customer_id}")
        
        # Vérification et insertion/mise à jour des données de la facture
        cur.execute("""
            SELECT id_facture FROM dylan.invoice WHERE texte = %s
        """, (invoice_data["invoice_number"],))
        invoice = cur.fetchone()
        
        if invoice:
            invoice_id = invoice[0]
            cur.execute("""
                UPDATE dylan.invoice SET date_facturation = %s, total = %s, id_client = %s WHERE id_facture = %s
            """, (valid_date, invoice_data["total"], customer_id, invoice_id))
        else:
            cur.execute("""
                INSERT INTO dylan.invoice (texte, date_facturation, total, id_client)
                VALUES (%s, %s, %s, %s)
                RETURNING id_facture
            """, (invoice_data["invoice_number"], valid_date, invoice_data["total"], customer_id))
            invoice_id = cur.fetchone()[0]

        # Insertion des articles pour cette facture
        for item in invoice_data["items"]:
            # Vérifier si le produit existe déjà
            cur.execute("""
                SELECT id_produit FROM dylan.invoice_item WHERE nom = %s
            """, (item["name"],))
            product = cur.fetchone()
            
            if product:
                product_id = product[0]
                # Mise à jour du prix si nécessaire
                cur.execute("""
                    UPDATE dylan.invoice_item SET prix = %s WHERE id_produit = %s
                """, (item["unit_price"], product_id))
            else:
                # Création d'un nouveau produit
                cur.execute("""
                    INSERT INTO dylan.invoice_item (nom, prix)
                    VALUES (%s, %s)
                    RETURNING id_produit
                """, (item["name"], item["unit_price"]))
                product_id = cur.fetchone()[0]
            
            # Association du produit à la facture et au client
            cur.execute("""
                INSERT INTO dylan.achat (id_produit, id_client, id_facture, quantité)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (id_produit, id_facture) DO UPDATE 
                SET quantité = %s
            """, (product_id, customer_id, invoice_id, item["quantity"], item["quantity"]))

        # Validation des transactions
        conn.commit()
        print("Données de la facture enregistrées dans la base de données.")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Erreur lors de l'enregistrement de la facture {invoice_data.get('invoice_number')}: {e}")
        # Journalisation de l'erreur
        try:
            cur.execute("""
                INSERT INTO dylan.log (time, fichier, erreur)
                VALUES (NOW(), 'save_invoice_data_to_db', %s)
            """, (f"Erreur facture {invoice_data.get('invoice_number')}: {e}",))
            conn.commit()
        except:
            pass
    finally:
        # Fermeture de la connexion
        cur.close()
        conn.close()

#-------------- Extract data QR code--------------
def extract_data_qrcode(image_path):
    """Extrait les données d'un QR code et les enregistre dans la base de données."""
    img = Image.open(image_path)
    result = decode(img)
    
    if not result:
        print("Aucun QR code détecté dans l'image.")
        return None
    
    qr_data = {}
    for code in result:
        data_str = code.data.decode("utf-8")
        print(f"Données brutes du QR code : {data_str}")
        
        # Traitement des lignes du QR code
        lines = data_str.strip().split('\n')
        for line in lines:
            if ':' in line:
                parts = line.split(':', 1)
                key = parts[0].strip()
                value = parts[1].strip()
                
                if key == "INVOICE":
                    qr_data["invoice_number"] = value
                elif key == "DATE":
                    # Extraction de la date (sans l'heure)
                    date_parts = value.split(' ')[0]
                    qr_data["issue_date"] = date_parts
                elif key == "CUST":
                    # Extraction du genre et de la date de naissance
                    if "," in value and "birth" in value:
                        genre = value.split(',')[0].strip()
                        birth_date = value.split('birth')[1].strip()
                        qr_data["genre"] = genre
                        qr_data["birthdate"] = birth_date
    
    # Si on a trouvé un numéro de facture, mettre à jour les infos client
    if "invoice_number" in qr_data:
        update_customer_from_qr(qr_data)
        print("✅ Informations extraites du QR code:", qr_data)
        return qr_data
    else:
        print("❌ Aucune information de facture trouvée dans le QR code.")
        return None

def update_customer_from_qr(qr_data):
    """Met à jour les informations client à partir des données du QR code."""
    # Connexion à la base de données
    conn = psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT")
    )
    cur = conn.cursor()
    
    try:
        # Rechercher la facture par son numéro
        cur.execute("""
            SELECT id_facture, id_client FROM dylan.invoice 
            WHERE texte = %s
        """, (qr_data["invoice_number"],))
        
        invoice = cur.fetchone()
        
        if invoice:
            invoice_id, customer_id = invoice
            print(f"Facture trouvée avec ID: {invoice_id}, Client ID: {customer_id}")
            
            # Mise à jour des informations client
            cur.execute("""
                UPDATE dylan.customer 
                SET genre = %s, birthdate = %s
                WHERE id_client = %s
            """, (qr_data.get("genre"), qr_data.get("birthdate"), customer_id))
            
            conn.commit()
            print(f"✅ Informations client mises à jour: Genre={qr_data.get('genre')}, Naissance={qr_data.get('birthdate')}")
        else:
            print(f"❌ Aucune facture trouvée avec le numéro: {qr_data['invoice_number']}")
    
    except Exception as e:
        conn.rollback()
        print(f"❌ Erreur lors de la mise à jour: {e}")
        cur.execute("""
            INSERT INTO dylan.log (time, fichier, erreur)
            VALUES (NOW(), 'update_customer_from_qr', %s)
        """, (str(e),))
        conn.commit()
    
    finally:
        cur.close()
        conn.close()
        
def invoice_data_log_error(invoice_data, image_path, log_error_dir="log_error"):
    """Enregistre les erreurs de données de facture dans un fichier JSON."""
    # Créer le répertoire de sortie s'il n'existe pas
    if not os.path.exists(log_error_dir):
        os.makedirs(log_error_dir)  
        
    # Extraire le nom du fichier à partir du chemin d'image
    filename = os.path.basename(image_path).split('.')[0]
    log_error_path = os.path.join(log_error_dir, f"{filename}.json")
    
    # Écrire les données JSON dans le fichier
    with open(log_error_path, 'w', encoding='utf-8') as f:
        json.dump(invoice_data, f, indent=4)
        
    print(f"✅ Erreurs enregistrées dans: {log_error_path}")
    return log_error_path

def save_invoice_data_to_file(invoice_data, image_path, output_dir="output_data"):
    """Enregistre les données de facture dans un fichier JSON."""
    # Créer le répertoire de sortie s'il n'existe pas
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Extraire le nom du fichier à partir du chemin d'image
    filename = os.path.basename(image_path).split('.')[0]
    output_path = os.path.join(output_dir, f"{filename}.json")
    
    # Écrire le contenu JSON dans le fichier
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(invoice_data)
    
    print(f"✅ Données sauvegardées dans: {output_path}")
    return output_path

if __name__ == "__main__":
    #--------------Test extract data données textte--------------
    #--------------Test 1--------------
    def test_1fichier():
        image_path = r"c:\Users\dd758\Formation_IA_Greta\OCR_Projet\OCR\data\facture_2019\FAC_2019_0139-390.png"
        image_path2 = r"c:\Users\dd758\Formation_IA_Greta\OCR_Projet\OCR\data\facture_2023\FAC_2023_0496-533.png"
        json_result = extract_invoice_data_to_json(image_path)
        print(json_result)
        # Enregistrer le résultat dans un fichier
        if json_result:
            save_invoice_data_to_file(json_result, image_path)
    
    #--------------Test 2--------------
    def test_allfichier():
        annee = [2018]
        # Créer un dossier pour les résultats par année
        base_output_dir = "resultats_json"
        if not os.path.exists(base_output_dir):
            os.makedirs(base_output_dir)
            
        for annees in annee:
            dossier_factures = fr"c:\Users\dd758\Formation_IA_Greta\OCR_Projet\OCR\data\facture_{annees}"
            output_dir = os.path.join(base_output_dir, f"facture_{annees}")
            
            # Parcours de tous les fichiers dans le dossier
            for fichier in os.listdir(dossier_factures):
                if fichier.endswith('.png'):
                    image_path = os.path.join(dossier_factures, fichier)
                    print(f"Traitement de la facture : {image_path}")
                    parsed_data = extract_invoice_data_to_json(image_path)
                    if parsed_data:
                        # Enregistrer les données extraites
                        save_invoice_data_to_file(parsed_data, image_path, output_dir)
                    print("\n📄 Données extraites et formatées :\n", parsed_data)
    #--------------Test extract data QR code--------------
    def test_qrcode():
        image_path = r"c:\Users\dd758\Formation_IA_Greta\OCR_Projet\OCR\data\facture_2018\FAC_2018_0001-654.png"
        qr_data = extract_data_qrcode(image_path)
        print("Données extraites du QR code :", qr_data)
    #test_qrcode()
    #-------------- Text extract data (base de données)(1 fichier)--------------
    def test_1fichier_db():
        image_path = r"c:\Users\dd758\Formation_IA_Greta\OCR_Projet\OCR\data\facture_2018\FAC_2018_0001-654.png"
        extract_and_save_invoice_data_improved(image_path)
        
    #test_1fichier_db()
    #-------------- Text extract data (base de données)(tous les fichiers)--------------
    def test_allfichier_db():
        annee = [2024]
        for annee in annee:
            dossier_factures = fr"c:\Users\dd758\Formation_IA_Greta\OCR_Projet\OCR\data\facture_{annee}"
            print(f"Traitement des factures de l'année {annee}...")
            for fichier in os.listdir(dossier_factures):
                if fichier.endswith('.png'):
                    image_path = os.path.join(dossier_factures, fichier)
                    print(f"\nTraitement de {fichier}...")
                    try:
                        invoice_data = extract_and_save_invoice_data_improved(image_path)
                    except Exception as e:
                        print(f"❌ Erreur lors du traitement de {fichier}: {e}")
                        # Créer un dictionnaire d'erreur à enregistrer
                        error_data = {
                            "error": str(e),
                            "file": fichier,
                            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                            "path": image_path
                        }
                        # Enregistrer les erreurs dans un fichier JSON
                        invoice_data_log_error(error_data, image_path)
                        # Continuer avec le fichier suivant
                        continue
            print(f"✅ Traitement terminé pour l'année {annee}")
    #test_allfichier_db()
    #-------------- Test extract data QR code--------------
    def test_qrcode_db():
        annee = [2018, 2019, 2020, 2021, 2022, 2023, 2024]
        for annee in annee:
            dossier_factures = fr"c:\Users\dd758\Formation_IA_Greta\OCR_Projet\OCR\data\facture_{annee}"
            print(f"Traitement des factures de l'année {annee}...")
            for fichier in os.listdir(dossier_factures):
                if fichier.endswith('.png'):
                    image_path = os.path.join(dossier_factures, fichier)
                    print(f"\nTraitement de {fichier}...")
                    try:
                        extract_data_qrcode(image_path)
                    except Exception as e:
                        print(f"❌ Erreur lors du traitement de {fichier}: {e}")
                        #Continuer avec le fichier suivant
                        continue
            print(f"✅ Traitement terminé pour l'année {annee}")
    #test_qrcode_db()
    #-------------- Creation des tables--------------
    def test_create_tables():
        create_tables()
    #test_create_tables()
