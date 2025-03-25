import cv2
import numpy as np
from PIL import Image

def preprocessing_image(image_path, scale=4):
    # Redimensionner l'image
    image = cv2.imread(image_path)
    if image is None:
        return None
    height, width = image.shape[:2]
    new_size = (width * scale, height * scale)
    resized_image = cv2.resize(image, new_size, interpolation=cv2.INTER_CUBIC)
    
    # Appliquer un masque sur la photo
    x_start = int(width * 0.55)
    y_start = 0
    x_end = width
    y_end = int(height * 0.15)
    cv2.rectangle(resized_image, (x_start, y_start), (x_end, y_end), (255, 255, 255), -1)
    
    # Convertir en niveaux de gris
    gray_image = cv2.cvtColor(resized_image, cv2.COLOR_BGR2GRAY)
    
    # Appliquer le seuillage
    _, binary_image = cv2.threshold(gray_image, 240, 255, cv2.THRESH_BINARY)
    
    return binary_image