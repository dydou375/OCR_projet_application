import os
from extract_qr_code import extract_data_qrcode
from ocr_tesseract import extract_invoice_data_improved
from save_data_bdd import create_tables
import time

if __name__ == "__main__":
    # Création des tables
    create_tables()
    # Extraction des données de la facture
    def test1_fichier_db():
        image_path = fr"C:\Users\dd758\Formation_IA_Greta\OCR_Projet\OCR\data\facture_2019\FAC_2019_0004-104.png"
        extract_invoice_data_improved(image_path)

    def test_allfichier_db():
        annee = [2018]
        for annee in annee:
            dossier_factures = fr"c:\Users\dd758\Formation_IA_Greta\OCR_Projet\OCR\data\facture_{annee}"
            print(f"Traitement des factures de l'année {annee}...")
            for fichier in os.listdir(dossier_factures):
                if fichier.endswith('.png'):
                    image_path = os.path.join(dossier_factures, fichier)
                    print(f"\nTraitement de {fichier}...")
                    try:
                        extract_invoice_data_improved(image_path)
                    except Exception as e:
                        print(f"❌ Erreur lors du traitement de {fichier}: {e}")
                        # Ajoutez ici un rollback si nécessaire
                        # connection.rollback()  # Décommentez cette ligne après avoir ajouté la connexion
                        continue
            print(f"✅ Traitement terminé pour l'année {annee}")
    # Extraction des données de la facture
    def test_allfichier_db_qr():
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
                        # Ajoutez ici un rollback si nécessaire
                        # connection.rollback()  # Décommentez cette ligne après avoir ajouté la connexion
                        continue
            print(f"✅ Traitement terminé pour l'année {annee}")
    
    test1_fichier_db()





