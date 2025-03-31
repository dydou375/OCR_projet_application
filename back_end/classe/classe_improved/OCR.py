import cv2
import pytesseract
import numpy as np
import os
import re
import time
from PIL import Image
from pyzbar.pyzbar import decode
from dotenv import load_dotenv
import json
import requests
from io import BytesIO
import base64

# Load environment variables
load_dotenv()

# Configure Tesseract path if needed
if os.getenv("TESSERACT_PATH"):
    pytesseract.pytesseract.tesseract_cmd = os.getenv("TESSERACT_PATH")

# OCR Service configuration
OCR_SERVICES = {
    "tesseract": {
        "name": "Tesseract OCR",
        "enabled": True,
        "config": {
            "psm": 4,  # Page segmentation mode
            "oem": 3,  # OCR Engine mode
            "lang": "eng"  # Language
        }
    },
    "azure": {
        "name": "Azure Computer Vision",
        "enabled": os.getenv("VISION_KEY") is not None,
        "endpoint": os.getenv("VISION_ENDPOINT"),
        "key": os.getenv("VISION_KEY")
    },
    "google": {
        "name": "Google Cloud Vision",
        "enabled": os.getenv("GOOGLE_VISION_KEY") is not None,
        "key": os.getenv("GOOGLE_VISION_KEY")
    }
}

def process_image(image_path, scale=2):
    """
    Preprocess an image for OCR to improve text recognition.
    
    Args:
        image_path: Path to the image file
        
    Returns:
        Processed image as a numpy array
    """
    # Load the image
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

def extract_text_tesseract(image, config=None):
    """
    Extract text from an image using Tesseract OCR.
    
    Args:
        image: Processed image as a numpy array
        config: Optional Tesseract configuration
        
    Returns:
        Extracted text as a string
    """
    if config is None:
        config = OCR_SERVICES["tesseract"]["config"]
    
    # Build Tesseract configuration string
    config_str = f"--psm {config['psm']} --oem {config['oem']} -l {config['lang']}"
    
    # Extract text
    start_time = time.time()
    text = pytesseract.image_to_string(image, config=config_str)
    processing_time = time.time() - start_time
    
    return text, processing_time

def extract_text_azure(image_path):
    """
    Extract text from an image using Azure Computer Vision.
    
    Args:
        image_path: Path to the image file
        
    Returns:
        Extracted text as a string
    """
    if not OCR_SERVICES["azure"]["enabled"]:
        raise ValueError("Azure Computer Vision is not configured")
    
    endpoint = OCR_SERVICES["azure"]["endpoint"]
    key = OCR_SERVICES["azure"]["key"]
    
    # API endpoint for OCR
    ocr_url = f"{endpoint}/vision/v3.2/ocr"
    
    # Read image and encode as base64
    with open(image_path, "rb") as image_file:
        image_data = image_file.read()
    
    # Set request headers and parameters
    headers = {
        'Ocp-Apim-Subscription-Key': key,
        'Content-Type': 'application/octet-stream'
    }
    params = {
        'language': 'en',
        'detectOrientation': 'true'
    }
    
    # Make request to Azure
    start_time = time.time()
    response = requests.post(ocr_url, headers=headers, params=params, data=image_data)
    response.raise_for_status()
    
    # Process response
    result = response.json()
    processing_time = time.time() - start_time
    
    # Extract text from response
    text = ""
    if 'regions' in result:
        for region in result['regions']:
            for line in region['lines']:
                for word in line['words']:
                    text += word['text'] + " "
                text += "\n"
    
    return text, processing_time

