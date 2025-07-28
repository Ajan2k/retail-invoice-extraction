"""
Validation Service for invoice data quality and business rule validation
"""

import logging
from typing import Dict, List, Tuple
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
import re

logger = logging.getLogger(__name__)

class ValidationService:
    """Service for validating extracted invoice data."""
    
    def __init__(self):
        """Initialize validation service."""
        self.validation_rules = self._initialize_validation_rules()
    
    def _initialize_validation_rules(self):
        """Initialize validation rules configuration."""
        return {
            'required_fields': {
                'invoice_metadata': ['invoice_number'],
                'company_data': ['name'],
                'financial_data': ['total_amount']
            },
            'confidence_thresholds': {
                'invoice_metadata': 0.6,
                'company_data': 0.5,
                'customer_data': 0.4,
                'financial_data': 0.7,
                'line_items': 0.5
            },
            'business_rules': {
                'max_total_amount': 1000000.00,  # $1M
                'min_total_amount': 0.01,
                'max_line_items': 100,
                'max_tax_rate': 50.0,  # 50%
                'future_invoice_date_days': 30  # Max 30 days in future
            }
        }
    
    def validate_invoice_data(self, extracted_data: Dict) -> Dict:
        """
        Validate extracted invoice data comprehensively.
        
        Args:
            extracted_data: Extracted invoice data from extraction service
            
        Returns:
            Validation result with status, errors, and recommendations
        """
        start_time = datetime.now()
        
        validation_result = {
            'is_valid': True,
            'requires_review': False,
            'confidence_score': 0.0,
            'validation_errors': [],
            'validation_warnings': [],
            'business_rule_violations': [],
            'data_quality_issues': [],
            'recommendations': []
        }
        
        try:
            # 1. Validate required fields
            self._validate_required_fields(extracted_data, validation_result)
            
            # 2. Validate confidence scores
            self._validate_confidence_scores(extracted_data, validation_result)
            
            # 3. Validate invoice metadata
            self._validate_invoice_metadata(extracted_data, validation_result)
            
            # 4. Validate company data
            self._validate_company_data(extracted_data, validation_result)
            
            # 5. Validate customer data
            self._validate_customer_data(extracted_data, validation_result)
            
            # 6. Validate financial data
            self._validate_financial_data(extracted_data, validation_result)
            
            # 7. Validate line items
            self._validate_line_items(extracted_data, validation_result)
            
            # 8. Apply business rules
            self._apply_business_rules(extracted_data, validation_result)
            
            # 9. Calculate overall validation score
            self._calculate_validation_score(validation_result)
            
            # 10. Determine if review is needed
            self._determine_review_requirement(validation_result)
            
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            validation_result['processing_time_ms'] = processing_time
            
            logger.info(f"Validation completed - Valid: {validation_result['is_valid']}, "
                       f"Review needed: {validation_result['requires_review']}")
            
            return validation_result
            
        except Exception as e:
            logger.error(f"Validation failed: {str(e)}")
            validation_result.update({
                'is_valid': False,
                'requires_review': True,
                'validation_errors': [f"Validation system error: {str(e)}"]
            })
            return validation_result
    
    def _validate_required_fields(self, data: Dict, result: Dict):
        """Validate that required fields are present."""
        for section, required_fields in self.validation_rules['required_fields'].items():
            section_data = data.get(section, {})
            
            for field in required_fields:
                if not section_data.get(field):
                    result['validation_errors'].append(
                        f"Missing required field: {section}.{field}"
                    )
                    result['is_valid'] = False
    
    def _validate_confidence_scores(self, data: Dict, result: Dict):
        """Validate confidence scores meet minimum thresholds."""
        thresholds = self.validation_rules['confidence_thresholds']
        
        for section, min_confidence in thresholds.items():
            section_data = data.get(section, {})
            confidence = section_data.get('confidence', 0.0)
            
            if confidence < min_confidence:
                result['validation_warnings'].append(
                    f"Low confidence in {section}: {confidence:.2f} < {min_confidence:.2f}"
                )
                result['requires_review'] = True
    
    def _validate_invoice_metadata(self, data: Dict, result: Dict):
        """Validate invoice metadata fields."""
        metadata = data.get('invoice_metadata', {})
        
        # Validate invoice number format
        invoice_number = metadata.get('invoice_number', '')
        if invoice_number:
            if len(invoice_number) < 3:
                result['data_quality_issues'].append(
                    "Invoice number appears too short"
                )
            
            # Check for suspicious characters
            if re.search(r'[^\w\-_]', invoice_number):
                result['data_quality_issues'].append(
                    "Invoice number contains unusual characters"
                )
        
        # Validate invoice date
        invoice_date = metadata.get('invoice_date')
        if invoice_date:
            try:
                if isinstance(invoice_date, str):
                    invoice_date = datetime.strptime(invoice_date, '%Y-%m-%d').date()
                
                # Check if date is too far in the future
                future_limit = date.today().replace(day=1)  # Beginning of current month
                max_future_days = self.validation_rules['business_rules']['future_invoice_date_days']
                
                if invoice_date > date.today():
                    days_future = (invoice_date - date.today()).days
                    if days_future > max_future_days:
                        result['business_rule_violations'].append(
                            f"Invoice date is {days_future} days in the future (max: {max_future_days})"
                        )
                
                # Check if date is too old (more than 2 years)
                if invoice_date < date.today().replace(year=date.today().year - 2):
                    result['validation_warnings'].append(
                        "Invoice date is more than 2 years old"
                    )
                    
            except (ValueError, TypeError) as e:
                result['validation_errors'].append(
                    f"Invalid invoice date format: {str(e)}"
                )
        
        # Validate due date
        due_date = metadata.get('due_date')
        invoice_date = metadata.get('invoice_date')
        
        if due_date and invoice_date:
            try:
                if isinstance(due_date, str):
                    due_date = datetime.strptime(due_date, '%Y-%m-%d').date()
                if isinstance(invoice_date, str):
                    invoice_date = datetime.strptime(invoice_date, '%Y-%m-%d').date()
                
                if due_date < invoice_date:
                    result['validation_errors'].append(
                        "Due date cannot be before invoice date"
                    )
                    
            except (ValueError, TypeError):
                result['validation_warnings'].append(
                    "Could not validate due date vs invoice date"
                )
    
    def _validate_company_data(self, data: Dict, result: Dict):
        """Validate company information."""
        company_data = data.get('company_data', {})
        
        # Validate company name
        name = company_data.get('name', '')
        if name:
            if len(name) < 2:
                result['data_quality_issues'].append(
                    "Company name appears too short"
                )
            
            # Check for common OCR errors
            if name.isupper() and len(name) > 10:
                result['validation_warnings'].append(
                    "Company name is all uppercase - possible OCR issue"
                )
        
        # Validate email format
        email = company_data.get('email', '')
        if email:
            email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
            if not email_pattern.match(email):
                result['data_quality_issues'].append(
                    f"Invalid email format: {email}"
                )
        
        # Validate phone format
        phone = company_data.get('phone', '')
        if phone:
            # Remove non-digits and check length
            digits_only = re.sub(r'\D', '', phone)
            if len(digits_only) < 7 or len(digits_only) > 15:
                result['data_quality_issues'].append(
                    f"Phone number appears invalid: {phone}"
                )
        
        # Validate address completeness
        address_fields = ['address_line1', 'city', 'postal_code']
        address_present = any(company_data.get(field) for field in address_fields)
        address_complete = all(company_data.get(field) for field in address_fields)
        
        if address_present and not address_complete:
            result['data_quality_issues'].append(
                "Company address is incomplete"
            )
    
    def _validate_customer_data(self, data: Dict, result: Dict):
        """Validate customer information."""
        customer_data = data.get('customer_data', {})
        
        # Similar validations as company data
        name = customer_data.get('name', '')
        if name and len(name) < 2:
            result['data_quality_issues'].append(
                "Customer name appears too short"
            )
        
        # Validate customer email
        email = customer_data.get('email', '')
        if email:
            email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
            if not email_pattern.match(email):
                result['data_quality_issues'].append(
                    f"Invalid customer email format: {email}"
                )
    
    def _validate_financial_data(self, data: Dict, result: Dict):
        """Validate financial amounts and calculations."""
        financial = data.get('financial_data', {})
        
        # Validate amounts are non-negative
        amount_fields = ['subtotal_amount', 'tax_amount', 'total_amount', 'discount_amount', 'shipping_amount']
        
        for field in amount_fields:
            amount = financial.get(field, 0.0)
            try:
                amount_decimal = Decimal(str(amount))
                if amount_decimal < 0:
                    result['validation_errors'].append(
                        f"{field} cannot be negative: {amount}"
                    )
            except (InvalidOperation, TypeError):
                result['validation_errors'].append(
                    f"Invalid amount format for {field}: {amount}"
                )
        
        # Validate total amount is within business rules
        total_amount = financial.get('total_amount', 0.0)
        min_amount = self.validation_rules['business_rules']['min_total_amount']
        max_amount = self.validation_rules['business_rules']['max_total_amount']
        
        if total_amount < min_amount:
            result['business_rule_violations'].append(
                f"Total amount too small: ${total_amount:.2f} < ${min_amount:.2f}"
            )
        
        if total_amount > max_amount:
            result['business_rule_violations'].append(
                f"Total amount too large: ${total_amount:.2f} > ${max_amount:.2f}"
            )
        
        # Validate tax rate
        tax_rate = financial.get('tax_rate', 0.0)
        max_tax_rate = self.validation_rules['business_rules']['max_tax_rate']
        
        if tax_rate > max_tax_rate:
            result['business_rule_violations'].append(
                f"Tax rate too high: {tax_rate:.2f}% > {max_tax_rate:.2f}%"
            )
        
        if tax_rate < 0:
            result['validation_errors'].append(
                f"Tax rate cannot be negative: {tax_rate:.2f}%"
            )
        
        # Validate calculation consistency
        self._validate_financial_calculations(financial, result)
        
        # Validate currency
        currency = financial.get('currency', '')
        valid_currencies = ['USD', 'EUR', 'GBP', 'CAD', 'AUD', 'JPY', 'INR']
        if currency and currency not in valid_currencies:
            result['validation_warnings'].append(
                f"Unusual currency detected: {currency}"
            )
    
    def _validate_financial_calculations(self, financial: Dict, result: Dict):
        """Validate financial calculation consistency."""
        try:
            subtotal = Decimal(str(financial.get('subtotal_amount', 0)))
            tax = Decimal(str(financial.get('tax_amount', 0)))
            discount = Decimal(str(financial.get('discount_amount', 0)))
            shipping = Decimal(str(financial.get('shipping_amount', 0)))
            total = Decimal(str(financial.get('total_amount', 0)))
            
            # Calculate expected total
            calculated_total = subtotal + tax + shipping - discount
            
            # Allow small rounding differences
            tolerance = Decimal('0.02')
            difference = abs(total - calculated_total)
            
            if difference > tolerance:
                result['data_quality_issues'].append(
                    f"Total amount calculation inconsistent: "
                    f"Expected ${calculated_total:.2f}, Found ${total:.2f}"
                )
                result['recommendations'].append(
                    "Review financial calculations for accuracy"
                )
            
            # Validate tax calculation if tax rate is provided
            tax_rate = financial.get('tax_rate', 0.0)
            if tax_rate > 0 and subtotal > 0:
                expected_tax = subtotal * (Decimal(str(tax_rate)) / 100)
                tax_difference = abs(tax - expected_tax)
                
                if tax_difference > tolerance:
                    result['data_quality_issues'].append(
                        f"Tax calculation inconsistent: "
                        f"Expected ${expected_tax:.2f}, Found ${tax:.2f}"
                    )
                    
        except (InvalidOperation, TypeError, ValueError) as e:
            result['validation_warnings'].append(
                f"Could not validate financial calculations: {str(e)}"
            )
    
    def _validate_line_items(self, data: Dict, result: Dict):
        """Validate line items data."""
        line_items = data.get('line_items', [])
        max_items = self.validation_rules['business_rules']['max_line_items']
        
        if len(line_items) > max_items:
            result['business_rule_violations'].append(
                f"Too many line items: {len(line_items)} > {max_items}"
            )
        
        # Validate individual line items
        for i, item in enumerate(line_items):
            self._validate_single_line_item(item, i + 1, result)
        
        # Validate line item totals vs invoice subtotal
        if line_items:
            line_items_total = sum(item.get('total_price', 0) for item in line_items)
            invoice_subtotal = data.get('financial_data', {}).get('subtotal_amount', 0)
            
            if invoice_subtotal > 0:
                tolerance = 0.02
                difference = abs(line_items_total - invoice_subtotal)
                
                if difference > tolerance:
                    result['data_quality_issues'].append(
                        f"Line items total (${line_items_total:.2f}) doesn't match "
                        f"invoice subtotal (${invoice_subtotal:.2f})"
                    )
    
    def _validate_single_line_item(self, item: Dict, line_number: int, result: Dict):
        """Validate a single line item."""
        # Validate required fields
        if not item.get('description'):
            result['data_quality_issues'].append(
                f"Line {line_number}: Missing description"
            )
        
        # Validate quantities
        quantity = item.get('quantity', 0)
        if quantity <= 0:
            result['validation_errors'].append(
                f"Line {line_number}: Invalid quantity: {quantity}"
            )
        
        # Validate prices
        unit_price = item.get('unit_price', 0)
        total_price = item.get('total_price', 0)
        
        if unit_price < 0:
            result['validation_errors'].append(
                f"Line {line_number}: Negative unit price: ${unit_price:.2f}"
            )
        
        if total_price < 0:
            result['validation_errors'].append(
                f"Line {line_number}: Negative total price: ${total_price:.2f}"
            )
        
        # Validate calculation
        if quantity > 0 and unit_price > 0:
            expected_total = quantity * unit_price
            tolerance = 0.02
            
            if abs(total_price - expected_total) > tolerance:
                result['data_quality_issues'].append(
                    f"Line {line_number}: Price calculation inconsistent: "
                    f"Expected ${expected_total:.2f}, Found ${total_price:.2f}"
                )
    
    def _apply_business_rules(self, data: Dict, result: Dict):
        """Apply additional business rules."""
        
        # Check for duplicate line items
        line_items = data.get('line_items', [])
        descriptions = [item.get('description', '').strip().lower() for item in line_items]
        
        seen_descriptions = set()
        for desc in descriptions:
            if desc and desc in seen_descriptions:
                result['validation_warnings'].append(
                    f"Possible duplicate line item: {desc}"
                )
            seen_descriptions.add(desc)
        
        # Check for reasonable payment terms
        payment_terms = data.get('financial_data', {}).get('payment_terms', '')
        if payment_terms:
            # Extract number of days from payment terms
            days_match = re.search(r'(\d+)', payment_terms)
            if days_match:
                days = int(days_match.group(1))
                if days > 365:
                    result['validation_warnings'].append(
                        f"Unusual payment terms: {payment_terms}"
                    )
    
    def _calculate_validation_score(self, result: Dict):
        """Calculate overall validation confidence score."""
        # Start with base score
        score = 1.0
        
        # Deduct for errors and issues
        score -= len(result['validation_errors']) * 0.2
        score -= len(result['business_rule_violations']) * 0.15
        score -= len(result['data_quality_issues']) * 0.1
        score -= len(result['validation_warnings']) * 0.05
        
        # Ensure score is between 0 and 1
        result['confidence_score'] = max(0.0, min(1.0, score))
    
    def _determine_review_requirement(self, result: Dict):
        """Determine if manual review is required."""
        
        # Always require review if there are errors or violations
        if result['validation_errors'] or result['business_rule_violations']:
            result['requires_review'] = True
            result['recommendations'].append(
                "Manual review required due to validation errors"
            )
        
        # Require review for low confidence
        if result['confidence_score'] < 0.7:
            result['requires_review'] = True
            result['recommendations'].append(
                "Manual review recommended due to low confidence score"
            )
        
        # Require review for many data quality issues
        if len(result['data_quality_issues']) >= 3:
            result['requires_review'] = True
            result['recommendations'].append(
                "Manual review recommended due to data quality concerns"
            )
        
        # Add specific recommendations
        if not result['requires_review']:
            result['recommendations'].append(
                "Invoice data appears valid and ready for processing"
            )
        
        return result['requires_review']