"""
Company model for vendor/supplier information
"""

from datetime import datetime, timezone
import uuid

from app import db

class Company(db.Model):
    """Company/Vendor model for invoice issuing entities."""
    
    __tablename__ = 'companies'
    
    # Primary key
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Basic company information
    name = db.Column(db.String(255), nullable=False, index=True)
    legal_name = db.Column(db.String(255))  # Official legal name if different
    registration_number = db.Column(db.String(100))  # Business registration number
    tax_id = db.Column(db.String(100), index=True)  # Tax identification number
    
    # Contact information
    email = db.Column(db.String(255))
    phone = db.Column(db.String(50))
    website = db.Column(db.String(255))
    
    # Address information
    address_line1 = db.Column(db.String(255))
    address_line2 = db.Column(db.String(255))
    city = db.Column(db.String(100))
    state_province = db.Column(db.String(100))
    postal_code = db.Column(db.String(20))
    country = db.Column(db.String(100))
    
    # Business information
    industry = db.Column(db.String(100))
    company_size = db.Column(db.String(50))  # small, medium, large, enterprise
    currency = db.Column(db.String(3), default='USD')  # ISO currency code
    
    # Multi-tenant support
    tenant_id = db.Column(db.String(100), nullable=False, default='default', index=True)
    
    # Data quality and confidence
    confidence_score = db.Column(db.Float, default=0.0)  # OCR extraction confidence
    is_verified = db.Column(db.Boolean, default=False)  # Manually verified
    verification_source = db.Column(db.String(100))  # How was it verified
    
    # Usage statistics
    invoice_count = db.Column(db.Integer, default=0, nullable=False)
    total_amount = db.Column(db.Numeric(15, 2), default=0.00)
    last_invoice_date = db.Column(db.Date)
    
    # Status and flags
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_preferred_vendor = db.Column(db.Boolean, default=False)
    payment_terms_days = db.Column(db.Integer)  # Default payment terms
    
    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc), 
                          onupdate=datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    invoices = db.relationship('InvoiceHeader', backref='company', lazy='dynamic')
    
    # Indexes for performance
    __table_args__ = (
        db.Index('idx_company_name_tenant', 'name', 'tenant_id'),
        db.Index('idx_company_tax_id', 'tax_id'),
        db.Index('idx_company_tenant_active', 'tenant_id', 'is_active'),
        db.Index('idx_company_country_city', 'country', 'city'),
    )
    
    def update_statistics(self):
        """Update company statistics based on invoices."""
        from app.models.invoice import InvoiceHeader
        from sqlalchemy import func
        
        stats = db.session.query(
            func.count(InvoiceHeader.id).label('count'),
            func.sum(InvoiceHeader.total_amount).label('total'),
            func.max(InvoiceHeader.invoice_date).label('last_date')
        ).filter(
            InvoiceHeader.company_id == self.id
        ).first()
        
        self.invoice_count = stats.count or 0
        self.total_amount = stats.total or 0.00
        self.last_invoice_date = stats.last_date
    
    @property
    def full_address(self):
        """Get formatted full address."""
        address_parts = [
            self.address_line1,
            self.address_line2,
            self.city,
            self.state_province,
            self.postal_code,
            self.country
        ]
        return ', '.join([part for part in address_parts if part])
    
    @property
    def display_name(self):
        """Get display name (legal name if available, otherwise name)."""
        return self.legal_name or self.name
    
    def is_duplicate_of(self, other_company):
        """Check if this company is likely a duplicate of another."""
        if not other_company:
            return False
        
        # Check for exact name match
        if self.name.lower() == other_company.name.lower():
            return True
        
        # Check for tax ID match
        if self.tax_id and other_company.tax_id:
            if self.tax_id == other_company.tax_id:
                return True
        
        # Check for similar name and same address
        name_similarity = self._calculate_name_similarity(other_company.name)
        if name_similarity > 0.8 and self._same_address(other_company):
            return True
        
        return False
    
    def _calculate_name_similarity(self, other_name):
        """Calculate similarity between company names."""
        # Simple similarity check - in production, use more sophisticated algorithms
        name1 = self.name.lower().strip()
        name2 = other_name.lower().strip()
        
        if name1 == name2:
            return 1.0
        
        # Check if one name contains the other
        if name1 in name2 or name2 in name1:
            return 0.8
        
        # Basic word overlap check
        words1 = set(name1.split())
        words2 = set(name2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union)
    
    def _same_address(self, other_company):
        """Check if companies have the same address."""
        return (
            self.address_line1 == other_company.address_line1 and
            self.city == other_company.city and
            self.postal_code == other_company.postal_code
        )
    
    @classmethod
    def find_similar(cls, name, tax_id=None, tenant_id='default', limit=5):
        """Find similar companies to avoid duplicates."""
        query = cls.query.filter(
            cls.tenant_id == tenant_id,
            cls.is_active == True
        )
        
        # First try exact tax ID match
        if tax_id:
            exact_match = query.filter(cls.tax_id == tax_id).first()
            if exact_match:
                return [exact_match]
        
        # Then try name similarity
        similar_companies = query.filter(
            cls.name.ilike(f'%{name}%')
        ).limit(limit).all()
        
        return similar_companies
    
    def to_dict(self, include_stats=False):
        """Convert company to dictionary for API responses."""
        data = {
            'id': self.id,
            'name': self.name,
            'legal_name': self.legal_name,
            'display_name': self.display_name,
            'registration_number': self.registration_number,
            'tax_id': self.tax_id,
            'email': self.email,
            'phone': self.phone,
            'website': self.website,
            'address': {
                'line1': self.address_line1,
                'line2': self.address_line2,
                'city': self.city,
                'state_province': self.state_province,
                'postal_code': self.postal_code,
                'country': self.country,
                'full_address': self.full_address
            },
            'industry': self.industry,
            'company_size': self.company_size,
            'currency': self.currency,
            'tenant_id': self.tenant_id,
            'confidence_score': self.confidence_score,
            'is_verified': self.is_verified,
            'verification_source': self.verification_source,
            'is_active': self.is_active,
            'is_preferred_vendor': self.is_preferred_vendor,
            'payment_terms_days': self.payment_terms_days,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
        
        if include_stats:
            data.update({
                'statistics': {
                    'invoice_count': self.invoice_count,
                    'total_amount': float(self.total_amount) if self.total_amount else 0.0,
                    'last_invoice_date': self.last_invoice_date.isoformat() if self.last_invoice_date else None
                }
            })
        
        return data
    
    def __repr__(self):
        return f'<Company {self.name} ({self.tenant_id})>'