def extract_text_google(image_path):
    """
    Extract text from an image using Google Cloud Vision.
    
    Args:
        image_path: Path to the image file
        
    Returns:
        Extracted text as a string
    """
    if not OCR_SERVICES["google"]["enabled"]:
        raise ValueError("Google Cloud Vision is not configured")
    
    key = OCR_SERVICES["google"]["key"]
    
    # API endpoint for OCR
    vision_url = "https://vision.googleapis.com/v1/images:annotate"
    
    # Read image and encode as base64
    with open(image_path, "rb") as image_file:
        encoded_image = base64.b64encode(image_file.read()).decode('utf-8')
    
    # Prepare request payload
    request_data = {
        "requests": [
            {
                "image": {
                    "content": encoded_image
                },
                "features": [
                    {
                        "type": "TEXT_DETECTION"
                    }
                ]
            }
        ]
    }
    
    # Set request headers
    headers = {
        'Content-Type': 'application/json',
        'X-Goog-Api-Key': key
    }
    
    # Make request to Google
    start_time = time.time()
    response = requests.post(vision_url, headers=headers, json=request_data)
    response.raise_for_status()
    
    # Process response
    result = response.json()
    processing_time = time.time() - start_time
    
    # Extract text from response
    text = ""
    if 'responses' in result and result['responses'] and 'textAnnotations' in result['responses'][0]:
        text = result['responses'][0]['textAnnotations'][0]['description']
    
    return text, processing_time

def extract_text_multi_service(image_path, processed_image):
    """
    Extract text using multiple OCR services and combine results.
    
    Args:
        image_path: Path to the image file
        processed_image: Processed image as a numpy array
        
    Returns:
        Best extracted text and service information
    """
    results = []
    
    # Try Tesseract
    if OCR_SERVICES["tesseract"]["enabled"]:
        try:
            text, processing_time = extract_text_tesseract(processed_image)
            results.append({
                "service": "tesseract",
                "text": text,
                "processing_time": processing_time,
                "confidence": estimate_confidence(text)
            })
        except Exception as e:
            print(f"Error with Tesseract OCR: {str(e)}")
    
    # Try Azure if configured
    if OCR_SERVICES["azure"]["enabled"]:
        try:
            text, processing_time = extract_text_azure(image_path)
            results.append({
                "service": "azure",
                "text": text,
                "processing_time": processing_time,
                "confidence": estimate_confidence(text)
            })
        except Exception as e:
            print(f"Error with Azure Computer Vision: {str(e)}")
    
    # Try Google if configured
    if OCR_SERVICES["google"]["enabled"]:
        try:
            text, processing_time = extract_text_google(image_path)
            results.append({
                "service": "google",
                "text": text,
                "processing_time": processing_time,
                "confidence": estimate_confidence(text)
            })
        except Exception as e:
            print(f"Error with Google Cloud Vision: {str(e)}")
    
    if not results:
        raise ValueError("No OCR service was able to process the image")
    
    # Select the best result based on confidence
    best_result = max(results, key=lambda x: x["confidence"])
    
    return best_result["text"], {
        "service": best_result["service"],
        "processing_time": best_result["processing_time"],
        "confidence": best_result["confidence"]
    }

def estimate_confidence(text):
    """
    Estimate the confidence of OCR results based on heuristics.
    
    Args:
        text: Extracted text
        
    Returns:
        Confidence score between 0 and 1
    """
    if not text:
        return 0.0
    
    # Check for common invoice keywords
    keywords = ["invoice", "bill", "date", "total", "customer", "payment", "amount", "tax", "item", "quantity", "price"]
    keyword_count = sum(1 for keyword in keywords if keyword.lower() in text.lower())
    keyword_score = min(1.0, keyword_count / len(keywords))
    
    # Check for expected patterns
    patterns = [
        r'\d{4}-\d{2}-\d{2}',  # Date format YYYY-MM-DD
        r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',  # Email
        r'\d+\s*x\s*\d+',  # Quantity x Price pattern
        r'total\s*:?\s*\d+',  # Total amount pattern
    ]
    pattern_count = sum(1 for pattern in patterns if re.search(pattern, text.lower()))
    pattern_score = min(1.0, pattern_count / len(patterns))
    
    # Check for text length and density
    length_score = min(1.0, len(text) / 500)  # Assume 500 chars is a good length
    
    # Calculate overall confidence
    confidence = (keyword_score * 0.4) + (pattern_score * 0.4) + (length_score * 0.2)
    
    return confidence

def extract_qr_data(image_path):
    """
    Extract data from QR codes in an image.
    
    Args:
        image_path: Path to the image file
        
    Returns:
        List of decoded QR code data
    """
    try:
        img = Image.open(image_path)
        decoded_result = decode(img)
        
        results = []
        for item in decoded_result:
            results.append(item.data.decode("utf-8"))
        
        return results
    except Exception as e:
        print(f"Error extracting QR code data: {str(e)}")
        return []

