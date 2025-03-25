"""
Module d'extraction de données de factures pour le traitement OCR.
"""

import re
import json
import logging
import os
import pytesseract
from datetime import datetime
from back_end.classe.preprocess_image import preprocessing_image

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def perform_ocr(image_path):
    """
    Prétraite l'image et effectue l'OCR.
    
    Args:
        image_path: Chemin vers l'image de la facture
        
    Returns:
        Texte extrait par OCR ou None en cas d'échec
    """
    processed_image = preprocessing_image(image_path)
    if processed_image is None:
        return None

    # Configuration Tesseract améliorée
    custom_config = r'--oem 1 --psm 4 -l eng'
    
    # Réaliser OCR sur l'image améliorée
    raw_text = pytesseract.image_to_string(processed_image, config=custom_config)
    
    # Affichage du texte brut extrait
    logger.info("🔍 Texte extrait après amélioration :\n%s", raw_text)
    
    return raw_text

def clean_ocr_text(raw_text):
    """
    Nettoie le texte extrait par OCR.
    
    Args:
        raw_text: Texte brut extrait par OCR
        
    Returns:
        Texte nettoyé
    """
    # Normalisation des espaces et retours à la ligne
    cleaned_text = " ".join(raw_text.split())
    cleaned_text = cleaned_text.replace("\n\n", " ¶ ").replace("\n", " ")
    
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
        cleaned_text = cleaned_text.replace(incorrect, correct)
    
    # Reconstitution des retours à la ligne pour faciliter l'extraction
    cleaned_text = cleaned_text.replace(" ¶ ", "\n\n")
    
    return cleaned_text

def extract_invoice_number_from_filename(image_path):
    """
    Extrait le numéro de facture à partir du nom du fichier.
    
    Args:
        image_path: Chemin vers l'image de la facture
        
    Returns:
        Numéro de facture extrait ou None si non trouvé
    """
    filename = os.path.basename(image_path)
    file_invoice_number = None
    
    filename_match = re.search(r'FAC_(\d{4})_(\d{4})-?(\d{3})?', filename)
    if filename_match:
        year = filename_match.group(1)
        number = filename_match.group(2)
        file_invoice_number = f"FAC/{year}/{number}"
        logger.info(f"📄 Numéro de facture extrait du nom de fichier: {file_invoice_number}")
    
    return file_invoice_number

