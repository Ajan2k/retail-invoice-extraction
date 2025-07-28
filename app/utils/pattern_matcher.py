"""
Pattern Matcher for extracting structured data from invoice text
Uses rule-based regex patterns without spaCy for commercial safety
"""

import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)

class PatternMatcher:
    """Rule-based pattern matcher for invoice data extraction."""
    
    def __init__(self):
        """Initialize pattern matcher with compiled regex patterns."""
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Compile all regex patterns for performance."""
        
        # Invoice number patterns
        self.invoice_number_patterns = [
            re.compile(r'invoice\s*#?\s*:?\s*([A-Z0-9\-]+)', re.IGNORECASE),
            re.compile(r'inv\s*#?\s*:?\s*([A-Z0-9\-]+)', re.IGNORECASE),
            re.compile(r'bill\s*#?\s*:?\s*([A-Z0-9\-]+)', re.IGNORECASE),
            re.compile(r'receipt\s*#?\s*:?\s*([A-Z0-9\-]+)', re.IGNORECASE),
            re.compile(r'#\s*([A-Z0-9\-]{3,})', re.IGNORECASE)
        ]
        
        # Date patterns
        self.date_patterns = [
            re.compile(r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})'),
            re.compile(r'(\d{2,4})[/-](\d{1,2})[/-](\d{1,2})'),
            re.compile(r'(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{2,4})', re.IGNORECASE),
            re.compile(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2}),?\s+(\d{2,4})', re.IGNORECASE)
        ]
        
        # Amount patterns
        self.amount_patterns = [
            re.compile(r'[$€£¥₹]\s*(\d{1,3}(?:,\d{3})*\.?\d{0,2})'),
            re.compile(r'(\d{1,3}(?:,\d{3})*\.?\d{0,2})\s*(?:USD|EUR|GBP|JPY|INR)', re.IGNORECASE),
            re.compile(r'(\d{1,3}(?:,\d{3})*\.?\d{0,2})')
        ]
        
        # Email pattern
        self.email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
        
        # Phone patterns
        self.phone_patterns = [
            re.compile(r'\+?1?[-.\s]?\(?(\d{3})\)?[-.\s]?(\d{3})[-.\s]?(\d{4})'),
            re.compile(r'\+?(\d{1,3})[-.\s]?(\d{3,4})[-.\s]?(\d{3,4})[-.\s]?(\d{3,4})'),
            re.compile(r'(\d{3})[-.\s]?(\d{3})[-.\s]?(\d{4})')
        ]
        
        # Website pattern
        self.website_pattern = re.compile(r'(?:https?://)?(?:www\.)?([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(?:/[^\s]*)?')
        
        # Tax ID patterns
        self.tax_id_patterns = [
            re.compile(r'tax\s*id\s*:?\s*([A-Z0-9\-]+)', re.IGNORECASE),
            re.compile(r'ein\s*:?\s*(\d{2}-\d{7})', re.IGNORECASE),
            re.compile(r'ssn\s*:?\s*(\d{3}-\d{2}-\d{4})', re.IGNORECASE),
            re.compile(r'vat\s*:?\s*([A-Z0-9\-]+)', re.IGNORECASE)
        ]
        
        # Address patterns
        self.address_patterns = [
            re.compile(r'(\d+\s+[A-Za-z\s]+(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|Dr|Drive|Ln|Lane|Ct|Court|Pl|Place)\.?)', re.IGNORECASE),
            re.compile(r'([A-Za-z\s]+),\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)', re.IGNORECASE),  # City, State ZIP
            re.compile(r'(\d{5}(?:-\d{4})?)'),  # ZIP code
        ]
        
        # Payment terms patterns
        self.payment_terms_patterns = [
            re.compile(r'net\s+(\d+)', re.IGNORECASE),
            re.compile(r'due\s+on\s+receipt', re.IGNORECASE),
            re.compile(r'(\d+)\s+days?', re.IGNORECASE),
            re.compile(r'cash\s+on\s+delivery', re.IGNORECASE),
            re.compile(r'cod', re.IGNORECASE)
        ]
        
        # Line item patterns
        self.line_item_patterns = [
            re.compile(r'(\d+(?:\.\d{1,3})?)\s+([^\d$€£¥₹]+?)\s+\$?(\d+(?:\.\d{2})?)\s+\$?(\d+(?:\.\d{2})?)', re.IGNORECASE),
            re.compile(r'([^\d$€£¥₹]+?)\s+(\d+(?:\.\d{1,3})?)\s+\$?(\d+(?:\.\d{2})?)\s+\$?(\d+(?:\.\d{2})?)', re.IGNORECASE)
        ]
    
    def extract_invoice_number(self, text: str) -> Tuple[str, float]:
        """Extract invoice number from text."""
        for pattern in self.invoice_number_patterns:
            match = pattern.search(text)
            if match:
                invoice_number = match.group(1).strip()
                # Higher confidence for patterns with "invoice" keyword
                confidence = 0.9 if 'invoice' in pattern.pattern.lower() else 0.7
                return invoice_number, confidence
        
        return "", 0.0
    
    def extract_invoice_date(self, text: str) -> Tuple[Optional[date], float]:
        """Extract invoice date from text."""
        # Look for date near "invoice date" or "date" keywords
        date_keywords = ['invoice date', 'date', 'dated', 'bill date']
        
        for keyword in date_keywords:
            keyword_pattern = re.compile(rf'{keyword}\s*:?\s*(.{{0,50}})', re.IGNORECASE)
            keyword_match = keyword_pattern.search(text)
            
            if keyword_match:
                date_text = keyword_match.group(1)
                parsed_date = self._parse_date(date_text)
                if parsed_date:
                    return parsed_date, 0.9
        
        # Fallback: look for any date in the text
        parsed_date = self._parse_date(text[:200])  # Check first 200 chars
        if parsed_date:
            return parsed_date, 0.6
        
        return None, 0.0
    
    def extract_due_date(self, text: str) -> Tuple[Optional[date], float]:
        """Extract due date from text."""
        due_keywords = ['due date', 'due', 'payment due', 'payable by']
        
        for keyword in due_keywords:
            keyword_pattern = re.compile(rf'{keyword}\s*:?\s*(.{{0,50}})', re.IGNORECASE)
            keyword_match = keyword_pattern.search(text)
            
            if keyword_match:
                date_text = keyword_match.group(1)
                parsed_date = self._parse_date(date_text)
                if parsed_date:
                    return parsed_date, 0.9
        
        return None, 0.0
    
    def extract_po_number(self, text: str) -> Tuple[str, float]:
        """Extract purchase order number from text."""
        po_patterns = [
            re.compile(r'p\.?o\.?\s*#?\s*:?\s*([A-Z0-9\-]+)', re.IGNORECASE),
            re.compile(r'purchase\s+order\s*#?\s*:?\s*([A-Z0-9\-]+)', re.IGNORECASE),
            re.compile(r'order\s*#?\s*:?\s*([A-Z0-9\-]+)', re.IGNORECASE)
        ]
        
        for pattern in po_patterns:
            match = pattern.search(text)
            if match:
                po_number = match.group(1).strip()
                confidence = 0.8 if 'purchase' in pattern.pattern.lower() else 0.7
                return po_number, confidence
        
        return "", 0.0
    
    def extract_company_name(self, text: str) -> Tuple[str, float]:
        """Extract company name (usually at the top of the invoice)."""
        lines = text.split('\n')
        
        # Company name is usually in the first few lines
        for i, line in enumerate(lines[:5]):
            line = line.strip()
            
            # Skip empty lines and common headers
            if not line or line.lower() in ['invoice', 'bill', 'receipt']:
                continue
            
            # Skip lines that look like addresses or contact info
            if (re.search(r'\d+\s+[A-Za-z\s]+(?:St|Street|Ave|Avenue)', line, re.IGNORECASE) or
                self.email_pattern.search(line) or
                any(pattern.search(line) for pattern in self.phone_patterns)):
                continue
            
            # This is likely the company name
            if len(line) > 2 and not line.isdigit():
                confidence = 0.9 if i == 0 else 0.7 - (i * 0.1)
                return line, max(confidence, 0.3)
        
        return "", 0.0
    
    def extract_address(self, text: str, address_type: str = 'company') -> Dict[str, str]:
        """Extract address components from text."""
        address_data = {
            'address_line1': '',
            'address_line2': '',
            'city': '',
            'state_province': '',
            'postal_code': '',
            'country': ''
        }
        
        # Look for address sections
        if address_type == 'billing':
            # Look for "Bill To" section
            bill_to_pattern = re.compile(r'bill\s+to\s*:?\s*(.*?)(?=\n\n|\n[A-Z]|\Z)', re.IGNORECASE | re.DOTALL)
            match = bill_to_pattern.search(text)
            if match:
                address_text = match.group(1)
            else:
                return address_data
        else:
            # Use the first part of the text for company address
            address_text = '\n'.join(text.split('\n')[:10])
        
        lines = [line.strip() for line in address_text.split('\n') if line.strip()]
        
        # Extract components
        for line in lines:
            # Check for street address
            if not address_data['address_line1']:
                street_match = self.address_patterns[0].search(line)
                if street_match:
                    address_data['address_line1'] = street_match.group(1)
                    continue
            
            # Check for city, state, ZIP
            city_state_zip_match = self.address_patterns[1].search(line)
            if city_state_zip_match:
                address_data['city'] = city_state_zip_match.group(1)
                address_data['state_province'] = city_state_zip_match.group(2)
                address_data['postal_code'] = city_state_zip_match.group(3)
                continue
            
            # Check for ZIP code only
            zip_match = self.address_patterns[2].search(line)
            if zip_match and not address_data['postal_code']:
                address_data['postal_code'] = zip_match.group(1)
        
        return address_data
    
    def extract_phone(self, text: str) -> Tuple[str, float]:
        """Extract phone number from text."""
        for pattern in self.phone_patterns:
            match = pattern.search(text)
            if match:
                # Format phone number
                if len(match.groups()) == 3:
                    phone = f"({match.group(1)}) {match.group(2)}-{match.group(3)}"
                else:
                    phone = match.group(0)
                return phone, 0.8
        
        return "", 0.0
    
    def extract_email(self, text: str) -> Tuple[str, float]:
        """Extract email address from text."""
        match = self.email_pattern.search(text)
        if match:
            return match.group(0), 0.9
        return "", 0.0
    
    def extract_website(self, text: str) -> Tuple[str, float]:
        """Extract website URL from text."""
        match = self.website_pattern.search(text)
        if match:
            return match.group(0), 0.8
        return "", 0.0
    
    def extract_tax_id(self, text: str) -> Tuple[str, float]:
        """Extract tax ID from text."""
        for pattern in self.tax_id_patterns:
            match = pattern.search(text)
            if match:
                return match.group(1), 0.8
        return "", 0.0
    
    def extract_currency(self, text: str) -> Tuple[str, float]:
        """Extract currency from text."""
        currency_symbols = {
            '$': 'USD',
            '€': 'EUR',
            '£': 'GBP',
            '¥': 'JPY',
            '₹': 'INR'
        }
        
        # Look for currency symbols
        for symbol, code in currency_symbols.items():
            if symbol in text:
                return code, 0.9
        
        # Look for currency codes
        currency_pattern = re.compile(r'\b(USD|EUR|GBP|JPY|INR|CAD|AUD)\b', re.IGNORECASE)
        match = currency_pattern.search(text)
        if match:
            return match.group(1).upper(), 0.9
        
        return 'USD', 0.3  # Default to USD
    
    def extract_amounts(self, text: str) -> Dict[str, float]:
        """Extract various amounts from text."""
        amounts = {}
        
        # Define amount keywords and their patterns
        amount_keywords = {
            'subtotal': [r'subtotal\s*:?\s*\$?(\d{1,3}(?:,\d{3})*\.?\d{0,2})', r'sub\s*total\s*:?\s*\$?(\d{1,3}(?:,\d{3})*\.?\d{0,2})'],
            'tax': [r'tax\s*:?\s*\$?(\d{1,3}(?:,\d{3})*\.?\d{0,2})', r'vat\s*:?\s*\$?(\d{1,3}(?:,\d{3})*\.?\d{0,2})'],
            'total': [r'total\s*:?\s*\$?(\d{1,3}(?:,\d{3})*\.?\d{0,2})', r'amount\s*due\s*:?\s*\$?(\d{1,3}(?:,\d{3})*\.?\d{0,2})'],
            'discount': [r'discount\s*:?\s*\$?(\d{1,3}(?:,\d{3})*\.?\d{0,2})'],
            'shipping': [r'shipping\s*:?\s*\$?(\d{1,3}(?:,\d{3})*\.?\d{0,2})', r'freight\s*:?\s*\$?(\d{1,3}(?:,\d{3})*\.?\d{0,2})']
        }
        
        for amount_type, patterns in amount_keywords.items():
            for pattern_str in patterns:
                pattern = re.compile(pattern_str, re.IGNORECASE)
                match = pattern.search(text)
                if match:
                    try:
                        amount_str = match.group(1).replace(',', '')
                        amounts[amount_type] = float(amount_str)
                        break
                    except (ValueError, IndexError):
                        continue
        
        return amounts
    
    def extract_tax_rate(self, text: str) -> Tuple[float, float]:
        """Extract tax rate percentage from text."""
        tax_rate_patterns = [
            re.compile(r'tax\s*(?:rate)?\s*:?\s*(\d{1,2}(?:\.\d{1,2})?)%', re.IGNORECASE),
            re.compile(r'(\d{1,2}(?:\.\d{1,2})?)%\s*tax', re.IGNORECASE),
            re.compile(r'vat\s*:?\s*(\d{1,2}(?:\.\d{1,2})?)%', re.IGNORECASE)
        ]
        
        for pattern in tax_rate_patterns:
            match = pattern.search(text)
            if match:
                try:
                    tax_rate = float(match.group(1))
                    return tax_rate, 0.9
                except ValueError:
                    continue
        
        return 0.0, 0.0
    
    def extract_payment_terms(self, text: str) -> Tuple[str, float]:
        """Extract payment terms from text."""
        for pattern in self.payment_terms_patterns:
            match = pattern.search(text)
            if match:
                if 'net' in pattern.pattern.lower():
                    return f"Net {match.group(1)}", 0.9
                elif 'receipt' in pattern.pattern.lower():
                    return "Due on receipt", 0.9
                elif 'days' in pattern.pattern.lower():
                    return f"{match.group(1)} days", 0.8
                elif 'cod' in pattern.pattern.lower():
                    return "Cash on delivery", 0.8
                else:
                    return match.group(0), 0.7
        
        return "", 0.0
    
    def extract_customer_info(self, text: str) -> Dict[str, str]:
        """Extract customer information from text."""
        customer_info = {
            'name': '',
            'company_name': '',
            'email': '',
            'phone': ''
        }
        
        # Look for "Bill To" or "Customer" section
        customer_patterns = [
            re.compile(r'bill\s+to\s*:?\s*(.*?)(?=\n\n|\n[A-Z]|\Z)', re.IGNORECASE | re.DOTALL),
            re.compile(r'customer\s*:?\s*(.*?)(?=\n\n|\n[A-Z]|\Z)', re.IGNORECASE | re.DOTALL),
            re.compile(r'sold\s+to\s*:?\s*(.*?)(?=\n\n|\n[A-Z]|\Z)', re.IGNORECASE | re.DOTALL)
        ]
        
        for pattern in customer_patterns:
            match = pattern.search(text)
            if match:
                customer_text = match.group(1).strip()
                lines = [line.strip() for line in customer_text.split('\n') if line.strip()]
                
                if lines:
                    # First line is usually the name or company
                    customer_info['name'] = lines[0]
                    
                    # Look for email and phone in the section
                    email_match = self.email_pattern.search(customer_text)
                    if email_match:
                        customer_info['email'] = email_match.group(0)
                    
                    for pattern in self.phone_patterns:
                        phone_match = pattern.search(customer_text)
                        if phone_match:
                            customer_info['phone'] = phone_match.group(0)
                            break
                
                break
        
        return customer_info
    
    def extract_line_items_section(self, text: str) -> str:
        """Extract the line items section from text."""
        # Look for common line item section headers
        section_patterns = [
            re.compile(r'(description\s*quantity\s*price\s*amount.*?)(?=\n\s*subtotal|\n\s*tax|\n\s*total|\Z)', re.IGNORECASE | re.DOTALL),
            re.compile(r'(item\s*qty\s*price\s*total.*?)(?=\n\s*subtotal|\n\s*tax|\n\s*total|\Z)', re.IGNORECASE | re.DOTALL),
            re.compile(r'(qty\s*description\s*unit\s*price\s*total.*?)(?=\n\s*subtotal|\n\s*tax|\n\s*total|\Z)', re.IGNORECASE | re.DOTALL)
        ]
        
        for pattern in section_patterns:
            match = pattern.search(text)
            if match:
                return match.group(1)
        
        # Fallback: look for lines that might be line items
        lines = text.split('\n')
        line_items_section = []
        in_items_section = False
        
        for line in lines:
            line = line.strip()
            
            # Check if this line has typical line item pattern (description + numbers)
            if re.search(r'^.+\s+\d+(?:\.\d{1,3})?\s+\$?\d+(?:\.\d{2})?\s+\$?\d+(?:\.\d{2})?$', line):
                in_items_section = True
                line_items_section.append(line)
            elif in_items_section and (re.search(r'subtotal|tax|total', line, re.IGNORECASE) or not line):
                break
            elif in_items_section:
                line_items_section.append(line)
        
        return '\n'.join(line_items_section)
    
    def parse_line_item(self, line: str, line_number: int) -> Optional[Dict]:
        """Parse a single line item."""
        line = line.strip()
        if not line:
            return None
        
        # Try different line item patterns
        for pattern in self.line_item_patterns:
            match = pattern.search(line)
            if match:
                groups = match.groups()
                
                if len(groups) >= 4:
                    try:
                        # Pattern 1: qty, description, unit_price, total
                        if groups[0].replace('.', '').isdigit():
                            return {
                                'line_number': line_number,
                                'quantity': float(groups[0]),
                                'description': groups[1].strip(),
                                'unit_price': float(groups[2]),
                                'total_price': float(groups[3]),
                                'confidence': 0.8
                            }
                        # Pattern 2: description, qty, unit_price, total
                        else:
                            return {
                                'line_number': line_number,
                                'description': groups[0].strip(),
                                'quantity': float(groups[1]),
                                'unit_price': float(groups[2]),
                                'total_price': float(groups[3]),
                                'confidence': 0.8
                            }
                    except (ValueError, IndexError):
                        continue
        
        # Fallback: simple description extraction
        if not re.search(r'subtotal|tax|total|shipping|discount', line, re.IGNORECASE):
            return {
                'line_number': line_number,
                'description': line,
                'quantity': 1.0,
                'unit_price': 0.0,
                'total_price': 0.0,
                'confidence': 0.3
            }
        
        return None
    
    def _parse_date(self, text: str) -> Optional[date]:
        """Parse date from text using various formats."""
        month_names = {
            'jan': 1, 'january': 1,
            'feb': 2, 'february': 2,
            'mar': 3, 'march': 3,
            'apr': 4, 'april': 4,
            'may': 5,
            'jun': 6, 'june': 6,
            'jul': 7, 'july': 7,
            'aug': 8, 'august': 8,
            'sep': 9, 'september': 9,
            'oct': 10, 'october': 10,
            'nov': 11, 'november': 11,
            'dec': 12, 'december': 12
        }
        
        for pattern in self.date_patterns:
            match = pattern.search(text)
            if match:
                try:
                    groups = match.groups()
                    
                    if len(groups) == 3:
                        # Handle different date formats
                        if groups[1].lower() in month_names:
                            # Month name format
                            day = int(groups[0])
                            month = month_names[groups[1].lower()]
                            year = int(groups[2])
                        elif groups[0].lower() in month_names:
                            # Month name first
                            month = month_names[groups[0].lower()]
                            day = int(groups[1])
                            year = int(groups[2])
                        else:
                            # Numeric format - assume MM/DD/YYYY or DD/MM/YYYY
                            if int(groups[0]) > 12:
                                # DD/MM/YYYY
                                day = int(groups[0])
                                month = int(groups[1])
                                year = int(groups[2])
                            else:
                                # MM/DD/YYYY
                                month = int(groups[0])
                                day = int(groups[1])
                                year = int(groups[2])
                        
                        # Handle 2-digit years
                        if year < 100:
                            year += 2000 if year < 50 else 1900
                        
                        return date(year, month, day)
                        
                except (ValueError, IndexError):
                    continue
        
        return None