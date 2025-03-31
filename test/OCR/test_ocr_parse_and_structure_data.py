from base64 import decode
import os
from tkinter import Image
import cv2
import pytesseract
import re
import json
import numpy as np
import csv
from dotenv import load_dotenv
import psycopg2
from pyzbar.pyzbar import decode

load_dotenv()

def preprocess_image(image_path):
    """Améliore l'image avant OCR."""
    image = cv2.imread(image_path)
    if image is None:
        print(f"Erreur : Impossible de charger l'image à partir de {image_path}")
        return None

    # Conversion en niveaux de gris
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Filtre de netteté pour améliorer le contraste
    kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
    sharp = cv2.filter2D(gray, -1, kernel)

    # Binarisation avec OTSU pour adapter le seuil dynamiquement
    _, thresh = cv2.threshold(sharp, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    return thresh

def extract_invoice_data(image_path):
    """Extrait et structure les données d'une facture via OCR."""
    # Prétraitement de l'image
    processed_image = preprocess_image(image_path)
    if processed_image is None:
        return None

    # Appliquer Tesseract avec un mode adapté
    custom_config = r'--psm 4'  # Mode adapté aux factures semi-structurées
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

    # Correction manuelle des erreurs fréquentes
    raw_text = raw_text.replace("Furo", "Euro").replace("Buro", "Euro")

    # Regex pour extraire les informations clés
    invoice_number_match = re.search(r'INVOICE\s+([\w/]+)', raw_text)
    date_match = re.search(r'Issue date (\d{4}-\d{2}-\d{2})', raw_text)
    email_match = re.search(r'Email\s+([\w\.\-]+@[\w\.\-]+)', raw_text)
    total_match = re.search(r'TOTAL\s+([\d\.,]+)\s+Euro', raw_text)

    # Extraction des données
    if invoice_number_match:
        invoice_data["invoice_number"] = invoice_number_match.group(1)
    if date_match:
        invoice_data["issue_date"] = date_match.group(1)
    if email_match:
        invoice_data["email"] = email_match.group(1)
    if total_match:
        invoice_data["total"] = float(total_match.group(1).replace(",", "."))

    # Extraction des articles (quantité x prix)
    item_pattern = re.findall(r'(.+?)\s+(\d+)\s*x\s*([\d\.,]+)\s*Euro', raw_text)
    for item in item_pattern:
        name, qty, price = item
        invoice_data["items"].append({
            "name": name.strip(),
            "quantity": int(qty),
            "unit_price": float(price.replace(",", ".")),
            "total_price": int(qty) * float(price.replace(",", "."))
        })

    # Extraction des informations personnelles
    client_match = re.search(r'Bill to\s*(.+)', raw_text)
    address_match = re.search(r'Address\s*(.+?)(?=\n\n|$)', raw_text, re.DOTALL)

    if client_match:
        invoice_data["client"] = client_match.group(1).strip()
    if address_match:
        invoice_data["address"] = address_match.group(1).strip().replace("\n", " ")

    # Écrire les données clients dans un fichier CSV
    client_csv_file_path = r'c:\Users\dd758\Formation_IA_Greta\OCR_Projet\OCR\resultats\resultat_client_ocr.csv'
    with open(client_csv_file_path, mode='a', newline='', encoding='utf-8') as client_csvfile:
        client_fieldnames = ['invoice_number', 'issue_date', 'client', 'email', 'address', 'total']
        client_writer = csv.DictWriter(client_csvfile, fieldnames=client_fieldnames)

        # Écrire l'en-tête seulement si le fichier est vide
        if client_csvfile.tell() == 0:
            client_writer.writeheader()
        client_writer.writerow({
            'invoice_number': invoice_data["invoice_number"],
            'issue_date': invoice_data["issue_date"],
            'client': invoice_data["client"],
            'email': invoice_data["email"],
            'address': invoice_data["address"],
            'total': invoice_data["total"]
        })

    # Écrire les données des produits dans un fichier CSV
    product_csv_file_path = r'c:\Users\dd758\Formation_IA_Greta\OCR_Projet\OCR\resultats\resultat_produit_ocr.csv'
    with open(product_csv_file_path, mode='a', newline='', encoding='utf-8') as product_csvfile:
        item_fieldnames = ['name', 'quantity', 'unit_price', 'total_price']
        item_writer = csv.DictWriter(product_csvfile, fieldnames=item_fieldnames)

        # Écrire l'en-tête seulement si le fichier est vide
        if product_csvfile.tell() == 0:
            item_writer.writeheader()
        for item in invoice_data["items"]:
            item_writer.writerow(item)

    print(f"Données clients extraites et enregistrées dans {client_csv_file_path}")
    print(f"Données des produits extraites et enregistrées dans {product_csv_file_path}")
    
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
    CREATE SCHEMA IF NOT EXISTS dylan;

    CREATE TABLE dylan.CUSTOMER (
    id SERIAL,
    name VARCHAR(255),
    address VARCHAR(500),
    email VARCHAR(500) PRIMARY KEY,
    sexe VARCHAR(12),
    date_naissance DATE
    );

    CREATE TABLE dylan.INVOICE (
        id SERIAL PRIMARY KEY,
        orderNumber INT,
        date DATE,
        total FLOAT,
        customer_id INT,
        FOREIGN KEY (customer_id) REFERENCES dylan.CUSTOMER(id)
    );

    CREATE TABLE dylan.INVOICE_ITEM (
        id SERIAL PRIMARY KEY,
        product VARCHAR(255),
        quantity INT,
        pricePerUnit FLOAT,
        invoice_id INT,
        FOREIGN KEY (invoice_id) REFERENCES dylan.INVOICE(id)
    );
    """

    # Exécution du script SQL
    cur.execute(create_table_query)
    conn.commit()

    # Fermeture de la connexion
    cur.close()
    conn.close()

def save_invoice_data_to_db(invoice_data):
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

    # Vérification et insertion/mise à jour des données du client
    cur.execute("""
        SELECT id FROM dylan.CUSTOMER WHERE email = %s
    """, (invoice_data["email"],))
    customer = cur.fetchone()
    
    if customer:
        customer_id = customer[0]
        cur.execute("""
            UPDATE dylan.CUSTOMER SET name = %s, address = %s WHERE id = %s
        """, (invoice_data["client"], invoice_data["address"], customer_id))
    else:
        cur.execute("""
            INSERT INTO dylan.CUSTOMER (name, address, email)
            VALUES (%s, %s, %s)
            RETURNING id
        """, (invoice_data["client"], invoice_data["address"], invoice_data["email"]))
        customer_id = cur.fetchone()[0]

    # Vérification et insertion/mise à jour des données de la facture
    cur.execute("""
        SELECT id FROM dylan.INVOICE WHERE orderNumber = %s
    """, (invoice_data["invoice_number"],))
    invoice = cur.fetchone()
    
    if invoice:
        invoice_id = invoice[0]
        cur.execute("""
            UPDATE dylan.INVOICE SET date = %s, total = %s, customer_id = %s WHERE id = %s
        """, (invoice_data["issue_date"], invoice_data["total"], customer_id, invoice_id))
    else:
        cur.execute("""
            INSERT INTO dylan.INVOICE (orderNumber, date, total, customer_id)
            VALUES (%s, %s, %s, %s)
            RETURNING id
        """, (invoice_data["invoice_number"], invoice_data["issue_date"], invoice_data["total"], customer_id))
        invoice_id = cur.fetchone()[0]

    # Suppression des articles existants et insertion des nouveaux articles
    cur.execute("""
        DELETE FROM dylan.INVOICE_ITEM WHERE invoice_id = %s
    """, (invoice_id,))
    
    for item in invoice_data["items"]:
        cur.execute("""
            INSERT INTO dylan.INVOICE_ITEM (product, quantity, pricePerUnit, invoice_id)
            VALUES (%s, %s, %s, %s)
        """, (item["name"], item["quantity"], item["unit_price"], invoice_id))

    # Validation des transactions
    conn.commit()

    # Fermeture de la connexion
    cur.close()
    conn.close()

    print("Données de la facture enregistrées dans la base de données.")

def extract_and_save_invoice_data(image_path):
    """Extrait et enregistre les données d'une facture via OCR dans la base de données."""
    # Prétraitement de l'image
    processed_image = preprocess_image(image_path)
    if processed_image is None:
        return None

    # Appliquer Tesseract avec un mode adapté
    custom_config = r'--psm 4'  # Mode adapté aux factures semi-structurées
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

    # Correction manuelle des erreurs fréquentes
    raw_text = raw_text.replace("Furo", "Euro").replace("Buro", "Euro")

    # Regex pour extraire les informations clés
    invoice_number_match = re.search(r'INVOICE\s+([\w/]+)', raw_text)
    date_match = re.search(r'Issue date (\d{4}-\d{2}-\d{2})', raw_text)
    email_match = re.search(r'Email\s+([\w\.\-]+@[\w\.\-]+)', raw_text)
    total_match = re.search(r'TOTAL\s+([\d\.,]+)\s+Euro', raw_text)

    # Extraction des données
    if invoice_number_match:
        invoice_data["invoice_number"] = invoice_number_match.group(1)
    if date_match:
        invoice_data["issue_date"] = date_match.group(1)
    if email_match:
        invoice_data["email"] = email_match.group(1)
    if total_match:
        invoice_data["total"] = float(total_match.group(1).replace(",", "."))

    # Extraction des articles (quantité x prix)
    item_pattern = re.findall(r'(.+?)\s+(\d+)\s*x\s*([\d\.,]+)\s*Euro', raw_text)
    for item in item_pattern:
        name, qty, price = item
        invoice_data["items"].append({
            "name": name.strip(),
            "quantity": int(qty),
            "unit_price": float(price.replace(",", ".")),
            "total_price": int(qty) * float(price.replace(",", "."))
        })

    # Extraction des informations personnelles
    client_match = re.search(r'Bill to\s*(.+)', raw_text)
    address_match = re.search(r'Address\s*(.+?)(?=\n\n|$)', raw_text, re.DOTALL)

    if client_match:
        invoice_data["client"] = client_match.group(1).strip()
    if address_match:
        invoice_data["address"] = address_match.group(1).strip().replace("\n", " ")

    # Enregistrement des données dans la base de données
    save_invoice_data_to_db(invoice_data)

    print("Données de la facture extraites et enregistrées dans la base de données.")
# ------------------- Test de la fonction sur 1 fichier -------------------
# Chemin de l'image de la facture
def test_1fichier():
    image_path = r"c:\Users\dd758\Formation_IA_Greta\OCR_Projet\OCR\data\facture_2018\FAC_2018_0001-654.png"

    # Extraction et affichage
    parsed_data = extract_and_save_invoice_data(image_path)
    print("\n📄 Données extraites et formatées :\n", parsed_data)

# ------------------- Test de la fonction sur tous les fichiers -------------------
# Chemin du dossier contenant les images des factures
def test_allfichier():
    annee = [2018, 2019, 2020, 2021, 2022, 2023, 2024]
    for annees in annee:
        dossier_factures = fr"c:\Users\dd758\Formation_IA_Greta\OCR_Projet\OCR\data\facture_{annees}"   

        # Parcours de tous les fichiers dans le dossier
        for fichier in os.listdir(dossier_factures):
            if fichier.endswith('.png'):
                image_path = os.path.join(dossier_factures, fichier)
                print(f"Traitement de la facture : {image_path}")
                parsed_data = extract_and_save_invoice_data(image_path)
                print("\n📄 Données extraites et formatées :\n", parsed_data)
                
def decode_qrcode():
    annee = [2018]
    result = []

    for annee in annee:
        dossier_factures = fr"c:\Users\dd758\Formation_IA_Greta\OCR_Projet\OCR\data\facture_{annee}"  
        #Parcours de tous les fichiers dans le dossier
        for fichier in os.listdir(dossier_factures):
            if fichier.endswith('.png'):
                image_path = os.path.join(dossier_factures, fichier)
                img = Image.open(image_path)
                decoded_result = decode(img)
                for i in decoded_result:
                    result.append(i.data.decode("utf-8"))

if __name__ == "__main__":
    test_allfichier()

