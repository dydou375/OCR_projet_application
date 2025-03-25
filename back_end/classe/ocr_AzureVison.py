import os
from azure.ai.vision.imageanalysis import ImageAnalysisClient
from azure.ai.vision.imageanalysis.models import VisualFeatures
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv
import json
from PIL import Image
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

image_path = r"c:\Users\dd758\Formation_IA_Greta\OCR_Projet\OCR\data\facture_2019\FAC_2019_0139-390.png"
image_path2 = r"c:\Users\dd758\Formation_IA_Greta\OCR_Projet\OCR\data\facture_2023\FAC_2023_0496-533.png"
# Ouvrir le fichier en mode binaire
with open(image_path, "rb") as f:
    image_data = f.read()
    
with open(image_path2, "rb") as f:
    image_data2 = f.read()

# Utiliser la méthode correcte pour analyser l'image
result = client.analyze(
    image_data=image_data,
    visual_features=[VisualFeatures.CAPTION, VisualFeatures.READ],
    gender_neutral_caption=True,  # Optional (default is False)
)

result2 = client.analyze(
    image_data=image_data2,
    visual_features=[VisualFeatures.CAPTION, VisualFeatures.READ],
    gender_neutral_caption=True,  # Optional (default is False)
)

print("Image analysis results:")
# Print caption results to the console
print(" Caption:")
if result.caption is not None:
    print(f"   '{result.caption.text}', Confidence {result.caption.confidence:.4f}")

# Print text (OCR) analysis results to the console
print(" Read:")
if result.read is not None:
    for line in result.read.blocks[0].lines:
        print(f"   Line: '{line.text}', Bounding box {line.bounding_polygon}")

print(" Image analysis results 2:")
# Print caption results to the console
print(" Caption:")
if result2.caption is not None:
    print(f"   '{result2.caption.text}', Confidence {result2.caption.confidence:.4f}")
# Print text (OCR) analysis results to the console
print(" Read:")
if result2.read is not None:
    for line in result2.read.blocks[0].lines:
        print(f"   Line: '{line.text}', Bounding box {line.bounding_polygon}")  