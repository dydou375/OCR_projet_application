import os
from azure.ai.vision.imageanalysis import ImageAnalysisClient
from azure.ai.vision.imageanalysis.models import VisualFeatures
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv
import json
# Set the values of your computer vision endpoint and computer vision key
# as environment variables:

load_dotenv()

try:
    endpoint = os.getenv("VISION_ENDPOINT")
    key = os.getenv("VISION_KEY")
except KeyError:
    print("Missing environment variable 'VISION_ENDPOINT' or 'VISION_KEY'")
    print("Set them before running this sample.")
    exit()

# Create an Image Analysis client
client = ImageAnalysisClient(
    endpoint=endpoint,
    credential=AzureKeyCredential(key)
)       
        
def ocr_azure(image_path):
    with open(image_path, "rb") as f:
        image_data = f.read()
        
    result = client.analyze(
        image_data=image_data,
        visual_features=[VisualFeatures.CAPTION, VisualFeatures.READ],
        gender_neutral_caption=True,  # Optional (default is False)
    )
    return result

def extraire_et_enregistrer_donnees_facture_ameliore(result):
    """Extrait et enregistre les données améliorées d'une facture via Azure Vision."""
    if result.read is None:
        print("❌ Aucun texte détecté dans l'image.")
        return None

    # Dictionnaire pour stocker les résultats
    donnees_facture = {
        "numero_facture": None,
        "date_emission": None,
        "client": None,
        "email": None,
        "adresse": None,
        "articles": [],
        "total": None
    }
    
    # Extraction du texte brut et des bounding boxes à partir du résultat Azure
    lignes = []
    bounding_boxes = []
    
    for block in result.read.blocks:
        for line in block.lines:
            lignes.append(line.text)
            # Ajout d'une vérification des attributs disponibles
            if hasattr(line, 'bounding_polygon'):
                polygon = line.bounding_polygon
            elif hasattr(line, 'polygon'):
                polygon = line.polygon
            elif hasattr(line, 'bounding_box'):
                polygon = line.bounding_box
            else:
                # Fallback si aucun attribut n'est trouvé
                print(f"Avertissement: Impossible de trouver les coordonnées pour: {line.text}")
                polygon = None
                
            if polygon:
                bounding_boxes.append({
                    "text": line.text,
                    "x": polygon[0].x,
                    "y": polygon[0].y,
                    "width": polygon[1].x - polygon[0].x,
                    "height": polygon[2].y - polygon[0].y
                })
            else:
                bounding_boxes.append({
                    "text": line.text,
                    "x": 0, "y": 0, "width": 0, "height": 0
                })
    
    raw_text = " ".join(lignes)
    
    # Affichage du texte brut extrait
    print("🔍 Texte extrait avec Azure Vision :\n", raw_text)
    
    # Nettoyage du texte brut
    # Normalisation des espaces et retours à la ligne
    raw_text = " ".join(raw_text.split())
    
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
    
    # Extraction des informations clés avec regex améliorés
    import re
    
    invoice_match = re.search(r'INVOICE\s*[:#]?\s*([\w\/-]+)', raw_text, re.IGNORECASE)
    if invoice_match:
        donnees_facture["numero_facture"] = invoice_match.group(1).strip()
    
    date_match = re.search(r'(?:Issue|Date)[:\s]+(\d{4}[-/]\d{1,2}[-/]\d{1,2})', raw_text, re.IGNORECASE)
    if date_match:
        date_str = date_match.group(1)
        date_parts = re.split(r'[-/]', date_str)
        if len(date_parts) == 3:
            donnees_facture["date_emission"] = f"{date_parts[0]}-{date_parts[1].zfill(2)}-{date_parts[2].zfill(2)}"
    
    email_match = re.search(r'Email[:\s]+\s*([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', raw_text)
    if email_match:
        donnees_facture["email"] = email_match.group(1).strip().lower()
    
    total_match = re.search(r'TOTAL\s+([\d\.,]+)\s+(?:Euro|EUR|€)', raw_text, re.IGNORECASE)
    if total_match:
        donnees_facture["total"] = float(total_match.group(1).replace(",", "."))
    
    # Identification de l'adresse en utilisant les bounding boxes
    address_label_index = -1
    for i, box in enumerate(bounding_boxes):
        if re.search(r'Address[:\s]*', box["text"], re.IGNORECASE):
            address_label_index = i
            break
    
    if address_label_index >= 0:
        # Trouver les lignes qui suivent "Address" et qui sont alignées verticalement
        address_y = bounding_boxes[address_label_index]["y"]
        address_x = bounding_boxes[address_label_index]["x"]
        address_height = bounding_boxes[address_label_index]["height"]
        
        address_lines = []
        address_line_indices = []
        
        # Récupérer la ligne qui contient le mot "Address" (peut contenir déjà une partie de l'adresse)
        label_line = bounding_boxes[address_label_index]["text"]
        address_content = re.sub(r'Address[:\s]*', '', label_line, flags=re.IGNORECASE).strip()
        if address_content:
            address_lines.append(address_content)
        
        # Chercher les lignes suivantes qui font probablement partie de l'adresse
        # Critères: 
        # 1. Position Y > position Y de "Address" (en-dessous)
        # 2. Les lignes qui sont relativement proches verticalement
        # 3. Arrêt avant de trouver un motif d'article (qty x price)
        
        for i, box in enumerate(bounding_boxes):
            if i == address_label_index:
                continue
                
            # Vérifier que la ligne est sous le label "Address"
            if box["y"] > address_y:
                # Vérifier que c'est relativement aligné horizontalement ou en-dessous
                # et que ce n'est pas trop loin verticalement (3-4 fois la hauteur de la ligne "Address")
                if (abs(box["x"] - address_x) < 100 or box["x"] > address_x) and \
                   (box["y"] - address_y) < 4 * address_height:
                    
                    # Vérifier que ce n'est pas un article (motif: quantité x prix)
                    if not re.search(r'(\d+)\s*[xX]\s*([\d\.,]+)\s*(?:Euro|EUR|€)', box["text"]):
                        address_lines.append(box["text"])
                        address_line_indices.append(i)
                    else:
                        # Si c'est un article, on arrête de chercher
                        break
        
        # Si on a trouvé des lignes d'adresse
        if address_lines:
            donnees_facture["adresse"] = " ".join(address_lines)
    
    # Extraction des articles en utilisant les bounding boxes
    product_pattern = r'([A-Za-z][A-Za-z\s\.\-\_\&]+?)\.?\s+(\d+)\s*[x×]\s*([\d\.,]+)\s*(?:Euro|EUR|€)'
    seen_items = set()
    
    for box in bounding_boxes:
        match = re.search(product_pattern, box["text"])
        if match:
            name, qty, price = match.groups()
            item_key = f"{name.strip()}_{qty}_{price}"
            
            if item_key not in seen_items:
                seen_items.add(item_key)
                try:
                    donnees_facture["articles"].append({
                        "nom": name.strip(),
                        "quantite": int(qty),
                        "prix_unitaire": float(price.replace(",", ".")),
                        "prix_total": int(qty) * float(price.replace(",", "."))
                    })
                except ValueError:
                    print(f"Erreur lors de l'extraction de l'article: {match.group()}")
    
    # Vérification de la cohérence des données avant enregistrement
    if not donnees_facture["numero_facture"]:
        print("⚠️ Attention: Numéro de facture non détecté!")
    
    # Validation du total par rapport aux éléments
    if donnees_facture["articles"]:
        calculated_total = sum(item["prix_total"] for item in donnees_facture["articles"])
        if donnees_facture["total"] and abs(calculated_total - donnees_facture["total"]) > 0.01:
            print(f"⚠️ Incohérence dans le total: {donnees_facture['total']} vs {calculated_total} calculé")

    # Fonction pour enregistrer dans la base de données (à implémenter)
    # save_invoice_data_to_db_improved(donnees_facture)
    
    # Affichage des informations structurées
    print(f"Numéro de facture: {donnees_facture['numero_facture']}")
    print(f"Date: {donnees_facture['date_emission']}")
    print(f"Client: {donnees_facture['client']}")
    print(f"Email: {donnees_facture['email']}")
    print(f"Adresse: {donnees_facture['adresse']}")
    print("Articles:")
    for produit in donnees_facture["articles"]:
        print(f"  - {produit['nom']} (Qté: {produit['quantite']}) : {produit['prix_unitaire']} Euro")
    print(f"Total: {donnees_facture['total']}")
    
    print("✅ Données de la facture extraites avec succès.")
    return donnees_facture

if __name__ == "__main__":
    def dossier_facture():
        annees = ["2018"]
        for annee in annees:
            for fichier in os.listdir(fr"c:\Users\dd758\Formation_IA_Greta\OCR_Projet\OCR\data\facture_{annee}"):
                if fichier.endswith(".png"):
                    image_path = os.path.join(fr"c:\Users\dd758\Formation_IA_Greta\OCR_Projet\OCR\data\facture_{annee}", fichier)
                    print(f"Facture N°{fichier}")
                    result = ocr_azure(image_path)
                    extraire_et_enregistrer_donnees_facture_ameliore(result)
                    print("--------------------------------")

    def fichier_facture():
        image_path = r"c:\Users\dd758\Formation_IA_Greta\OCR_Projet\OCR\data\facture_2019\FAC_2019_0139-390.png"
        result = ocr_azure(image_path)
        extraire_et_enregistrer_donnees_facture_ameliore(result)

    fichier_facture()