def extract_invoice_data(processed_image, image_path=None, ocr_service="auto"):
    """
    Extract structured invoice data from a processed image.
    
    Args:
        processed_image: Processed image as a numpy array
        image_path: Optional path to the original image file
        ocr_service: OCR service to use ("auto", "tesseract", "azure", "google")
        
    Returns:
        Dictionary with extracted invoice data
    """
    # Initialize result dictionary
    invoice_data = {
        "invoice_number": None,
        "issue_date": None,
        "client": None,
        "email": None,
        "address": None,
        "items": [],
        "total": None
    }
    
    # Extract text using specified OCR service
    start_time = time.time()
    
    if ocr_service == "auto" and image_path:
        raw_text, service_info = extract_text_multi_service(image_path, processed_image)
    elif ocr_service == "tesseract" or (ocr_service == "auto" and not image_path):
        raw_text, processing_time = extract_text_tesseract(processed_image)
        service_info = {
            "service": "tesseract",
            "processing_time": processing_time,
            "confidence": estimate_confidence(raw_text)
        }
    elif ocr_service == "azure" and image_path:
        raw_text, processing_time = extract_text_azure(image_path)
        service_info = {
            "service": "azure",
            "processing_time": processing_time,
            "confidence": estimate_confidence(raw_text)
        }
    elif ocr_service == "google" and image_path:
        raw_text, processing_time = extract_text_google(image_path)
        service_info = {
            "service": "google",
            "processing_time": processing_time,
            "confidence": estimate_confidence(raw_text)
        }
    else:
        raise ValueError(f"Invalid OCR service: {ocr_service}")
    
    # Store OCR service information
    invoice_data["ocr_service"] = service_info
    
    # Correct common OCR errors
    raw_text = raw_text.replace("Furo", "Euro").replace("Buro", "Euro")
    
    # Extract invoice number
    invoice_number_match = re.search(r'INVOICE\s+([\w/]+)', raw_text)
    if invoice_number_match:
        invoice_data["invoice_number"] = invoice_number_match.group(1)
    
    # Extract date
    date_match = re.search(r'Issue date (\d{4}-\d{2}-\d{2})', raw_text)
    if date_match:
        invoice_data["issue_date"] = date_match.group(1)
    
    # Extract email
    email_match = re.search(r'Email\s+([\w\.\-]+@[\w\.\-]+)', raw_text)
    if email_match:
        invoice_data["email"] = email_match.group(1)
    
    # Extract total
    total_match = re.search(r'TOTAL\s+([\d\.,]+)\s+Euro', raw_text)
    if total_match:
        invoice_data["total"] = float(total_match.group(1).replace(",", "."))
    
    # Extract items (quantity x price)
    item_pattern = re.findall(r'(.+?)\s+(\d+)\s*x\s*([\d\.,]+)\s*Euro', raw_text)
    for item in item_pattern:
        name, qty, price = item
        invoice_data["items"].append({
            "name": name.strip(),
            "quantity": int(qty),
            "unit_price": float(price.replace(",", ".")),
            "total_price": int(qty) * float(price.replace(",", "."))
        })
    
    # Extract client name
    client_match = re.search(r'Bill to\s*(.+)', raw_text)
    if client_match:
        invoice_data["client"] = client_match.group(1).strip()
    
    # Extract address
    address_match = re.search(r'Address\s*(.+?)(?=\n\n|$)', raw_text, re.DOTALL)
    if address_match:
        invoice_data["address"] = address_match.group(1).strip().replace("\n", " ")
    
    # Extract QR code data if image_path is provided
    if image_path:
        qr_data = extract_qr_data(image_path)
        if qr_data:
            invoice_data["qr_data"] = qr_data
    
    # Calculate processing time
    invoice_data["processing_time"] = time.time() - start_time
    
    return invoice_data

def get_available_ocr_services():
    """
    Get a list of available OCR services.
    
    Returns:
        List of dictionaries with service information
    """
    available_services = []
    
    for service_id, service_info in OCR_SERVICES.items():
        if service_info["enabled"]:
            available_services.append({
                "id": service_id,
                "name": service_info["name"]
            })
    
    return available_services
