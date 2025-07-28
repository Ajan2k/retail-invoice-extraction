"""
Invoice models for invoice data and processing tracking
"""

from datetime import datetime, timezone, date
from decimal import Decimal
import uuid
import json

from app import db

class InvoiceHeader(db.Model):
    """Main invoice header model containing invoice metadata and totals."""
    
    __tablename__ = 'invoice_headers'
    
    # Primary key
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Invoice identification
    invoice_number = db.Column(db.String(100), nullable=False, index=True)
    invoice_date = db.Column(db.Date, nullable=False, index=True)
    due_date = db.Column(db.Date)
    po_number = db.Column(db.String(100))  # Purchase order number
    
    # Foreign keys
    company_id = db.Column(db.String(36), db.ForeignKey('companies.id'), nullable=False, index=True)
    customer_id = db.Column(db.String(36), db.ForeignKey('customers.id'), index=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)
    
    # Multi-tenant support
    tenant_id = db.Column(db.String(100), nullable=False, default='default', index=True)
    
    # Financial information
    currency = db.Column(db.String(3), default='USD', nullable=False)
    subtotal_amount = db.Column(db.Numeric(15, 2), default=0.00, nullable=False)
    tax_amount = db.Column(db.Numeric(15, 2), default=0.00, nullable=False)
    tax_rate = db.Column(db.Float, default=0.0)  # Tax percentage
    discount_amount = db.Column(db.Numeric(15, 2), default=0.00)
    shipping_amount = db.Column(db.Numeric(15, 2), default=0.00)
    total_amount = db.Column(db.Numeric(15, 2), default=0.00, nullable=False, index=True)
    
    # Payment information
    payment_terms = db.Column(db.String(100))  # e.g., "Net 30", "Due on receipt"
    payment_method = db.Column(db.String(50))  # cash, check, credit_card, bank_transfer
    payment_status = db.Column(db.String(50), default='unpaid', nullable=False, index=True)  # unpaid, partial, paid, overdue
    paid_amount = db.Column(db.Numeric(15, 2), default=0.00)
    payment_date = db.Column(db.Date)
    payment_reference = db.Column(db.String(100))
    
    # Invoice type and category
    invoice_type = db.Column(db.String(50), default='standard')  # standard, proforma, credit_note, debit_note
    invoice_category = db.Column(db.String(100))  # goods, services, mixed
    
    # Processing information
    processing_status = db.Column(db.String(50), default='pending', nullable=False, index=True)  # pending, processing, completed, failed
    extraction_confidence = db.Column(db.Float, default=0.0)  # Overall extraction confidence
    requires_review = db.Column(db.Boolean, default=False, nullable=False)
    reviewed_by = db.Column(db.String(36), db.ForeignKey('users.id'))
    reviewed_at = db.Column(db.DateTime(timezone=True))
    
    # File information
    original_filename = db.Column(db.String(255))
    file_path = db.Column(db.String(500))
    file_size = db.Column(db.Integer)  # File size in bytes
    file_hash = db.Column(db.String(64))  # SHA-256 hash for deduplication
    
    # OCR and extraction metadata
    ocr_text = db.Column(db.Text)  # Full OCR extracted text
    extraction_metadata = db.Column(db.Text)  # JSON metadata about extraction process
    
    # Business logic fields
    is_duplicate = db.Column(db.Boolean, default=False)
    duplicate_of = db.Column(db.String(36), db.ForeignKey('invoice_headers.id'))
    line_items_count = db.Column(db.Integer, default=0)
    
    # Compliance and audit
    retention_until = db.Column(db.Date)  # Data retention date
    is_archived = db.Column(db.Boolean, default=False, nullable=False)
    archived_at = db.Column(db.DateTime(timezone=True))
    
    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc), 
                          onupdate=datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    line_items = db.relationship('LineItem', backref='invoice', lazy='dynamic', cascade='all, delete-orphan')
    processing_logs = db.relationship('ProcessingLog', backref='invoice', lazy='dynamic', cascade='all, delete-orphan')
    duplicates = db.relationship('InvoiceHeader', remote_side=[id], backref='original_invoice')
    reviewer = db.relationship('User', foreign_keys=[reviewed_by], backref='reviewed_invoices')
    
    # Indexes for performance
    __table_args__ = (
        db.Index('idx_invoice_number_tenant', 'invoice_number', 'tenant_id'),
        db.Index('idx_invoice_date_status', 'invoice_date', 'processing_status'),
        db.Index('idx_invoice_company_date', 'company_id', 'invoice_date'),
        db.Index('idx_invoice_customer_date', 'customer_id', 'invoice_date'),
        db.Index('idx_invoice_payment_status', 'payment_status', 'due_date'),
        db.Index('idx_invoice_tenant_active', 'tenant_id', 'is_archived'),
        db.Index('idx_invoice_file_hash', 'file_hash'),
        # Unique constraint for invoice number per company per tenant
        db.UniqueConstraint('invoice_number', 'company_id', 'tenant_id', name='uq_invoice_number_company_tenant'),
    )
    
    def __init__(self, **kwargs):
        super(InvoiceHeader, self).__init__(**kwargs)
        if not self.retention_until:
            from datetime import timedelta
            # Set retention period based on configuration (default 7 years)
            self.retention_until = (self.invoice_date or date.today()) + timedelta(days=2555)
    
    def calculate_totals(self):
        """Calculate invoice totals from line items."""
        if not self.line_items:
            return
        
        self.subtotal_amount = sum(item.total_price for item in self.line_items)
        
        # Calculate tax if tax rate is provided
        if self.tax_rate and self.tax_rate > 0:
            self.tax_amount = self.subtotal_amount * (Decimal(str(self.tax_rate)) / 100)
        
        # Calculate total
        self.total_amount = (
            self.subtotal_amount + 
            (self.tax_amount or 0) + 
            (self.shipping_amount or 0) - 
            (self.discount_amount or 0)
        )
        
        # Update line items count
        self.line_items_count = self.line_items.count()
    
    @property
    def outstanding_amount(self):
        """Calculate outstanding amount to be paid."""
        return (self.total_amount or 0) - (self.paid_amount or 0)
    
    @property
    def is_overdue(self):
        """Check if invoice is overdue."""
        if not self.due_date or self.payment_status == 'paid':
            return False
        return date.today() > self.due_date
    
    @property
    def days_overdue(self):
        """Calculate days overdue."""
        if not self.is_overdue:
            return 0
        return (date.today() - self.due_date).days
    
    @property
    def is_fully_paid(self):
        """Check if invoice is fully paid."""
        return self.payment_status == 'paid' and self.outstanding_amount <= 0
    
    def update_payment_status(self):
        """Update payment status based on paid amount."""
        if not self.total_amount or self.total_amount <= 0:
            self.payment_status = 'paid'
        elif not self.paid_amount or self.paid_amount <= 0:
            self.payment_status = 'overdue' if self.is_overdue else 'unpaid'
        elif self.paid_amount >= self.total_amount:
            self.payment_status = 'paid'
        else:
            self.payment_status = 'partial'
    
    def mark_as_duplicate(self, original_invoice_id):
        """Mark this invoice as a duplicate of another."""
        self.is_duplicate = True
        self.duplicate_of = original_invoice_id
        self.processing_status = 'completed'
        self.requires_review = True
    
    def set_extraction_metadata(self, metadata_dict):
        """Set extraction metadata as JSON."""
        self.extraction_metadata = json.dumps(metadata_dict) if metadata_dict else None
    
    def get_extraction_metadata(self):
        """Get extraction metadata as dictionary."""
        if not self.extraction_metadata:
            return {}
        try:
            return json.loads(self.extraction_metadata)
        except (json.JSONDecodeError, TypeError):
            return {}
    
    @classmethod
    def find_potential_duplicates(cls, file_hash, invoice_number, company_id, tenant_id):
        """Find potential duplicate invoices."""
        # First check by file hash
        if file_hash:
            file_duplicate = cls.query.filter(
                cls.file_hash == file_hash,
                cls.tenant_id == tenant_id,
                cls.is_archived == False
            ).first()
            if file_duplicate:
                return file_duplicate
        
        # Then check by invoice number and company
        invoice_duplicate = cls.query.filter(
            cls.invoice_number == invoice_number,
            cls.company_id == company_id,
            cls.tenant_id == tenant_id,
            cls.is_archived == False
        ).first()
        
        return invoice_duplicate
    
    def to_dict(self, include_line_items=False, include_logs=False):
        """Convert invoice to dictionary for API responses."""
        data = {
            'id': self.id,
            'invoice_number': self.invoice_number,
            'invoice_date': self.invoice_date.isoformat() if self.invoice_date else None,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'po_number': self.po_number,
            'company_id': self.company_id,
            'customer_id': self.customer_id,
            'user_id': self.user_id,
            'tenant_id': self.tenant_id,
            'currency': self.currency,
            'amounts': {
                'subtotal': float(self.subtotal_amount) if self.subtotal_amount else 0.0,
                'tax': float(self.tax_amount) if self.tax_amount else 0.0,
                'tax_rate': self.tax_rate,
                'discount': float(self.discount_amount) if self.discount_amount else 0.0,
                'shipping': float(self.shipping_amount) if self.shipping_amount else 0.0,
                'total': float(self.total_amount) if self.total_amount else 0.0,
                'paid': float(self.paid_amount) if self.paid_amount else 0.0,
                'outstanding': float(self.outstanding_amount)
            },
            'payment': {
                'terms': self.payment_terms,
                'method': self.payment_method,
                'status': self.payment_status,
                'date': self.payment_date.isoformat() if self.payment_date else None,
                'reference': self.payment_reference
            },
            'invoice_type': self.invoice_type,
            'invoice_category': self.invoice_category,
            'processing': {
                'status': self.processing_status,
                'confidence': self.extraction_confidence,
                'requires_review': self.requires_review,
                'reviewed_by': self.reviewed_by,
                'reviewed_at': self.reviewed_at.isoformat() if self.reviewed_at else None
            },
            'file_info': {
                'original_filename': self.original_filename,
                'file_size': self.file_size,
                'file_hash': self.file_hash
            },
            'flags': {
                'is_duplicate': self.is_duplicate,
                'duplicate_of': self.duplicate_of,
                'is_overdue': self.is_overdue,
                'days_overdue': self.days_overdue,
                'is_fully_paid': self.is_fully_paid,
                'is_archived': self.is_archived
            },
            'line_items_count': self.line_items_count,
            'retention_until': self.retention_until.isoformat() if self.retention_until else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
        
        if include_line_items:
            data['line_items'] = [item.to_dict() for item in self.line_items]
        
        if include_logs:
            data['processing_logs'] = [log.to_dict() for log in self.processing_logs.order_by(ProcessingLog.created_at.desc()).limit(10)]
        
        return data
    
    def __repr__(self):
        return f'<Invoice {self.invoice_number} - {self.company.name if self.company else "No Company"} ({self.tenant_id})>'


class LineItem(db.Model):
    """Individual invoice line items."""
    
    __tablename__ = 'line_items'
    
    # Primary key
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Foreign key
    invoice_id = db.Column(db.String(36), db.ForeignKey('invoice_headers.id'), nullable=False, index=True)
    
    # Line item information
    line_number = db.Column(db.Integer, nullable=False)  # Order in invoice
    description = db.Column(db.Text, nullable=False)
    item_code = db.Column(db.String(100))  # SKU or product code
    
    # Quantity and pricing
    quantity = db.Column(db.Numeric(10, 3), default=1.000, nullable=False)
    unit_of_measure = db.Column(db.String(20), default='each')  # each, kg, lb, hour, etc.
    unit_price = db.Column(db.Numeric(15, 4), default=0.0000, nullable=False)
    total_price = db.Column(db.Numeric(15, 2), default=0.00, nullable=False)
    
    # Tax and discounts for this line item
    tax_rate = db.Column(db.Float, default=0.0)
    tax_amount = db.Column(db.Numeric(15, 2), default=0.00)
    discount_rate = db.Column(db.Float, default=0.0)
    discount_amount = db.Column(db.Numeric(15, 2), default=0.00)
    
    # Product categorization
    category = db.Column(db.String(100))  # Product category
    product_type = db.Column(db.String(50), default='product')  # product, service, other
    
    # Data quality
    confidence_score = db.Column(db.Float, default=0.0)  # OCR extraction confidence
    
    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc), 
                          onupdate=datetime.now(timezone.utc), nullable=False)
    
    # Indexes for performance
    __table_args__ = (
        db.Index('idx_lineitem_invoice_line', 'invoice_id', 'line_number'),
        db.Index('idx_lineitem_item_code', 'item_code'),
        db.Index('idx_lineitem_category', 'category'),
    )
    
    def calculate_total(self):
        """Calculate total price including tax and discount."""
        base_total = self.quantity * self.unit_price
        
        # Apply discount
        if self.discount_rate and self.discount_rate > 0:
            self.discount_amount = base_total * (Decimal(str(self.discount_rate)) / 100)
        
        # Calculate after discount
        after_discount = base_total - (self.discount_amount or 0)
        
        # Apply tax
        if self.tax_rate and self.tax_rate > 0:
            self.tax_amount = after_discount * (Decimal(str(self.tax_rate)) / 100)
        
        # Final total
        self.total_price = after_discount + (self.tax_amount or 0)
    
    def to_dict(self):
        """Convert line item to dictionary for API responses."""
        return {
            'id': self.id,
            'invoice_id': self.invoice_id,
            'line_number': self.line_number,
            'description': self.description,
            'item_code': self.item_code,
            'quantity': float(self.quantity) if self.quantity else 0.0,
            'unit_of_measure': self.unit_of_measure,
            'unit_price': float(self.unit_price) if self.unit_price else 0.0,
            'total_price': float(self.total_price) if self.total_price else 0.0,
            'tax_rate': self.tax_rate,
            'tax_amount': float(self.tax_amount) if self.tax_amount else 0.0,
            'discount_rate': self.discount_rate,
            'discount_amount': float(self.discount_amount) if self.discount_amount else 0.0,
            'category': self.category,
            'product_type': self.product_type,
            'confidence_score': self.confidence_score,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    def __repr__(self):
        return f'<LineItem {self.line_number}: {self.description[:50]}... ({self.total_price})>'


class ProcessingLog(db.Model):
    """Audit trail and processing logs for invoices."""
    
    __tablename__ = 'processing_logs'
    
    # Primary key
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Foreign keys
    invoice_id = db.Column(db.String(36), db.ForeignKey('invoice_headers.id'), nullable=False, index=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), index=True)
    
    # Log information
    log_level = db.Column(db.String(20), default='INFO', nullable=False)  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    process_stage = db.Column(db.String(50), nullable=False, index=True)  # upload, ocr, extraction, validation, completion
    message = db.Column(db.Text, nullable=False)
    
    # Processing details
    processing_time_ms = db.Column(db.Integer)  # Time taken in milliseconds
    confidence_score = db.Column(db.Float)  # Confidence at this stage
    
    # Error information
    error_code = db.Column(db.String(50))
    error_details = db.Column(db.Text)  # Detailed error information
    stack_trace = db.Column(db.Text)  # For debugging
    
    # Metadata
    metadata = db.Column(db.Text)  # JSON metadata for this processing stage
    ip_address = db.Column(db.String(45))  # Client IP address
    user_agent = db.Column(db.String(500))  # Client user agent
    
    # Timestamp
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc), nullable=False, index=True)
    
    # Indexes for performance
    __table_args__ = (
        db.Index('idx_log_invoice_stage', 'invoice_id', 'process_stage'),
        db.Index('idx_log_level_created', 'log_level', 'created_at'),
        db.Index('idx_log_user_created', 'user_id', 'created_at'),
    )
    
    @classmethod
    def log(cls, invoice_id, process_stage, message, log_level='INFO', user_id=None, 
            processing_time_ms=None, confidence_score=None, error_code=None, 
            error_details=None, metadata=None, ip_address=None, user_agent=None):
        """Create a new processing log entry."""
        
        log_entry = cls(
            invoice_id=invoice_id,
            user_id=user_id,
            log_level=log_level,
            process_stage=process_stage,
            message=message,
            processing_time_ms=processing_time_ms,
            confidence_score=confidence_score,
            error_code=error_code,
            error_details=error_details,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        if metadata:
            log_entry.set_metadata(metadata)
        
        db.session.add(log_entry)
        return log_entry
    
    def set_metadata(self, metadata_dict):
        """Set metadata as JSON."""
        self.metadata = json.dumps(metadata_dict) if metadata_dict else None
    
    def get_metadata(self):
        """Get metadata as dictionary."""
        if not self.metadata:
            return {}
        try:
            return json.loads(self.metadata)
        except (json.JSONDecodeError, TypeError):
            return {}
    
    def to_dict(self):
        """Convert processing log to dictionary for API responses."""
        return {
            'id': self.id,
            'invoice_id': self.invoice_id,
            'user_id': self.user_id,
            'log_level': self.log_level,
            'process_stage': self.process_stage,
            'message': self.message,
            'processing_time_ms': self.processing_time_ms,
            'confidence_score': self.confidence_score,
            'error_code': self.error_code,
            'error_details': self.error_details,
            'metadata': self.get_metadata(),
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'created_at': self.created_at.isoformat()
        }
    
    def __repr__(self):
        return f'<ProcessingLog {self.process_stage} - {self.log_level}: {self.message[:50]}...>'