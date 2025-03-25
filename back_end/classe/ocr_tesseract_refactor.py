import os
from save_data_bdd import save_invoice_data_to_db_improved
from back_end.utils.invoice_extraction import (
    extract_invoice_number_from_filename,
    perform_ocr,
    clean_ocr_text,
    extract_invoice_number_from_text,
    extract_issue_date,
    extract_email,
    extract_total,
    extract_items,
    extract_client_name,
    extract_address,
    validate_total
)

def extract_invoice_data_improved(image_path):
    """
    Fonction principale pour extraire les données d'une facture à partir d'une image.
    Utilise des fonctions utilitaires modulaires pour chaque étape du processus.
    """
    # Extraire le numéro de facture du nom de fichier
    file_invoice_number = extract_invoice_number_from_filename(image_path)
    
    # Effectuer l'OCR sur l'image
    raw_text = perform_ocr(image_path)
    if raw_text is None:
        return None
    
    # Nettoyer le texte extrait
    cleaned_text = clean_ocr_text(raw_text)
    
    # Initialiser le dictionnaire pour stocker les résultats
    invoice_data = {
        "invoice_number": file_invoice_number,  # Utiliser le numéro extrait du nom de fichier par défaut
        "issue_date": None,
        "client": None,
        "email": None,
        "address": None,
        "items": [],
        "total": None
    }
    
    # Extraire les différentes informations
    invoice_data["invoice_number"] = extract_invoice_number_from_text(cleaned_text, file_invoice_number)
    invoice_data["issue_date"] = extract_issue_date(cleaned_text)
    invoice_data["email"] = extract_email(cleaned_text)
    invoice_data["total"] = extract_total(cleaned_text)
    invoice_data["items"] = extract_items(cleaned_text)
    invoice_data["client"] = extract_client_name(cleaned_text)
    invoice_data["address"] = extract_address(cleaned_text)
    
    # Valider le total par rapport aux éléments
    validate_total(invoice_data["items"], invoice_data["total"])
    
    # Ajouter une gestion d'erreur lors de l'enregistrement
    try:
        save_invoice_data_to_db_improved(invoice_data)
        print("✅ Données de la facture extraites et enregistrées avec succès.")
    except Exception as e:
        print(f"❌ Erreur lors de l'enregistrement des données: {str(e)}")
    
    return invoice_data