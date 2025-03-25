import pytesseract
from preprocess_image import preprocessing_image
import re
from save_data_bdd import save_invoice_data_to_db_improved
import os

def extract_invoice_data_improved(image_path):
    # Extraire le nom du fichier pour obtenir le numéro de facture
    filename = os.path.basename(image_path)
    file_invoice_number = None
    
    # Essayer d'extraire le numéro de facture du nom de fichier
    filename_match = re.search(r'FAC_(\d{4})_(\d{4})-?(\d{3})?', filename)
    if filename_match:
        year = filename_match.group(1)
        number = filename_match.group(2)
        file_invoice_number = f"FAC/{year}/{number}"
        print(f"📄 Numéro de facture extrait du nom de fichier: {file_invoice_number}")
    
    processed_image = preprocessing_image(image_path)
    if processed_image is None:
        return None

    # Configuration Tesseract améliorée
    custom_config = r'--oem 3 --psm 4 -l eng'
    
    # Réaliser OCR sur l'image améliorée
    raw_text = pytesseract.image_to_string(processed_image, config=custom_config)
    
    # Affichage du texte brut extrait
    print("🔍 Texte extrait après amélioration :\n", raw_text)

    # Dictionnaire pour stocker les résultats
    invoice_data = {
        "invoice_number": file_invoice_number,  # Utiliser le numéro extrait du nom de fichier par défaut
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
    # Seulement si on n'a pas déjà extrait le numéro du nom de fichier ou pour vérification
    if not file_invoice_number:
        invoice_match = re.search(r'INVOICE\s*(?:FAC/)?(\d{4}(?:[,/]\d+)?)', raw_text, re.IGNORECASE)
        if invoice_match:
            invoice_number = invoice_match.group(1).replace(',', '/')
            invoice_data["invoice_number"] = f"FAC/{invoice_number}"
    
    date_match = re.search(r'(?:Issue|Date)[:\s]+(\d{4}[-/]\d{1,2}[-/]\d{1,2})', raw_text, re.IGNORECASE)
    if date_match:
        date_str = date_match.group(1)
        date_parts = re.split(r'[-/]', date_str)
        if len(date_parts) == 3:
            invoice_data["issue_date"] = f"{date_parts[0]}-{date_parts[1].zfill(2)}-{date_parts[2].zfill(2)}"
    
    email_pattern = r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}'
    email_match = re.search(email_pattern, raw_text)
    if email_match:
        email_extrait = email_match.group(0).strip().lower()
        if email_extrait:  # Vérification supplémentaire
            invoice_data["email"] = email_extrait
        else:
            print("⚠️ Adresse email invalide détectée")
    
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
        # Limiter la longueur du nom du client à 255 caractères pour éviter l'erreur de base de données
        invoice_data["client"] = client_match.group(1).strip()[:255]
    
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
            invoice_data["address"] = address_text[:255]
    
    # Version alternative plus stricte pour le format FAC/YYYY/XXXX
    invoice_match = re.search(r'(FAC/\d{4}/\d{4})', raw_text)
    if invoice_match:
        invoice_data["invoice_number"] = invoice_match.group(1).strip()

    # Validation du total par rapport aux éléments
    calculated_total = sum(item["total_price"] for item in invoice_data["items"])
    if invoice_data["total"] and abs(calculated_total - invoice_data["total"]) > 0.01:
        print(f"⚠️ Incohérence dans le total: {invoice_data['total']} vs {calculated_total} calculé")

    # Ajouter une gestion d'erreur lors de l'enregistrement
    try:
        save_invoice_data_to_db_improved(invoice_data)
        print("✅ Données de la facture extraites et enregistrées avec succès.")
    except Exception as e:
        print(f"❌ Erreur lors de l'enregistrement des données: {str(e)}")
        
    return invoice_data