from base64 import decode
from tkinter import Image
from PIL import Image
from pyzbar.pyzbar import decode
from save_data_bdd import update_customer_from_qr


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