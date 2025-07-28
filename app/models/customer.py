"""
Customer model for billing and customer information
"""

from datetime import datetime, timezone
import uuid

from app import db

class Customer(db.Model):
    """Customer/Client model for invoice billing entities."""
    
    __tablename__ = 'customers'
    
    # Primary key
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Basic customer information
    name = db.Column(db.String(255), nullable=False, index=True)
    company_name = db.Column(db.String(255))  # If customer is a business
    customer_type = db.Column(db.String(50), default='individual')  # individual, business
    
    # Contact information
    email = db.Column(db.String(255), index=True)
    phone = db.Column(db.String(50))
    mobile = db.Column(db.String(50))
    
    # Address information
    billing_address_line1 = db.Column(db.String(255))
    billing_address_line2 = db.Column(db.String(255))
    billing_city = db.Column(db.String(100))
    billing_state_province = db.Column(db.String(100))
    billing_postal_code = db.Column(db.String(20))
    billing_country = db.Column(db.String(100))
    
    # Shipping address (if different from billing)
    shipping_address_line1 = db.Column(db.String(255))
    shipping_address_line2 = db.Column(db.String(255))
    shipping_city = db.Column(db.String(100))
    shipping_state_province = db.Column(db.String(100))
    shipping_postal_code = db.Column(db.String(20))
    shipping_country = db.Column(db.String(100))
    
    # Business information (for business customers)
    tax_id = db.Column(db.String(100), index=True)
    registration_number = db.Column(db.String(100))
    website = db.Column(db.String(255))
    
    # Multi-tenant support
    tenant_id = db.Column(db.String(100), nullable=False, default='default', index=True)
    
    # Data quality and confidence
    confidence_score = db.Column(db.Float, default=0.0)  # OCR extraction confidence
    is_verified = db.Column(db.Boolean, default=False)  # Manually verified
    verification_source = db.Column(db.String(100))  # How was it verified
    
    # Customer relationship management
    customer_since = db.Column(db.Date)
    customer_segment = db.Column(db.String(50))  # premium, standard, basic
    credit_limit = db.Column(db.Numeric(15, 2))
    payment_terms_days = db.Column(db.Integer, default=30)
    
    # Usage statistics
    invoice_count = db.Column(db.Integer, default=0, nullable=False)
    total_billed = db.Column(db.Numeric(15, 2), default=0.00)
    total_paid = db.Column(db.Numeric(15, 2), default=0.00)
    last_invoice_date = db.Column(db.Date)
    last_payment_date = db.Column(db.Date)
    
    # Status and flags
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_vip = db.Column(db.Boolean, default=False)
    allow_credit = db.Column(db.Boolean, default=True)
    
    # Communication preferences
    preferred_contact_method = db.Column(db.String(50), default='email')  # email, phone, mail
    send_invoice_copy = db.Column(db.Boolean, default=True)
    marketing_consent = db.Column(db.Boolean, default=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc), 
                          onupdate=datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    invoices = db.relationship('InvoiceHeader', backref='customer', lazy='dynamic')
    
    # Indexes for performance
    __table_args__ = (
        db.Index('idx_customer_name_tenant', 'name', 'tenant_id'),
        db.Index('idx_customer_email_tenant', 'email', 'tenant_id'),
        db.Index('idx_customer_tax_id', 'tax_id'),
        db.Index('idx_customer_tenant_active', 'tenant_id', 'is_active'),
        db.Index('idx_customer_type_segment', 'customer_type', 'customer_segment'),
    )
    
    def update_statistics(self):
        """Update customer statistics based on invoices."""
        from app.models.invoice import InvoiceHeader
        from sqlalchemy import func
        
        stats = db.session.query(
            func.count(InvoiceHeader.id).label('count'),
            func.sum(InvoiceHeader.total_amount).label('total_billed'),
            func.sum(InvoiceHeader.paid_amount).label('total_paid'),
            func.max(InvoiceHeader.invoice_date).label('last_invoice'),
            func.max(InvoiceHeader.payment_date).label('last_payment')
        ).filter(
            InvoiceHeader.customer_id == self.id
        ).first()
        
        self.invoice_count = stats.count or 0
        self.total_billed = stats.total_billed or 0.00
        self.total_paid = stats.total_paid or 0.00
        self.last_invoice_date = stats.last_invoice
        self.last_payment_date = stats.last_payment
    
    @property
    def display_name(self):
        """Get display name (company name if business, otherwise personal name)."""
        if self.customer_type == 'business' and self.company_name:
            return self.company_name
        return self.name
    
    @property
    def outstanding_balance(self):
        """Calculate outstanding balance."""
        return (self.total_billed or 0) - (self.total_paid or 0)
    
    @property
    def full_billing_address(self):
        """Get formatted billing address."""
        address_parts = [
            self.billing_address_line1,
            self.billing_address_line2,
            self.billing_city,
            self.billing_state_province,
            self.billing_postal_code,
            self.billing_country
        ]
        return ', '.join([part for part in address_parts if part])
    
    @property
    def full_shipping_address(self):
        """Get formatted shipping address."""
        address_parts = [
            self.shipping_address_line1,
            self.shipping_address_line2,
            self.shipping_city,
            self.shipping_state_province,
            self.shipping_postal_code,
            self.shipping_country
        ]
        return ', '.join([part for part in address_parts if part])
    
    @property
    def has_different_shipping_address(self):
        """Check if shipping address differs from billing address."""
        return any([
            self.shipping_address_line1,
            self.shipping_address_line2,
            self.shipping_city,
            self.shipping_state_province,
            self.shipping_postal_code,
            self.shipping_country
        ])
    
    def is_duplicate_of(self, other_customer):
        """Check if this customer is likely a duplicate of another."""
        if not other_customer:
            return False
        
        # Check for exact email match
        if self.email and other_customer.email:
            if self.email.lower() == other_customer.email.lower():
                return True
        
        # Check for tax ID match (for business customers)
        if self.tax_id and other_customer.tax_id:
            if self.tax_id == other_customer.tax_id:
                return True
        
        # Check for name and address similarity
        name_similarity = self._calculate_name_similarity(other_customer.name)
        if name_similarity > 0.9 and self._same_billing_address(other_customer):
            return True
        
        return False
    
    def _calculate_name_similarity(self, other_name):
        """Calculate similarity between customer names."""
        if not other_name:
            return 0.0
        
        name1 = self.name.lower().strip()
        name2 = other_name.lower().strip()
        
        if name1 == name2:
            return 1.0
        
        # Simple word overlap for name similarity
        words1 = set(name1.split())
        words2 = set(name2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union)
    
    def _same_billing_address(self, other_customer):
        """Check if customers have the same billing address."""
        return (
            self.billing_address_line1 == other_customer.billing_address_line1 and
            self.billing_city == other_customer.billing_city and
            self.billing_postal_code == other_customer.billing_postal_code
        )
    
    @classmethod
    def find_similar(cls, name=None, email=None, tax_id=None, tenant_id='default', limit=5):
        """Find similar customers to avoid duplicates."""
        query = cls.query.filter(
            cls.tenant_id == tenant_id,
            cls.is_active == True
        )
        
        # First try exact email match
        if email:
            exact_match = query.filter(cls.email.ilike(email)).first()
            if exact_match:
                return [exact_match]
        
        # Then try tax ID match
        if tax_id:
            exact_match = query.filter(cls.tax_id == tax_id).first()
            if exact_match:
                return [exact_match]
        
        # Finally try name similarity
        if name:
            similar_customers = query.filter(
                cls.name.ilike(f'%{name}%')
            ).limit(limit).all()
            return similar_customers
        
        return []
    
    def to_dict(self, include_stats=False):
        """Convert customer to dictionary for API responses."""
        data = {
            'id': self.id,
            'name': self.name,
            'company_name': self.company_name,
            'display_name': self.display_name,
            'customer_type': self.customer_type,
            'email': self.email,
            'phone': self.phone,
            'mobile': self.mobile,
            'billing_address': {
                'line1': self.billing_address_line1,
                'line2': self.billing_address_line2,
                'city': self.billing_city,
                'state_province': self.billing_state_province,
                'postal_code': self.billing_postal_code,
                'country': self.billing_country,
                'full_address': self.full_billing_address
            },
            'tax_id': self.tax_id,
            'registration_number': self.registration_number,
            'website': self.website,
            'tenant_id': self.tenant_id,
            'confidence_score': self.confidence_score,
            'is_verified': self.is_verified,
            'verification_source': self.verification_source,
            'customer_since': self.customer_since.isoformat() if self.customer_since else None,
            'customer_segment': self.customer_segment,
            'credit_limit': float(self.credit_limit) if self.credit_limit else None,
            'payment_terms_days': self.payment_terms_days,
            'is_active': self.is_active,
            'is_vip': self.is_vip,
            'allow_credit': self.allow_credit,
            'preferred_contact_method': self.preferred_contact_method,
            'send_invoice_copy': self.send_invoice_copy,
            'marketing_consent': self.marketing_consent,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
        
        if self.has_different_shipping_address:
            data['shipping_address'] = {
                'line1': self.shipping_address_line1,
                'line2': self.shipping_address_line2,
                'city': self.shipping_city,
                'state_province': self.shipping_state_province,
                'postal_code': self.shipping_postal_code,
                'country': self.shipping_country,
                'full_address': self.full_shipping_address
            }
        
        if include_stats:
            data.update({
                'statistics': {
                    'invoice_count': self.invoice_count,
                    'total_billed': float(self.total_billed) if self.total_billed else 0.0,
                    'total_paid': float(self.total_paid) if self.total_paid else 0.0,
                    'outstanding_balance': float(self.outstanding_balance),
                    'last_invoice_date': self.last_invoice_date.isoformat() if self.last_invoice_date else None,
                    'last_payment_date': self.last_payment_date.isoformat() if self.last_payment_date else None
                }
            })
        
        return data
    
    def __repr__(self):
        return f'<Customer {self.display_name} ({self.tenant_id})>'