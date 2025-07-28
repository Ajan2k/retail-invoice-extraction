"""
Data validation utilities for Invoice Extraction System
"""

import re
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
import email_validator


class DataValidator:
    """Utility class for data validation and sanitization."""
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email address format."""
        try:
            email_validator.validate_email(email)
            return True
        except email_validator.EmailNotValidError:
            return False
    
    @staticmethod
    def validate_phone(phone: str) -> bool:
        """Validate phone number format."""
        if not phone:
            return False
        
        # Remove all non-digit characters
        digits_only = re.sub(r'\D', '', phone)
        
        # Check if length is reasonable (7-15 digits)
        return 7 <= len(digits_only) <= 15
    
    @staticmethod
    def validate_currency_amount(amount: Union[str, float, int, Decimal]) -> bool:
        """Validate currency amount."""
        try:
            decimal_amount = Decimal(str(amount))
            return decimal_amount >= 0
        except (InvalidOperation, TypeError, ValueError):
            return False
    
    @staticmethod
    def validate_date(date_value: Union[str, date, datetime]) -> bool:
        """Validate date value."""
        if isinstance(date_value, (date, datetime)):
            return True
        
        if isinstance(date_value, str):
            try:
                datetime.strptime(date_value, '%Y-%m-%d')
                return True
            except ValueError:
                pass
        
        return False
    
    @staticmethod
    def sanitize_string(text: str, max_length: Optional[int] = None) -> str:
        """Sanitize string input."""
        if not isinstance(text, str):
            return ""
        
        # Remove leading/trailing whitespace
        sanitized = text.strip()
        
        # Remove null bytes and other control characters
        sanitized = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', sanitized)
        
        # Truncate if max_length specified
        if max_length and len(sanitized) > max_length:
            sanitized = sanitized[:max_length]
        
        return sanitized
    
    @staticmethod
    def validate_invoice_number(invoice_number: str) -> bool:
        """Validate invoice number format."""
        if not invoice_number:
            return False
        
        # Must be at least 3 characters
        if len(invoice_number) < 3:
            return False
        
        # Can contain letters, numbers, hyphens, underscores
        if not re.match(r'^[A-Za-z0-9\-_]+$', invoice_number):
            return False
        
        return True
    
    @staticmethod
    def validate_tax_id(tax_id: str) -> bool:
        """Validate tax ID format."""
        if not tax_id:
            return False
        
        # Remove spaces and hyphens for validation
        clean_tax_id = re.sub(r'[\s\-]', '', tax_id)
        
        # Must be alphanumeric and reasonable length
        if not re.match(r'^[A-Za-z0-9]+$', clean_tax_id):
            return False
        
        return 3 <= len(clean_tax_id) <= 20
    
    @staticmethod
    def validate_postal_code(postal_code: str, country: Optional[str] = None) -> bool:
        """Validate postal code format."""
        if not postal_code:
            return False
        
        # Basic validation - alphanumeric and reasonable length
        clean_code = re.sub(r'[\s\-]', '', postal_code)
        
        if not re.match(r'^[A-Za-z0-9]+$', clean_code):
            return False
        
        return 3 <= len(clean_code) <= 10
    
    @classmethod
    def validate_company_data(cls, data: Dict[str, Any]) -> Dict[str, List[str]]:
        """Validate company data and return validation errors."""
        errors = {}
        
        # Required fields
        if not data.get('name'):
            errors.setdefault('name', []).append('Company name is required')
        elif len(cls.sanitize_string(data['name'])) < 2:
            errors.setdefault('name', []).append('Company name must be at least 2 characters')
        
        # Email validation
        email = data.get('email')
        if email and not cls.validate_email(email):
            errors.setdefault('email', []).append('Invalid email format')
        
        # Phone validation
        phone = data.get('phone')
        if phone and not cls.validate_phone(phone):
            errors.setdefault('phone', []).append('Invalid phone number format')
        
        # Tax ID validation
        tax_id = data.get('tax_id')
        if tax_id and not cls.validate_tax_id(tax_id):
            errors.setdefault('tax_id', []).append('Invalid tax ID format')
        
        return errors
    
    @classmethod
    def validate_customer_data(cls, data: Dict[str, Any]) -> Dict[str, List[str]]:
        """Validate customer data and return validation errors."""
        errors = {}
        
        # Required fields
        if not data.get('name'):
            errors.setdefault('name', []).append('Customer name is required')
        elif len(cls.sanitize_string(data['name'])) < 2:
            errors.setdefault('name', []).append('Customer name must be at least 2 characters')
        
        # Email validation
        email = data.get('email')
        if email and not cls.validate_email(email):
            errors.setdefault('email', []).append('Invalid email format')
        
        # Phone validation
        phone = data.get('phone')
        if phone and not cls.validate_phone(phone):
            errors.setdefault('phone', []).append('Invalid phone number format')
        
        return errors
    
    @classmethod
    def validate_invoice_data(cls, data: Dict[str, Any]) -> Dict[str, List[str]]:
        """Validate invoice data and return validation errors."""
        errors = {}
        
        # Invoice number validation
        invoice_number = data.get('invoice_number')
        if not invoice_number:
            errors.setdefault('invoice_number', []).append('Invoice number is required')
        elif not cls.validate_invoice_number(invoice_number):
            errors.setdefault('invoice_number', []).append('Invalid invoice number format')
        
        # Date validation
        invoice_date = data.get('invoice_date')
        if invoice_date and not cls.validate_date(invoice_date):
            errors.setdefault('invoice_date', []).append('Invalid invoice date format')
        
        due_date = data.get('due_date')
        if due_date and not cls.validate_date(due_date):
            errors.setdefault('due_date', []).append('Invalid due date format')
        
        # Amount validation
        total_amount = data.get('total_amount')
        if total_amount is not None:
            if not cls.validate_currency_amount(total_amount):
                errors.setdefault('total_amount', []).append('Invalid total amount')
            elif Decimal(str(total_amount)) < 0:
                errors.setdefault('total_amount', []).append('Total amount cannot be negative')
        
        return errors
    
    @classmethod
    def validate_line_item_data(cls, data: Dict[str, Any]) -> Dict[str, List[str]]:
        """Validate line item data and return validation errors."""
        errors = {}
        
        # Description validation
        if not data.get('description'):
            errors.setdefault('description', []).append('Line item description is required')
        elif len(cls.sanitize_string(data['description'])) < 1:
            errors.setdefault('description', []).append('Line item description cannot be empty')
        
        # Quantity validation
        quantity = data.get('quantity')
        if quantity is not None:
            try:
                qty_decimal = Decimal(str(quantity))
                if qty_decimal <= 0:
                    errors.setdefault('quantity', []).append('Quantity must be greater than zero')
            except (InvalidOperation, TypeError, ValueError):
                errors.setdefault('quantity', []).append('Invalid quantity format')
        
        # Unit price validation
        unit_price = data.get('unit_price')
        if unit_price is not None:
            if not cls.validate_currency_amount(unit_price):
                errors.setdefault('unit_price', []).append('Invalid unit price format')
            elif Decimal(str(unit_price)) < 0:
                errors.setdefault('unit_price', []).append('Unit price cannot be negative')
        
        # Total price validation
        total_price = data.get('total_price')
        if total_price is not None:
            if not cls.validate_currency_amount(total_price):
                errors.setdefault('total_price', []).append('Invalid total price format')
            elif Decimal(str(total_price)) < 0:
                errors.setdefault('total_price', []).append('Total price cannot be negative')
        
        return errors
    
    @staticmethod
    def sanitize_file_name(filename: str) -> str:
        """Sanitize uploaded file name."""
        if not filename:
            return "unknown_file"
        
        # Remove path separators and special characters
        sanitized = re.sub(r'[^\w\-_\.]', '_', filename)
        
        # Remove multiple dots
        sanitized = re.sub(r'\.+', '.', sanitized)
        
        # Ensure reasonable length
        if len(sanitized) > 255:
            name, ext = sanitized.rsplit('.', 1) if '.' in sanitized else (sanitized, '')
            max_name_length = 255 - len(ext) - 1 if ext else 255
            sanitized = name[:max_name_length] + ('.' + ext if ext else '')
        
        return sanitized or "file"
    
    @staticmethod
    def validate_file_type(filename: str, allowed_extensions: set) -> bool:
        """Validate file type based on extension."""
        if not filename or '.' not in filename:
            return False
        
        extension = filename.rsplit('.', 1)[1].lower()
        return extension in allowed_extensions
    
    @staticmethod
    def validate_tenant_id(tenant_id: str) -> bool:
        """Validate tenant ID format."""
        if not tenant_id:
            return False
        
        # Must be alphanumeric with underscores, reasonable length
        if not re.match(r'^[a-zA-Z0-9_]+$', tenant_id):
            return False
        
        return 3 <= len(tenant_id) <= 50