def extract_invoice_number(text, image_path=None):
    """
    Extrait le numéro de facture du texte OCR et/ou du nom de fichier.
    
    Args:
        text: Texte OCR extrait
        image_path: Chemin vers l'image de la facture (optionnel)
        
    Returns:
        Numéro de facture extrait ou None si non trouvé
    """
    # D'abord essayer d'extraire du nom de fichier si disponible
    invoice_number = None
    if image_path:
        invoice_number = extract_invoice_number_from_filename(image_path)
    
    # Si pas trouvé dans le nom de fichier, chercher dans le texte
    if not invoice_number:
        # Patterns spécifiques au format FAC/YYYY/XXXX
        fac_pattern = re.search(r'(FAC/\d{4}/\d{4})', text)
        if fac_pattern:
            invoice_number = fac_pattern.group(1).strip()
            return invoice_number
            
        # Patterns génériques pour différents formats de numéros de facture
        patterns = [
            r'INVOICE\s*(?:FAC/)?(\d{4}(?:[,/]\d+)?)',
            r'Invoice\s*#?\s*(\w+[-/]?\w+)',
            r'Invoice\s*Number\s*:?\s*(\w+[-/]?\w+)',
            r'Invoice\s*No\s*\.?\s*:?\s*(\w+[-/]?\w+)',
            r'Invoice\s*ID\s*:?\s*(\w+[-/]?\w+)',
            r'Facture\s*N°\s*:?\s*(\w+[-/]?\w+)',  # French
            r'Rechnung\s*Nr\s*\.?\s*:?\s*(\w+[-/]?\w+)',  # German
            r'Factura\s*N°\s*:?\s*(\w+[-/]?\w+)',  # Spanish
            r'Fattura\s*N°\s*:?\s*(\w+[-/]?\w+)',  # Italian
            r'#\s*(\w+[-/]?\w+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                invoice_number_text = match.group(1).strip().replace(',', '/')
                if 'FAC/' in text:
                    invoice_number = f"FAC/{invoice_number_text}"
                else:
                    invoice_number = invoice_number_text
                break
    
    return invoice_number

def extract_date(text):
    """
    Extrait la date d'émission de la facture.
    
    Args:
        text: Texte OCR extrait
        
    Returns:
        Date extraite au format YYYY-MM-DD ou None si non trouvée
    """
    # Patterns spécifiques pour la date d'émission
    date_match = re.search(r'(?:Issue|Date)[:\s]+(\d{4}[-/]\d{1,2}[-/]\d{1,2})', text, re.IGNORECASE)
    if date_match:
        date_str = date_match.group(1)
        date_parts = re.split(r'[-/]', date_str)
        if len(date_parts) == 3:
            return f"{date_parts[0]}-{date_parts[1].zfill(2)}-{date_parts[2].zfill(2)}"
    
    # Patterns génériques pour différents formats de date
    patterns = [
        # ISO format: YYYY-MM-DD
        r'(?:Date|Issue Date|Invoice Date|Issued|Dated)\s*:?\s*(\d{4}-\d{1,2}-\d{1,2})',
        
        # US format: MM/DD/YYYY
        r'(?:Date|Issue Date|Invoice Date|Issued|Dated)\s*:?\s*(\d{1,2}/\d{1,2}/\d{4})',
        
        # European format: DD/MM/YYYY
        r'(?:Date|Issue Date|Invoice Date|Issued|Dated)\s*:?\s*(\d{1,2}/\d{1,2}/\d{4})',
        
        # European format: DD.MM.YYYY
        r'(?:Date|Issue Date|Invoice Date|Issued|Dated)\s*:?\s*(\d{1,2}\.\d{1,2}\.\d{4})',
        
        # Written format: Month DD, YYYY
        r'(?:Date|Issue Date|Invoice Date|Issued|Dated)\s*:?\s*([A-Za-z]+\s+\d{1,2},?\s+\d{4})'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            date_str = match.group(1).strip()
            
            try:
                # Essayer de parser la date
                if '-' in date_str:
                    # Format ISO
                    year, month, day = map(int, date_str.split('-'))
                    return f"{year:04d}-{month:02d}-{day:02d}"
                elif '/' in date_str:
                    # Format US ou européen
                    parts = date_str.split('/')
                    if len(parts[2]) == 4:  # L'année est en position 2
                        if int(parts[0]) > 12:  # Le jour est en position 0
                            day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
                        else:  # Le mois est en position 0
                            month, day, year = int(parts[0]), int(parts[1]), int(parts[2])
                        return f"{year:04d}-{month:02d}-{day:02d}"
                elif '.' in date_str:
                    # Format européen avec points
                    day, month, year = map(int, date_str.split('.'))
                    return f"{year:04d}-{month:02d}-{day:02d}"
                else:
                    # Format écrit
                    date_obj = datetime.strptime(date_str, "%B %d, %Y")
                    return date_obj.strftime("%Y-%m-%d")
            except (ValueError, IndexError):
                # Si l'analyse échoue, continuer avec le pattern suivant
                continue
    
    return None

def extract_total_amount(text):
    """
    Extrait le montant total de la facture.
    
    Args:
        text: Texte OCR extrait
        
    Returns:
        Montant total extrait (float) ou None si non trouvé
    """
    # Pattern spécifique pour le format Euro
    total_match = re.search(r'TOTAL\s+([\d\.,]+)\s+(?:Euro|EUR|€)', text, re.IGNORECASE)
    if total_match:
        return float(total_match.group(1).replace(",", "."))
    
    # Patterns génériques pour différents formats de montant total
    patterns = [
        r'Total\s*:?\s*[$€£]?\s*([\d,]+\.\d{2})',
        r'Total\s*Amount\s*:?\s*[$€£]?\s*([\d,]+\.\d{2})',
        r'Amount\s*Due\s*:?\s*[$€£]?\s*([\d,]+\.\d{2})',
        r'Balance\s*Due\s*:?\s*[$€£]?\s*([\d,]+\.\d{2})',
        r'Grand\s*Total\s*:?\s*[$€£]?\s*([\d,]+\.\d{2})',
        r'Total\s*à\s*payer\s*:?\s*[$€£]?\s*([\d,]+\.\d{2})',  # French
        r'Gesamtbetrag\s*:?\s*[$€£]?\s*([\d,]+\.\d{2})',  # German
        r'Importe\s*Total\s*:?\s*[$€£]?\s*([\d,]+\.\d{2})',  # Spanish
        r'Importo\s*Totale\s*:?\s*[$€£]?\s*([\d,]+\.\d{2})'  # Italian
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            amount_str = match.group(1).strip()
            # Supprimer les virgules et convertir en float
            amount = float(amount_str.replace(',', ''))
            return amount
    
    return None

def extract_email(text):
    """
    Extrait l'adresse email du client.
    
    Args:
        text: Texte OCR extrait
        
    Returns:
        Adresse email extraite ou None si non trouvée
    """
    email_pattern = r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}'
    email_match = re.search(email_pattern, text)
    if email_match:
        email_extrait = email_match.group(0).strip().lower()
        if email_extrait:  # Vérification supplémentaire
            return email_extrait
        else:
            logger.warning("⚠️ Adresse email invalide détectée")
    
    return None

def extract_client_info(text):
    """
    Extrait les informations du client du texte OCR.
    
    Args:
        text: Texte OCR extrait
        
    Returns:
        Dictionnaire avec nom, email et adresse du client
    """
    client_info = {
        'name': None,
        'email': None,
        'address': None
    }
    
    # Extraire le nom du client
    name_patterns = [
        r'Bill to\s*(.+?)(?=\s*Email|\s*Address|\n)',
        r'(?:Bill To|Sold To|Customer|Client|Billed To)\s*:?\s*([A-Za-z0-9\s&]+)',
        r'(?:Bill To|Sold To|Customer|Client|Billed To)\s*:?\s*\n\s*([A-Za-z0-9\s&]+)'
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            client_info['name'] = match.group(1).strip()[:255]  # Limiter à 255 caractères
            break
    
    # Extraire l'email
    client_info['email'] = extract_email(text)
    
    # Extraire l'adresse
    address_label_match = re.search(r'Address[:\s]+', text, re.IGNORECASE)
    if address_label_match:
        address_start = address_label_match.end()
        
        # Trouver la fin de l'adresse (avant le premier article ou le total)
        items_start = []
        item_matches = re.finditer(r'([A-Z][a-zA-Z\s\.\-\_\&]+?)\.?\s+(\d+)\s*x\s*([\d\.,]+)\s*(?:Euro|EUR|€)', text)
        for match in item_matches:
            items_start.append(match.start())
        
        total_match = re.search(r'TOTAL\s+([\d\.,]+)\s+(?:Euro|EUR|€)', text, re.IGNORECASE)
        if total_match:
            items_start.append(total_match.start())
        
        address_end = len(text)
        if items_start:
            address_end = min(items_start)
        
        if address_start < address_end:
            address_text = text[address_start:address_end].strip()
            # Nettoyer l'adresse
            address_text = re.sub(r'\s+', ' ', address_text)
            # Limiter la longueur de l'adresse à 255 caractères
            client_info['address'] = address_text[:255]
    
    # Si l'adresse n'a pas été trouvée, essayer avec les patterns génériques
    if not client_info['address']:
        address_patterns = [
            r'(?:Address|Location|Billing Address)\s*:?\s*([A-Za-z0-9\s,.-]+)',
            r'(?:Bill To|Sold To|Customer|Client|Billed To)\s*:?\s*(?:[A-Za-z0-9\s&]+)\s*\n\s*([A-Za-z0-9\s,.-]+)'
        ]
        
        for pattern in address_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                client_info['address'] = match.group(1).strip()[:255]
                break
    
    return client_info

def extract_items(text):
    """
    Extrait les articles de la facture.
    
    Args:
        text: Texte OCR extrait
        
    Returns:
        Liste de dictionnaires avec les détails des articles
    """
    items = []
    seen_items = set()  # Pour éviter les doublons
    
    # Pattern spécifique pour le format Euro
    item_matches = re.finditer(r'([A-Z][a-zA-Z\s\.\-\_\&]+?)\.?\s+(\d+)\s*x\s*([\d\.,]+)\s*(?:Euro|EUR|€)', text)
    
    for match in item_matches:
        name, qty, price = match.groups()
        # Créer une clé unique pour cet article
        item_key = f"{name.strip()}_{qty}_{price}"
        
        # Vérifier si on a déjà traité cet article
        if item_key not in seen_items:
            seen_items.add(item_key)
            try:
                items.append({
                    "name": name.strip(),
                    "quantity": int(qty),
                    "unit_price": float(price.replace(",", ".")),
                    "total_price": int(qty) * float(price.replace(",", "."))
                })
            except ValueError:
                logger.error(f"Erreur lors de l'extraction de l'article: {match.group()}")
    
    # Si aucun article n'a été trouvé avec le pattern spécifique, essayer avec le pattern générique
    if not items:
        # Pattern générique: Description suivie de quantité, prix unitaire et total
        item_pattern = r'([A-Za-z0-9\s]+)\s+(\d+)\s*x\s*[$€£]?\s*([\d,]+\.\d{2})'
        
        matches = re.finditer(item_pattern, text)
        for match in matches:
            description = match.group(1).strip()
            quantity = int(match.group(2))
            unit_price = float(match.group(3).replace(',', ''))
            total_price = quantity * unit_price
            
            items.append({
                'name': description,
                'quantity': quantity,
                'unit_price': unit_price,
                'total_price': total_price
            })
    
    return items

def validate_invoice_data(invoice_data):
    """
    Valide les données extraites de la facture.
    
    Args:
        invoice_data: Dictionnaire avec les données extraites
        
    Returns:
        Dictionnaire avec les résultats de validation
    """
    validation = {
        'is_valid': True,
        'missing_fields': [],
        'warnings': []
    }
    
    # Vérifier les champs requis
    required_fields = ['invoice_number', 'issue_date', 'total']
    for field in required_fields:
        if not invoice_data.get(field):
            validation['is_valid'] = False
            validation['missing_fields'].append(field)
    
    # Vérifier si des articles sont présents
    if not invoice_data.get('items'):
        validation['warnings'].append('Aucun article trouvé')
    
    # Vérifier si le total correspond à la somme des articles
    if invoice_data.get('items') and invoice_data.get('total'):
        items_total = sum(item.get('total_price', 0) for item in invoice_data['items'])
        if abs(items_total - invoice_data['total']) > 0.01:
            validation['warnings'].append('Le montant total ne correspond pas à la somme des articles')
    
    return validation

def extract_invoice_data(ocr_text, image_path=None):
    """
    Extrait les données structurées de la facture à partir du texte OCR.
    
    Args:
        ocr_text: Texte OCR extrait
        image_path: Chemin vers l'image de la facture (optionnel)
        
    Returns:
        Dictionnaire avec les données extraites de la facture
    """
    try:
        # Nettoyer le texte OCR
        cleaned_text = clean_ocr_text(ocr_text)
        
        # Initialiser les données de la facture
        invoice_data = {
            'invoice_number': None,
            'issue_date': None,
            'client': None,
            'email': None,
            'address': None,
            'items': [],
            'total': None
        }
        
        # Extraire le numéro de facture
        invoice_data['invoice_number'] = extract_invoice_number(cleaned_text, image_path)
        
        # Extraire la date
        invoice_data['issue_date'] = extract_date(cleaned_text)
        
        # Extraire le montant total
        invoice_data['total'] = extract_total_amount(cleaned_text)
        
        # Extraire les informations du client
        client_info = extract_client_info(cleaned_text)
        invoice_data['client'] = client_info['name']
        invoice_data['email'] = client_info['email']
        invoice_data['address'] = client_info['address']
        
        # Extraire les articles
        invoice_data['items'] = extract_items(cleaned_text)
        
        # Valider les données extraites
        validation = validate_invoice_data(invoice_data)
        if not validation['is_valid']:
            logger.warning(f"Validation de la facture échouée: {validation['missing_fields']}")
        if validation['warnings']:
            logger.warning(f"Avertissements: {validation['warnings']}")
        
        return invoice_data
    
    except Exception as e:
        logger.error(f"Erreur lors de l'extraction des données de la facture: {str(e)}")
        return {}

def format_invoice_data(invoice_data, format_type='json'):
    """
    Formate les données de la facture pour la sortie.
    
    Args:
        invoice_data: Dictionnaire avec les données extraites
        format_type: Format de sortie ('json', 'text', ou 'html')
        
    Returns:
        Données de facture formatées
    """
    if format_type == 'json':
        return json.dumps(invoice_data, indent=2)
    
    elif format_type == 'text':
        text = []
        text.append("Numéro de facture: " + (invoice_data.get('invoice_number') or 'N/A'))
        text.append("Date d'émission: " + (invoice_data.get('issue_date') or 'N/A'))
        text.append("Client: " + (invoice_data.get('client') or 'N/A'))
        text.append("Email: " + (invoice_data.get('email') or 'N/A'))
        text.append("Adresse: " + (invoice_data.get('address') or 'N/A'))
        text.append("\nArticles:")
        
        if invoice_data.get('items'):
            for item in invoice_data['items']:
                text.append(f"  {item.get('name')} - {item.get('quantity')} x {item.get('unit_price'):.2f}€ = {item.get('total_price'):.2f}€")
        else:
            text.append("  Aucun article trouvé")
        
        text.append("\nTotal: " + (f"{invoice_data.get('total'):.2f}€" if invoice_data.get('total') else 'N/A'))
        
        return "\n".join(text)
    
    elif format_type == 'html':
        html = []
        html.append("<div class='invoice'>")
        html.append(f"<p><strong>Numéro de facture:</strong> {invoice_data.get('invoice_number') or 'N/A'}</p>")
        html.append(f"<p><strong>Date d'émission:</strong> {invoice_data.get('issue_date') or 'N/A'}</p>")
        html.append(f"<p><strong>Client:</strong> {invoice_data.get('client') or 'N/A'}</p>")
        html.append(f"<p><strong>Email:</strong> {invoice_data.get('email') or 'N/A'}</p>")
        html.append(f"<p><strong>Adresse:</strong> {invoice_data.get('address') or 'N/A'}</p>")
        
        html.append("<h3>Articles:</h3>")
        html.append("<table border='1'>")
        html.append("<tr><th>Article</th><th>Quantité</th><th>Prix unitaire</th><th>Total</th></tr>")
        
        if invoice_data.get('items'):
            for item in invoice_data['items']:
                html.append("<tr>")
                html.append(f"<td>{item.get('name')}</td>")
                html.append(f"<td>{item.get('quantity')}</td>")
                html.append(f"<td>{item.get('unit_price'):.2f}€</td>")
                html.append(f"<td>{item.get('total_price'):.2f}€</td>")
                html.append("</tr>")
        else:
            html.append("<tr><td colspan='4'>Aucun article trouvé</td></tr>")
        
        html.append("</table>")
        html.append(f"<p><strong>Total:</strong> {invoice_data.get('total'):.2f}€ if invoice_data.get('total') else 'N/A'</p>")
        html.append("</div>")
        
        return "\n".join(html)
    
    else:
        raise ValueError(f"Type de format inconnu: {format_type}")

def process_invoice_image(image_path):
    """
    Traite une image de facture et extrait toutes les données.
    
    Args:
        image_path: Chemin vers l'image de la facture
        
    Returns:
        Dictionnaire avec les données extraites de la facture
    """
    # Effectuer l'OCR sur l'image
    ocr_text = perform_ocr(image_path)
    if not ocr_text:
        logger.error("Échec de l'OCR sur l'image")
        return {}
    
    # Extraire les données de la facture
    invoice_data = extract_invoice_data(ocr_text, image_path)
    
    return invoice_data