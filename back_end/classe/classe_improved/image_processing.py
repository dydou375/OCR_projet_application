"""
Image processing utilities for OCR invoice processing.
"""

import cv2
import numpy as np
import os
from PIL import Image
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_image(image_path):
    """
    Load an image from a file path.
    
    Args:
        image_path: Path to the image file
        
    Returns:
        Loaded image as a numpy array
    """
    try:
        image = cv2.imread(image_path)
        if image is None:
            # Try with PIL if OpenCV fails
            pil_image = Image.open(image_path)
            image = np.array(pil_image)
            # Convert RGB to BGR for OpenCV compatibility
            if len(image.shape) == 3 and image.shape[2] == 3:
                image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        return image
    except Exception as e:
        logger.error(f"Error loading image from {image_path}: {str(e)}")
        raise

def save_image(image, output_path):
    """
    Save an image to a file.
    
    Args:
        image: Image as a numpy array
        output_path: Path to save the image
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Save image
        cv2.imwrite(output_path, image)
        return True
    except Exception as e:
        logger.error(f"Error saving image to {output_path}: {str(e)}")
        return False

def resize_image(image, max_width=1000, max_height=1000):
    """
    Resize an image while maintaining aspect ratio.
    
    Args:
        image: Image as a numpy array
        max_width: Maximum width
        max_height: Maximum height
        
    Returns:
        Resized image as a numpy array
    """
    # Get current dimensions
    height, width = image.shape[:2]
    
    # Calculate scaling factor
    scale = min(max_width / width, max_height / height)
    
    # Only resize if the image is larger than the maximum dimensions
    if scale < 1:
        new_width = int(width * scale)
        new_height = int(height * scale)
        resized = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)
        return resized
    
    return image

def convert_to_grayscale(image):
    """
    Convert an image to grayscale.
    
    Args:
        image: Image as a numpy array
        
    Returns:
        Grayscale image as a numpy array
    """
    if len(image.shape) == 3:
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return image

def apply_threshold(image, method='adaptive'):
    """
    Apply thresholding to an image.
    
    Args:
        image: Grayscale image as a numpy array
        method: Thresholding method ('simple', 'adaptive', or 'otsu')
        
    Returns:
        Thresholded image as a numpy array
    """
    if method == 'simple':
        _, thresh = cv2.threshold(image, 127, 255, cv2.THRESH_BINARY)
    elif method == 'adaptive':
        thresh = cv2.adaptiveThreshold(
            image, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 11, 2
        )
    elif method == 'otsu':
        _, thresh = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    else:
        raise ValueError(f"Unknown thresholding method: {method}")
    
    return thresh

def denoise_image(image, method='gaussian'):
    """
    Apply denoising to an image.
    
    Args:
        image: Image as a numpy array
        method: Denoising method ('gaussian', 'median', or 'nlm')
        
    Returns:
        Denoised image as a numpy array
    """
    if method == 'gaussian':
        return cv2.GaussianBlur(image, (5, 5), 0)
    elif method == 'median':
        return cv2.medianBlur(image, 5)
    elif method == 'nlm':
        return cv2.fastNlMeansDenoising(image, None, 10, 7, 21)
    else:
        raise ValueError(f"Unknown denoising method: {method}")

def sharpen_image(image):
    """
    Apply sharpening to an image.
    
    Args:
        image: Image as a numpy array
        
    Returns:
        Sharpened image as a numpy array
    """
    kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
    return cv2.filter2D(image, -1, kernel)

def deskew_image(image):
    """
    Deskew an image to correct rotation.
    
    Args:
        image: Grayscale image as a numpy array
        
    Returns:
        Deskewed image as a numpy array
    """
    try:
        # Calculate skew angle
        coords = np.column_stack(np.where(image > 0))
        angle = cv2.minAreaRect(coords)[-1]
        
        # Adjust angle
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        
        # Rotate image
        (h, w) = image.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(
            image, M, (w, h), 
            flags=cv2.INTER_CUBIC, 
            borderMode=cv2.BORDER_REPLICATE
        )
        
        return rotated
    except Exception as e:
        logger.warning(f"Error deskewing image: {str(e)}")
        return image

def remove_borders(image):
    """
    Remove black borders from an image.
    
    Args:
        image: Image as a numpy array
        
    Returns:
        Image with borders removed as a numpy array
    """
    # Convert to grayscale if needed
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
    
    # Threshold
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    # Find contours
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        return image
    
    # Find largest contour
    largest_contour = max(contours, key=cv2.contourArea)
    
    # Get bounding rectangle
    x, y, w, h = cv2.boundingRect(largest_contour)
    
    # Crop image
    if len(image.shape) == 3:
        return image[y:y+h, x:x+w]
    else:
        return image[y:y+h, x:x+w]

def preprocess_image_for_ocr(image_path, output_path=None):
    """
    Preprocess an image for OCR.
    
    Args:
        image_path: Path to the input image
        output_path: Optional path to save the preprocessed image
        
    Returns:
        Preprocessed image as a numpy array
    """
    try:
        # Load image
        image = load_image(image_path)
        
        # Resize image
        image = resize_image(image)
        
        # Convert to grayscale
        gray = convert_to_grayscale(image)
        
        # Apply sharpening
        sharp = sharpen_image(gray)
        
        # Apply denoising
        denoised = denoise_image(sharp, method='nlm')
        
        # Apply thresholding
        thresh = apply_threshold(denoised, method='adaptive')
        
        # Deskew image
        deskewed = deskew_image(thresh)
        
        # Save preprocessed image if output path is provided
        if output_path:
            save_image(deskewed, output_path)
        
        return deskewed
    
    except Exception as e:
        logger.error(f"Error preprocessing image: {str(e)}")
        raise

def extract_regions_of_interest(image, regions):
    """
    Extract regions of interest from an image.
    
    Args:
        image: Image as a numpy array
        regions: List of (x, y, w, h) tuples defining regions
        
    Returns:
        List of extracted regions as numpy arrays
    """
    extracted = []
    for x, y, w, h in regions:
        roi = image[y:y+h, x:x+w]
        extracted.append(roi)
    return extracted

def detect_text_regions(image):
    """
    Detect regions containing text in an image.
    
    Args:
        image: Image as a numpy array
        
    Returns:
        List of (x, y, w, h) tuples defining text regions
    """
    # Convert to grayscale if needed
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
    
    # Apply thresholding
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    # Apply morphological operations to find text regions
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    dilated = cv2.dilate(thresh, kernel, iterations=3)
    
    # Find contours
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Filter contours by size
    regions = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        
        # Filter out very small regions
        if w < 20 or h < 20:
            continue
        
        regions.append((x, y, w, h))
    
    return regions
