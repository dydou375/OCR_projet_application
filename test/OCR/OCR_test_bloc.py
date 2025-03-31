import os
import cv2
import csv
import pandas as pd
import pytesseract


def test_bloc_1fichier():
    image_path = fr"c:\Users\dd758\Formation_IA_Greta\OCR_Projet\OCR\data\facture_2018\FAC_2018_0001-654.png"
    image = cv2.imread(image_path)
    if image is None:
        print(f"Erreur : Impossible de charger l'image à partir de {image_path}")
    else:
        # Convertir en niveaux de gris
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Appliquer un seuil
        _, thresh_2 = cv2.threshold(gray, 155, 255, cv2.THRESH_BINARY_INV)

        # Dilater l'image
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (20, 30))
        dilated = cv2.dilate(thresh_2, kernel, iterations=1)
        #trouver les contours
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            #trouver le premier contour
            x, y, w, h = cv2.boundingRect(contour)
            #extraire le segment
            segment = image[y:y+h, x:x+w]
            # Appliquer tesseract avec des paramètres ajustés
            custom_config = r'--psm 6'  # Utiliser le mode de page 6 pour une meilleure extraction
            text = pytesseract.image_to_string(segment, config=custom_config)
            print(text)

def test_bloc_allfichier():
    annee = [2018, 2019, 2020, 2021, 2022, 2023, 2024]
    for annees in annee:
        dossier = fr"c:\Users\dd758\Formation_IA_Greta\OCR_Projet\OCR\data\facture_{annees}"
        for fichier in os.listdir(dossier):
            image_path = os.path.join(dossier, fichier)
            image = cv2.imread(image_path)
            # Vérifier si l'image est chargée correctement
            if image is None:
                print(f"Erreur : Impossible de charger l'image à partir de {image_path}")
            else:
                # Convertir en niveaux de gris
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

                # Appliquer un seuillage adaptatif
                thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                    cv2.THRESH_BINARY_INV, 11, 2)
                #appliquer un seuil
                _, thresh_2 = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)

                # Dilater l'image
                kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (20, 30))
                dilated = cv2.dilate(thresh_2, kernel, iterations=1)
                contours_image, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                #compter le nombre de blocs
                bloc_ref = len(contours_image)
                
                # Définir le chemin du fichier CSV
                csv_path = fr"c:\Users\dd758\Formation_IA_Greta\OCR_Projet\OCR\resultats\resultats_blocs.csv"

                # Vérifier si le fichier CSV existe déjà
                file_exists = os.path.isfile(csv_path)

                # Ouvrir le fichier CSV en mode ajout
                with open(csv_path, mode='a', newline='') as file:
                    writer = csv.writer(file)
                    # Écrire l'en-tête si le fichier est nouveau
                    if not file_exists:
                        writer.writerow(["Date", "Nom du fichier", "Nombre de blocs"])
                    # Écrire les résultats dans le fichier CSV
                    writer.writerow([annees, fichier, bloc_ref])
    return bloc_ref

def tesseract_bloc():
    annee = [2018, 2019, 2020, 2021, 2022, 2023, 2024]
    for annees in annee:
        dossier = fr"c:\Users\dd758\Formation_IA_Greta\OCR_Projet\OCR\data\facture_{annees}"
        for fichier in os.listdir(dossier):
            image_path = os.path.join(dossier, fichier)
            image = cv2.imread(image_path)
            # Vérifier si l'image est chargée correctement
            if image is None:
                print(f"Erreur : Impossible de charger l'image à partir de {image_path}")
            else:
                # Convertir en niveaux de gris
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

                # Appliquer un seuillage adaptatif
                thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                    cv2.THRESH_BINARY_INV, 11, 2)
                #appliquer un seuil
                _, thresh_2 = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)

                # Dilater l'image
                kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (20, 30))
                dilated = cv2.dilate(thresh_2, kernel, iterations=1)
                contours_image, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                #appliquer tesseract
                text = pytesseract.image_to_string(image)                
                print(text)
    return text

if __name__ == "__main__":
    test_bloc_1fichier()
