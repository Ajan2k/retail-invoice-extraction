"""
User model for authentication and multi-tenant support
"""

from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import uuid

from app import db

class User(db.Model):
    """User model for authentication and authorization."""
    
    __tablename__ = 'users'
    
    # Primary key
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Authentication fields
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    
    # Profile information
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    
    # Multi-tenant support
    tenant_id = db.Column(db.String(100), nullable=False, default='default', index=True)
    
    # Authorization
    role = db.Column(db.String(50), nullable=False, default='user')  # user, admin, super_admin
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    
    # Security tracking
    last_login_at = db.Column(db.DateTime(timezone=True))
    last_login_ip = db.Column(db.String(45))  # IPv6 support
    failed_login_attempts = db.Column(db.Integer, default=0, nullable=False)
    locked_until = db.Column(db.DateTime(timezone=True))
    
    # API access
    api_key = db.Column(db.String(64), unique=True, index=True)
    api_requests_count = db.Column(db.Integer, default=0, nullable=False)
    api_rate_limit = db.Column(db.Integer, default=1000, nullable=False)  # requests per hour
    
    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc), 
                          onupdate=datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    invoices = db.relationship('InvoiceHeader', backref='user', lazy='dynamic')
    processing_logs = db.relationship('ProcessingLog', backref='user', lazy='dynamic')
    
    # Indexes for performance
    __table_args__ = (
        db.Index('idx_user_tenant_active', 'tenant_id', 'is_active'),
        db.Index('idx_user_email_tenant', 'email', 'tenant_id'),
        db.Index('idx_user_api_key', 'api_key'),
    )
    
    def __init__(self, **kwargs):
        super(User, self).__init__(**kwargs)
        if not self.api_key:
            self.generate_api_key()
    
    def set_password(self, password):
        """Set password hash."""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check password against hash."""
        return check_password_hash(self.password_hash, password)
    
    def generate_api_key(self):
        """Generate a new API key."""
        import secrets
        self.api_key = secrets.token_urlsafe(32)
    
    def reset_api_key(self):
        """Reset API key (revoke current access)."""
        self.generate_api_key()
        self.api_requests_count = 0
    
    def increment_api_usage(self):
        """Increment API usage counter."""
        self.api_requests_count += 1
    
    def is_rate_limited(self):
        """Check if user has exceeded rate limit."""
        # This is a simple counter - in production, use time-based windows
        return self.api_requests_count >= self.api_rate_limit
    
    def is_account_locked(self):
        """Check if account is locked due to failed login attempts."""
        if self.locked_until:
            if datetime.now(timezone.utc) < self.locked_until:
                return True
            else:
                # Unlock account if lock period has expired
                self.locked_until = None
                self.failed_login_attempts = 0
        return False
    
    def record_failed_login(self):
        """Record a failed login attempt."""
        self.failed_login_attempts += 1
        
        # Lock account after 5 failed attempts for 1 hour
        if self.failed_login_attempts >= 5:
            from datetime import timedelta
            self.locked_until = datetime.now(timezone.utc) + timedelta(hours=1)
    
    def record_successful_login(self, ip_address=None):
        """Record a successful login."""
        self.last_login_at = datetime.now(timezone.utc)
        self.last_login_ip = ip_address
        self.failed_login_attempts = 0
        self.locked_until = None
    
    @property
    def full_name(self):
        """Get user's full name."""
        return f"{self.first_name} {self.last_name}".strip()
    
    @property
    def is_admin(self):
        """Check if user has admin privileges."""
        return self.role in ['admin', 'super_admin']
    
    @property
    def is_super_admin(self):
        """Check if user has super admin privileges."""
        return self.role == 'super_admin'
    
    def can_access_tenant(self, tenant_id):
        """Check if user can access a specific tenant."""
        # Super admins can access any tenant
        if self.is_super_admin:
            return True
        # Regular users can only access their own tenant
        return self.tenant_id == tenant_id
    
    def to_dict(self, include_sensitive=False):
        """Convert user to dictionary for API responses."""
        data = {
            'id': self.id,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'full_name': self.full_name,
            'phone': self.phone,
            'tenant_id': self.tenant_id,
            'role': self.role,
            'is_active': self.is_active,
            'is_verified': self.is_verified,
            'last_login_at': self.last_login_at.isoformat() if self.last_login_at else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
        
        if include_sensitive:
            data.update({
                'api_key': self.api_key,
                'api_requests_count': self.api_requests_count,
                'api_rate_limit': self.api_rate_limit,
                'failed_login_attempts': self.failed_login_attempts,
                'is_locked': self.is_account_locked()
            })
        
        return data
    
    def __repr__(self):
        return f'<User {self.email} ({self.tenant_id})>'