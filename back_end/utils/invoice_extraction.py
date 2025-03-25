import re
import os
import pytesseract
from back_end.classe.preprocess_image import preprocessing_image

def extract_invoice_number_from_filename(image_path):
    """Extrait le numéro de facture à partir du nom du fichier."""
    filename = os.path.basename(image_path)
    file_invoice_number = None
    
    filename_match = re.search(r'FAC_(\d{4})_(\d{4})-?(\d{3})?', filename)
    if filename_match:
        year = filename_match.group(1)
        number = filename_match.group(2)
        file_invoice_number = f"FAC/{year}/{number}"
        print(f"📄 Numéro de facture extrait du nom de fichier: {file_invoice_number}")
    
    return file_invoice_number

def perform_ocr(image_path):
    """Prétraite l'image et effectue l'OCR."""
    processed_image = preprocessing_image(image_path)
    if processed_image is None:
        return None

    # Configuration Tesseract améliorée
    custom_config = r'--oem 1 --psm 4 -l eng'
    
    # Réaliser OCR sur l'image améliorée
    raw_text = pytesseract.image_to_string(processed_image, config=custom_config)
    
    # Affichage du texte brut extrait
    print("🔍 Texte extrait après amélioration :\n", raw_text)
    
    return raw_text

def clean_ocr_text(raw_text):
    """Nettoie le texte extrait par OCR."""
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

def extract_invoice_number_from_text(raw_text, file_invoice_number=None):
    """Extrait le numéro de facture du texte OCR."""
    invoice_number = file_invoice_number
    
    # Seulement si on n'a pas déjà extrait le numéro du nom de fichier ou pour vérification
    if not invoice_number:
        invoice_match = re.search(r'INVOICE\s*(?:FAC/)?(\d{4}(?:[,/]\d+)?)', raw_text, re.IGNORECASE)
        if invoice_match:
            invoice_number_text = invoice_match.group(1).replace(',', '/')
            invoice_number = f"FAC/{invoice_number_text}"
    
    # Version alternative plus stricte pour le format FAC/YYYY/XXXX
    invoice_match = re.search(r'(FAC/\d{4}/\d{4})', raw_text)
    if invoice_match:
        invoice_number = invoice_match.group(1).strip()
        
    return invoice_number

def extract_issue_date(raw_text):
    """Extrait la date d'émission de la facture."""
    issue_date = None
    
    date_match = re.search(r'(?:Issue|Date)[:\s]+(\d{4}[-/]\d{1,2}[-/]\d{1,2})', raw_text, re.IGNORECASE)
    if date_match:
        date_str = date_match.group(1)
        date_parts = re.split(r'[-/]', date_str)
        if len(date_parts) == 3:
            issue_date = f"{date_parts[0]}-{date_parts[1].zfill(2)}-{date_parts[2].zfill(2)}"
    
    return issue_date

def extract_email(raw_text):
    """Extrait l'adresse email du client."""
    email = None
    
    email_pattern = r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}'
    email_match = re.search(email_pattern, raw_text)
    if email_match:
        email_extrait = email_match.group(0).strip().lower()
        if email_extrait:  # Vérification supplémentaire
            email = email_extrait
        else:
            print("⚠️ Adresse email invalide détectée")
    
    return email

def extract_total(raw_text):
    """Extrait le montant total de la facture."""
    total = None
    
    total_match = re.search(r'TOTAL\s+([\d\.,]+)\s+(?:Euro|EUR|€)', raw_text, re.IGNORECASE)
    if total_match:
        total = float(total_match.group(1).replace(",", "."))
    
    return total

def extract_items(raw_text):
    """Extrait les articles de la facture."""
    items = []
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
                items.append({
                    "name": name.strip(),
                    "quantity": int(qty),
                    "unit_price": float(price.replace(",", ".")),
                    "total_price": int(qty) * float(price.replace(",", "."))
                })
            except ValueError:
                print(f"Erreur lors de l'extraction de l'article: {match.group()}")
    
    return items

def extract_client_name(raw_text):
    """Extrait le nom du client."""
    client = None
    
    client_match = re.search(r'Bill to\s*(.+?)(?=\s*Email|\s*Address|\n)', raw_text, re.IGNORECASE)
    if client_match:
        # Limiter la longueur du nom du client à 255 caractères pour éviter l'erreur de base de données
        client = client_match.group(1).strip()[:255]
    
    return client

def extract_address(raw_text):
    """Extrait l'adresse du client."""
    address = None
    
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
            # Limiter la longueur de l'adresse à 255 caractères
            address = address_text[:255]
    
    return address

def validate_total(items, total):
    """Valide le total par rapport aux éléments."""
    if not items or total is None:
        return True
        
    calculated_total = sum(item["total_price"] for item in items)
    if abs(calculated_total - total) > 0.01:
        print(f"⚠️ Incohérence dans le total: {total} vs {calculated_total} calculé")
        return False
    return True