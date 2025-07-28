"""
Extraction Service for structured data extraction from OCR text
Uses rule-based pattern matching without spaCy for commercial safety
"""

import re
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
import json

from app.utils.pattern_matcher import PatternMatcher
from app.models.company import Company
from app.models.customer import Customer

logger = logging.getLogger(__name__)

class ExtractionService:
    """Service for extracting structured data from OCR text."""
    
    def __init__(self):
        """Initialize extraction service with pattern matcher."""
        self.pattern_matcher = PatternMatcher()
    
    def extract_invoice_data(self, ocr_text: str, tenant_id: str = 'default') -> Dict:
        """
        Extract all invoice data from OCR text.
        
        Args:
            ocr_text: Raw OCR extracted text
            tenant_id: Tenant identifier for multi-tenant support
            
        Returns:
            Dictionary containing extracted invoice data
        """
        start_time = datetime.now()
        
        try:
            # Clean and normalize text
            cleaned_text = self._clean_text(ocr_text)
            
            # Extract different sections
            invoice_metadata = self._extract_invoice_metadata(cleaned_text)
            company_data = self._extract_company_data(cleaned_text, tenant_id)
            customer_data = self._extract_customer_data(cleaned_text, tenant_id)
            financial_data = self._extract_financial_data(cleaned_text)
            line_items = self._extract_line_items(cleaned_text)
            
            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            # Calculate overall confidence
            confidence_scores = [
                invoice_metadata.get('confidence', 0.0),
                company_data.get('confidence', 0.0),
                customer_data.get('confidence', 0.0),
                financial_data.get('confidence', 0.0)
            ]
            overall_confidence = sum(confidence_scores) / len(confidence_scores)
            
            extracted_data = {
                'invoice_metadata': invoice_metadata,
                'company_data': company_data,
                'customer_data': customer_data,
                'financial_data': financial_data,
                'line_items': line_items,
                'extraction_metadata': {
                    'processing_time_ms': processing_time,
                    'overall_confidence': overall_confidence,
                    'total_line_items': len(line_items),
                    'text_length': len(cleaned_text),
                    'extraction_engine': 'RuleBasedExtractor'
                }
            }
            
            logger.info(f"Invoice data extraction completed in {processing_time:.2f}ms")
            return extracted_data
            
        except Exception as e:
            logger.error(f"Invoice data extraction failed: {str(e)}")
            raise RuntimeError(f"Invoice data extraction failed: {str(e)}")
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize OCR text."""
        if not text:
            return ""
        
        # Remove excessive whitespace
        cleaned = re.sub(r'\s+', ' ', text.strip())
        
        # Fix common OCR errors
        cleaned = cleaned.replace('|', 'I')  # Common OCR mistake
        cleaned = cleaned.replace('0', 'O', 1)  # First character might be letter O
        
        # Normalize currency symbols
        cleaned = re.sub(r'[$]\s*', '$', cleaned)
        
        return cleaned
    
    def _extract_invoice_metadata(self, text: str) -> Dict:
        """Extract invoice metadata (number, date, due date, etc.)."""
        metadata = {
            'invoice_number': '',
            'invoice_date': None,
            'due_date': None,
            'po_number': '',
            'confidence': 0.0
        }
        
        confidence_scores = []
        
        # Extract invoice number
        invoice_number, conf = self.pattern_matcher.extract_invoice_number(text)
        if invoice_number:
            metadata['invoice_number'] = invoice_number
            confidence_scores.append(conf)
        
        # Extract invoice date
        invoice_date, conf = self.pattern_matcher.extract_invoice_date(text)
        if invoice_date:
            metadata['invoice_date'] = invoice_date
            confidence_scores.append(conf)
        
        # Extract due date
        due_date, conf = self.pattern_matcher.extract_due_date(text)
        if due_date:
            metadata['due_date'] = due_date
            confidence_scores.append(conf)
        
        # Extract PO number
        po_number, conf = self.pattern_matcher.extract_po_number(text)
        if po_number:
            metadata['po_number'] = po_number
            confidence_scores.append(conf)
        
        # Calculate average confidence
        metadata['confidence'] = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
        
        return metadata
    
    def _extract_company_data(self, text: str, tenant_id: str) -> Dict:
        """Extract company/vendor information."""
        company_data = {
            'name': '',
            'address_line1': '',
            'address_line2': '',
            'city': '',
            'state_province': '',
            'postal_code': '',
            'country': '',
            'phone': '',
            'email': '',
            'tax_id': '',
            'website': '',
            'confidence': 0.0
        }
        
        confidence_scores = []
        
        # Extract company name (usually at the top)
        company_name, conf = self.pattern_matcher.extract_company_name(text)
        if company_name:
            company_data['name'] = company_name
            confidence_scores.append(conf)
        
        # Extract address
        address_components = self.pattern_matcher.extract_address(text, 'company')
        if address_components:
            company_data.update(address_components)
            confidence_scores.append(0.8)  # Assume good confidence for address
        
        # Extract contact information
        phone, conf = self.pattern_matcher.extract_phone(text)
        if phone:
            company_data['phone'] = phone
            confidence_scores.append(conf)
        
        email, conf = self.pattern_matcher.extract_email(text)
        if email:
            company_data['email'] = email
            confidence_scores.append(conf)
        
        # Extract tax ID
        tax_id, conf = self.pattern_matcher.extract_tax_id(text)
        if tax_id:
            company_data['tax_id'] = tax_id
            confidence_scores.append(conf)
        
        # Extract website
        website, conf = self.pattern_matcher.extract_website(text)
        if website:
            company_data['website'] = website
            confidence_scores.append(conf)
        
        # Try to match with existing companies
        if company_data['name']:
            similar_companies = Company.find_similar(
                company_data['name'], 
                company_data['tax_id'], 
                tenant_id
            )
            
            if similar_companies:
                # Use existing company data to improve extraction
                existing_company = similar_companies[0]
                company_data['existing_company_id'] = existing_company.id
                
                # Fill in missing data from existing company
                if not company_data['address_line1'] and existing_company.address_line1:
                    company_data['address_line1'] = existing_company.address_line1
                if not company_data['phone'] and existing_company.phone:
                    company_data['phone'] = existing_company.phone
                if not company_data['email'] and existing_company.email:
                    company_data['email'] = existing_company.email
        
        # Calculate average confidence
        company_data['confidence'] = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
        
        return company_data
    
    def _extract_customer_data(self, text: str, tenant_id: str) -> Dict:
        """Extract customer/billing information."""
        customer_data = {
            'name': '',
            'company_name': '',
            'billing_address_line1': '',
            'billing_address_line2': '',
            'billing_city': '',
            'billing_state_province': '',
            'billing_postal_code': '',
            'billing_country': '',
            'email': '',
            'phone': '',
            'confidence': 0.0
        }
        
        confidence_scores = []
        
        # Extract customer information (usually in "Bill To" section)
        customer_info = self.pattern_matcher.extract_customer_info(text)
        if customer_info:
            customer_data.update(customer_info)
            confidence_scores.append(0.8)
        
        # Extract billing address
        billing_address = self.pattern_matcher.extract_address(text, 'billing')
        if billing_address:
            # Map generic address to billing address
            for key, value in billing_address.items():
                billing_key = f"billing_{key}" if not key.startswith('billing_') else key
                customer_data[billing_key] = value
            confidence_scores.append(0.7)
        
        # Try to match with existing customers
        if customer_data['name'] or customer_data['email']:
            similar_customers = Customer.find_similar(
                customer_data['name'],
                customer_data['email'],
                None,  # No tax_id for customers usually
                tenant_id
            )
            
            if similar_customers:
                existing_customer = similar_customers[0]
                customer_data['existing_customer_id'] = existing_customer.id
        
        # Calculate average confidence
        customer_data['confidence'] = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
        
        return customer_data
    
    def _extract_financial_data(self, text: str) -> Dict:
        """Extract financial totals and payment information."""
        financial_data = {
            'currency': 'USD',
            'subtotal_amount': 0.0,
            'tax_amount': 0.0,
            'tax_rate': 0.0,
            'discount_amount': 0.0,
            'shipping_amount': 0.0,
            'total_amount': 0.0,
            'payment_terms': '',
            'confidence': 0.0
        }
        
        confidence_scores = []
        
        # Extract currency
        currency, conf = self.pattern_matcher.extract_currency(text)
        if currency:
            financial_data['currency'] = currency
            confidence_scores.append(conf)
        
        # Extract amounts
        amounts = self.pattern_matcher.extract_amounts(text)
        
        if 'subtotal' in amounts:
            financial_data['subtotal_amount'] = amounts['subtotal']
            confidence_scores.append(0.9)
        
        if 'tax' in amounts:
            financial_data['tax_amount'] = amounts['tax']
            confidence_scores.append(0.9)
        
        if 'total' in amounts:
            financial_data['total_amount'] = amounts['total']
            confidence_scores.append(0.9)
        
        if 'discount' in amounts:
            financial_data['discount_amount'] = amounts['discount']
            confidence_scores.append(0.8)
        
        if 'shipping' in amounts:
            financial_data['shipping_amount'] = amounts['shipping']
            confidence_scores.append(0.8)
        
        # Extract tax rate
        tax_rate, conf = self.pattern_matcher.extract_tax_rate(text)
        if tax_rate:
            financial_data['tax_rate'] = tax_rate
            confidence_scores.append(conf)
        
        # Extract payment terms
        payment_terms, conf = self.pattern_matcher.extract_payment_terms(text)
        if payment_terms:
            financial_data['payment_terms'] = payment_terms
            confidence_scores.append(conf)
        
        # Validate and recalculate totals if needed
        financial_data = self._validate_financial_data(financial_data)
        
        # Calculate average confidence
        financial_data['confidence'] = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
        
        return financial_data
    
    def _extract_line_items(self, text: str) -> List[Dict]:
        """Extract line items from invoice text."""
        line_items = []
        
        # Find the line items section
        line_items_text = self.pattern_matcher.extract_line_items_section(text)
        if not line_items_text:
            return line_items
        
        # Split into potential line items
        lines = line_items_text.split('\n')
        line_number = 1
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Try to parse this line as a line item
            line_item = self.pattern_matcher.parse_line_item(line, line_number)
            
            if line_item and line_item.get('description'):
                # Calculate total price if missing
                if not line_item.get('total_price') and line_item.get('quantity') and line_item.get('unit_price'):
                    try:
                        quantity = float(line_item['quantity'])
                        unit_price = float(line_item['unit_price'])
                        line_item['total_price'] = round(quantity * unit_price, 2)
                    except (ValueError, TypeError):
                        line_item['total_price'] = 0.0
                
                line_items.append(line_item)
                line_number += 1
        
        return line_items
    
    def _validate_financial_data(self, financial_data: Dict) -> Dict:
        """Validate and recalculate financial totals."""
        try:
            subtotal = Decimal(str(financial_data.get('subtotal_amount', 0)))
            tax = Decimal(str(financial_data.get('tax_amount', 0)))
            discount = Decimal(str(financial_data.get('discount_amount', 0)))
            shipping = Decimal(str(financial_data.get('shipping_amount', 0)))
            total = Decimal(str(financial_data.get('total_amount', 0)))
            
            # Calculate expected total
            calculated_total = subtotal + tax + shipping - discount
            
            # If total is missing or significantly different, use calculated total
            if not total or abs(total - calculated_total) > Decimal('0.01'):
                financial_data['total_amount'] = float(calculated_total)
                financial_data['calculated_total'] = True
            
            # Calculate tax rate if missing
            if not financial_data.get('tax_rate') and subtotal > 0 and tax > 0:
                tax_rate = (tax / subtotal) * 100
                financial_data['tax_rate'] = float(tax_rate)
                financial_data['calculated_tax_rate'] = True
            
        except (InvalidOperation, ValueError, TypeError) as e:
            logger.warning(f"Financial data validation failed: {str(e)}")
        
        return financial_data
    
    def enhance_extraction_with_existing_data(self, extracted_data: Dict, existing_company: Company = None, 
                                            existing_customer: Customer = None) -> Dict:
        """Enhance extracted data with existing company/customer information."""
        
        if existing_company:
            company_data = extracted_data.get('company_data', {})
            
            # Fill missing company data
            if not company_data.get('phone') and existing_company.phone:
                company_data['phone'] = existing_company.phone
            
            if not company_data.get('email') and existing_company.email:
                company_data['email'] = existing_company.email
            
            if not company_data.get('address_line1') and existing_company.address_line1:
                company_data['address_line1'] = existing_company.address_line1
                company_data['city'] = existing_company.city
                company_data['state_province'] = existing_company.state_province
                company_data['postal_code'] = existing_company.postal_code
                company_data['country'] = existing_company.country
            
            # Use existing currency if not detected
            financial_data = extracted_data.get('financial_data', {})
            if not financial_data.get('currency') and existing_company.currency:
                financial_data['currency'] = existing_company.currency
        
        if existing_customer:
            customer_data = extracted_data.get('customer_data', {})
            
            # Fill missing customer data
            if not customer_data.get('email') and existing_customer.email:
                customer_data['email'] = existing_customer.email
            
            if not customer_data.get('phone') and existing_customer.phone:
                customer_data['phone'] = existing_customer.phone
            
            # Use customer's payment terms if not detected
            financial_data = extracted_data.get('financial_data', {})
            if not financial_data.get('payment_terms') and existing_customer.payment_terms_days:
                financial_data['payment_terms'] = f"Net {existing_customer.payment_terms_days}"
        
        return extracted_data
    
    def calculate_extraction_confidence(self, extracted_data: Dict) -> float:
        """Calculate overall extraction confidence score."""
        
        confidence_weights = {
            'invoice_metadata': 0.3,
            'company_data': 0.25,
            'customer_data': 0.15,
            'financial_data': 0.3
        }
        
        total_confidence = 0.0
        total_weight = 0.0
        
        for section, weight in confidence_weights.items():
            section_data = extracted_data.get(section, {})
            section_confidence = section_data.get('confidence', 0.0)
            
            total_confidence += section_confidence * weight
            total_weight += weight
        
        overall_confidence = total_confidence / total_weight if total_weight > 0 else 0.0
        
        # Bonus for having line items
        line_items = extracted_data.get('line_items', [])
        if len(line_items) > 0:
            overall_confidence = min(overall_confidence + 0.1, 1.0)
        
        return round(overall_confidence, 3)