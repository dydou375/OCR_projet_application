"""
Invoice data extraction utilities for OCR invoice processing.
"""

import re
import json
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def extract_invoice_number(text):
    """
    Extract invoice number from OCR text.
    
    Args:
        text: OCR extracted text
        
    Returns:
        Extracted invoice number or None if not found
    """
    # Common invoice number patterns
    patterns = [
        r'Invoice\s*#?\s*(\w+[-/]?\w+)',
        r'Invoice\s*Number\s*:?\s*(\w+[-/]?\w+)',
        r'Invoice\s*No\s*\.?\s*:?\s*(\w+[-/]?\w+)',
        r'Invoice\s*ID\s*:?\s*(\w+[-/]?\w+)',
        r'Facture\s*N°\s*:?\s*(\w+[-/]?\w+)',  # French
        r'Rechnung\s*Nr\s*\.?\s*:?\s*(\w+[-/]?\w+)',  # German
        r'Factura\s*N°\s*:?\s*(\w+[-/]?\w+)',  # Spanish
        r'Fattura\s*N°\s*:?\s*(\w+[-/]?\w+)',  # Italian
        r'#\s*(\w+[-/]?\w+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    return None

def extract_date(text):
    """
    Extract date from OCR text.
    
    Args:
        text: OCR extracted text
        
    Returns:
        Extracted date in YYYY-MM-DD format or None if not found
    """
    # Common date patterns
    patterns = [
        # ISO format: YYYY-MM-DD
        r'(?:Date|Issue Date|Invoice Date|Issued|Dated)\s*:?\s*(\d{4}-\d{1,2}-\d{1,2})',
        
        # US format: MM/DD/YYYY
        r'(?:Date|Issue Date|Invoice Date|Issued|Dated)\s*:?\s*(\d{1,2}/\d{1,2}/\d{4})',
        
        # European format: DD/MM/YYYY
        r'(?:Date|Issue Date|Invoice Date|Issued|Dated)\s*:?\s*(\d{1,2}/\d{1,2}/\d{4})',
        
        # European format: DD.MM.YYYY
        r'(?:Date|Issue Date|Invoice Date|Issued|Dated)\s*:?\s*(\d{1,2}\.\d{1,2}\.\d{4})',
        
        # Written format: Month DD, YYYY
        r'(?:Date|Issue Date|Invoice Date|Issued|Dated)\s*:?\s*([A-Za-z]+\s+\d{1,2},?\s+\d{4})'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            date_str = match.group(1).strip()
            
            try:
                # Try to parse the date
                if '-' in date_str:
                    # ISO format
                    year, month, day = map(int, date_str.split('-'))
                    return f"{year:04d}-{month:02d}-{day:02d}"
                elif '/' in date_str:
                    # US or European format
                    parts = date_str.split('/')
                    if len(parts[2]) == 4:  # Year is in position 2
                        if int(parts[0]) > 12:  # Day is in position 0
                            day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
                        else:  # Month is in position 0
                            month, day, year = int(parts[0]), int(parts[1]), int(parts[2])
                        return f"{year:04d}-{month:02d}-{day:02d}"
                elif '.' in date_str:
                    # European format with dots
                    day, month, year = map(int, date_str.split('.'))
                    return f"{year:04d}-{month:02d}-{day:02d}"
                else:
                    # Written format
                    date_obj = datetime.strptime(date_str, "%B %d, %Y")
                    return date_obj.strftime("%Y-%m-%d")
            except (ValueError, IndexError):
                # If parsing fails, continue to the next pattern
                continue
    
    return None

def extract_total_amount(text):
    """
    Extract total amount from OCR text.
    
    Args:
        text: OCR extracted text
        
    Returns:
        Extracted total amount as a float or None if not found
    """
    # Common total amount patterns
    patterns = [
        r'Total\s*:?\s*[$€£]?\s*([\d,]+\.\d{2})',
        r'Total\s*Amount\s*:?\s*[$€£]?\s*([\d,]+\.\d{2})',
        r'Amount\s*Due\s*:?\s*[$€£]?\s*([\d,]+\.\d{2})',
        r'Balance\s*Due\s*:?\s*[$€£]?\s*([\d,]+\.\d{2})',
        r'Grand\s*Total\s*:?\s*[$€£]?\s*([\d,]+\.\d{2})',
        r'Total\s*à\s*payer\s*:?\s*[$€£]?\s*([\d,]+\.\d{2})',  # French
        r'Gesamtbetrag\s*:?\s*[$€£]?\s*([\d,]+\.\d{2})',  # German
        r'Importe\s*Total\s*:?\s*[$€£]?\s*([\d,]+\.\d{2})',  # Spanish
        r'Importo\s*Totale\s*:?\s*[$€£]?\s*([\d,]+\.\d{2})'  # Italian
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            amount_str = match.group(1).strip()
            # Remove commas and convert to float
            amount = float(amount_str.replace(',', ''))
            return amount
    
    return None

def extract_client_info(text):
    """
    Extract client information from OCR text.
    
    Args:
        text: OCR extracted text
        
    Returns:
        Dictionary with client name, email, and address
    """
    client_info = {
        'name': None,
        'email': None,
        'address': None
    }
    
    # Extract client name
    name_patterns = [
        r'(?:Bill To|Sold To|Customer|Client|Billed To)\s*:?\s*([A-Za-z0-9\s&]+)',
        r'(?:Bill To|Sold To|Customer|Client|Billed To)\s*:?\s*\n\s*([A-Za-z0-9\s&]+)'
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            client_info['name'] = match.group(1).strip()
            break
    
    # Extract email
    email_pattern = r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'
    email_match = re.search(email_pattern, text)
    if email_match:
        client_info['email'] = email_match.group(0)
    
    # Extract address
    address_patterns = [
        r'(?:Address|Location|Billing Address)\s*:?\s*([A-Za-z0-9\s,.-]+)',
        r'(?:Bill To|Sold To|Customer|Client|Billed To)\s*:?\s*(?:[A-Za-z0-9\s&]+)\s*\n\s*([A-Za-z0-9\s,.-]+)'
    ]
    
    for pattern in address_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            client_info['address'] = match.group(1).strip()
            break
    
    return client_info

def extract_items(text):
    """
    Extract line items from OCR text.
    
    Args:
        text: OCR extracted text
        
    Returns:
        List of dictionaries with item details
    """
    items = []
    
    # Look for item patterns
    # Pattern: Description followed by quantity, unit price, and total
    item_pattern = r'([A-Za-z0-9\s]+)\s+(\d+)\s*x\s*[$€£]?\s*([\d,]+\.\d{2})'
    
    matches = re.finditer(item_pattern, text)
    for match in matches:
        description = match.group(1).strip()
        quantity = int(match.group(2))
        unit_price = float(match.group(3).replace(',', ''))
        total_price = quantity * unit_price
        
        items.append({
            'name': description,
            'quantity': quantity,
            'unit_price': unit_price,
            'total_price': total_price
        })
    
    return items

def extract_invoice_data(ocr_text):
    """
    Extract structured invoice data from OCR text.
    
    Args:
        ocr_text: OCR extracted text
        
    Returns:
        Dictionary with extracted invoice data
    """
    try:
        # Initialize invoice data
        invoice_data = {
            'invoice_number': None,
            'issue_date': None,
            'client': None,
            'email': None,
            'address': None,
            'items': [],
            'total': None
        }
        
        # Extract invoice number
        invoice_data['invoice_number'] = extract_invoice_number(ocr_text)
        
        # Extract date
        invoice_data['issue_date'] = extract_date(ocr_text)
        
        # Extract total amount
        invoice_data['total'] = extract_total_amount(ocr_text)
        
        # Extract client information
        client_info = extract_client_info(ocr_text)
        invoice_data['client'] = client_info['name']
        invoice_data['email'] = client_info['email']
        invoice_data['address'] = client_info['address']
        
        # Extract items
        invoice_data['items'] = extract_items(ocr_text)
        
        return invoice_data
    
    except Exception as e:
        logger.error(f"Error extracting invoice data: {str(e)}")
        return {}

def validate_invoice_data(invoice_data):
    """
    Validate extracted invoice data.
    
    Args:
        invoice_data: Dictionary with extracted invoice data
        
    Returns:
        Dictionary with validation results
    """
    validation = {
        'is_valid': True,
        'missing_fields': [],
        'warnings': []
    }
    
    # Check required fields
    required_fields = ['invoice_number', 'issue_date', 'total']
    for field in required_fields:
        if not invoice_data.get(field):
            validation['is_valid'] = False
            validation['missing_fields'].append(field)
    
    # Check if items are present
    if not invoice_data.get('items'):
        validation['warnings'].append('No line items found')
    
    # Check if total matches sum of items
    if invoice_data.get('items') and invoice_data.get('total'):
        items_total = sum(item.get('total_price', 0) for item in invoice_data['items'])
        if abs(items_total - invoice_data['total']) > 0.01:
            validation['warnings'].append('Total amount does not match sum of line items')
    
    return validation

def format_invoice_data(invoice_data, format_type='json'):
    """
    Format invoice data for output.
    
    Args:
        invoice_data: Dictionary with extracted invoice data
        format_type: Output format ('json', 'text', or 'html')
        
    Returns:
        Formatted invoice data
    """
    if format_type == 'json':
        return json.dumps(invoice_data, indent=2)
    
    elif format_type == 'text':
        text = []
        text.append("Invoice Number: " + (invoice_data.get('invoice_number') or 'N/A'))
        text.append("Issue Date: " + (invoice_data.get('issue_date') or 'N/A'))
        text.append("Client: " + (invoice_data.get('client') or 'N/A'))
        text.append("Email: " + (invoice_data.get('email') or 'N/A'))
        text.append("Address: " + (invoice_data.get('address') or 'N/A'))
        text.append("\nItems:")
        
        if invoice_data.get('items'):
            for item in invoice_data['items']:
                text.append(f"  {item.get('name')} - {item.get('quantity')} x ${item.get('unit_price'):.2f} = ${item.get('total_price'):.2f}")
        else:
            text.append("  No items found")
        
        text.append("\nTotal: $" + (f"{invoice_data.get('total'):.2f}" if invoice_data.get('total') else 'N/A'))
        
        return "\n".join(text)
    
    elif format_type == 'html':
        html = []
        html.append("<div class='invoice'>")
        html.append(f"<p><strong>Invoice Number:</strong> {invoice_data.get('invoice_number') or 'N/A'}</p>")
        html.append(f"<p><strong>Issue Date:</strong> {invoice_data.get('issue_date') or 'N/A'}</p>")
        html.append(f"<p><strong>Client:</strong> {invoice_data.get('client') or 'N/A'}</p>")
        html.append(f"<p><strong>Email:</strong> {invoice_data.get('email') or 'N/A'}</p>")
        html.append(f"<p><strong>Address:</strong> {invoice_data.get('address') or 'N/A'}</p>")
        
        html.append("<h3>Items:</h3>")
        html.append("<table border='1'>")
        html.append("<tr><th>Item</th><th>Quantity</th><th>Unit Price</th><th>Total</th></tr>")
        
        if invoice_data.get('items'):
            for item in invoice_data['items']:
                html.append("<tr>")
                html.append(f"<td>{item.get('name')}</td>")
                html.append(f"<td>{item.get('quantity')}</td>")
                html.append(f"<td>${item.get('unit_price'):.2f}</td>")
                html.append(f"<td>${item.get('total_price'):.2f}</td>")
                html.append("</tr>")
        else:
            html.append("<tr><td colspan='4'>No items found</td></tr>")
        
        html.append("</table>")
        html.append(f"<p><strong>Total:</strong> ${invoice_data.get('total'):.2f if invoice_data.get('total') else 'N/A'}</p>")
        html.append("</div>")
        
        return "\n".join(html)
    
    else:
        raise ValueError(f"Unknown format type: {format_type}")
