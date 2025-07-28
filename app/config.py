"""
Configuration management for Invoice Extraction System
Supports multiple environments with secure defaults
"""

import os
from datetime import timedelta
from dotenv import load_dotenv

# Load environment variables
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

class Config:
    """Base configuration class with common settings."""
    
    # Flask Core Settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    FLASK_ENV = os.environ.get('FLASK_ENV') or 'production'
    
    # Database Configuration
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        f'sqlite:///{os.path.join(basedir, "invoice_extraction.db")}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': int(os.environ.get('DATABASE_POOL_SIZE', 20)),
        'pool_timeout': 20,
        'pool_recycle': 3600,
        'max_overflow': int(os.environ.get('DATABASE_MAX_OVERFLOW', 10))
    }
    
    # JWT Configuration
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or SECRET_KEY
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        seconds=int(os.environ.get('JWT_ACCESS_TOKEN_EXPIRES', 3600))
    )
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    
    # Redis Configuration
    REDIS_URL = os.environ.get('REDIS_URL') or 'redis://localhost:6379/0'
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL') or REDIS_URL
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND') or REDIS_URL
    
    # File Upload Configuration
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 10 * 1024 * 1024))  # 10MB
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER') or os.path.join(basedir, '../uploads')
    EXPORT_FOLDER = os.environ.get('EXPORT_FOLDER') or os.path.join(basedir, '../exports')
    ALLOWED_EXTENSIONS = set(os.environ.get('ALLOWED_EXTENSIONS', 'pdf,jpg,jpeg,png').split(','))
    
    # OCR Configuration
    OCR_CONFIDENCE_THRESHOLD = float(os.environ.get('OCR_CONFIDENCE_THRESHOLD', 0.7))
    OCR_TIMEOUT = int(os.environ.get('OCR_TIMEOUT', 30))
    OCR_LANGUAGE = os.environ.get('OCR_LANGUAGE', 'en')
    
    # Rate Limiting Configuration
    RATELIMIT_STORAGE_URL = os.environ.get('RATE_LIMIT_STORAGE_URL') or REDIS_URL
    RATELIMIT_DEFAULT = os.environ.get('DEFAULT_RATE_LIMIT', '100 per hour')
    RATELIMIT_API = os.environ.get('API_RATE_LIMIT', '1000 per hour')
    
    # CORS Configuration
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*').split(',')
    
    # Security Configuration
    SECURE_SSL_REDIRECT = os.environ.get('SECURE_SSL_REDIRECT', 'False').lower() == 'true'
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'True').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = os.environ.get('SESSION_COOKIE_HTTPONLY', 'True').lower() == 'true'
    
    # Logging Configuration
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FORMAT = os.environ.get('LOG_FORMAT', 'json')
    SENTRY_DSN = os.environ.get('SENTRY_DSN')
    
    # Business Configuration
    DATA_RETENTION_DAYS = int(os.environ.get('DATA_RETENTION_DAYS', 2555))  # 7 years
    BACKUP_SCHEDULE = os.environ.get('BACKUP_SCHEDULE', 'daily')
    AUDIT_LOG_RETENTION_DAYS = int(os.environ.get('AUDIT_LOG_RETENTION_DAYS', 2555))
    
    # Performance Configuration
    CELERY_WORKER_CONCURRENCY = int(os.environ.get('CELERY_WORKER_CONCURRENCY', 4))
    CACHE_TTL = int(os.environ.get('CACHE_TTL', 3600))
    IMAGE_PROCESSING_TIMEOUT = int(os.environ.get('IMAGE_PROCESSING_TIMEOUT', 60))
    
    # Multi-tenant Configuration
    ENABLE_MULTI_TENANT = os.environ.get('ENABLE_MULTI_TENANT', 'True').lower() == 'true'
    DEFAULT_TENANT = os.environ.get('DEFAULT_TENANT', 'default')
    
    # Monitoring Configuration
    HEALTH_CHECK_INTERVAL = int(os.environ.get('HEALTH_CHECK_INTERVAL', 60))
    METRICS_ENABLED = os.environ.get('METRICS_ENABLED', 'True').lower() == 'true'
    PERFORMANCE_MONITORING = os.environ.get('PERFORMANCE_MONITORING', 'True').lower() == 'true'
    
    @staticmethod
    def init_app(app):
        """Initialize application with configuration."""
        # Ensure upload and export directories exist
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        os.makedirs(app.config['EXPORT_FOLDER'], exist_ok=True)

class DevelopmentConfig(Config):
    """Development environment configuration."""
    DEBUG = True
    FLASK_ENV = 'development'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or \
        f'sqlite:///{os.path.join(basedir, "dev_invoice_extraction.db")}'
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False

class TestingConfig(Config):
    """Testing environment configuration."""
    TESTING = True
    FLASK_ENV = 'testing'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(seconds=300)  # 5 minutes for tests
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    WTF_CSRF_ENABLED = False

class ProductionConfig(Config):
    """Production environment configuration."""
    DEBUG = False
    TESTING = False
    FLASK_ENV = 'production'
    
    @classmethod
    def init_app(cls, app):
        Config.init_app(app)
        
        # Log to syslog in production
        import logging
        from logging.handlers import SysLogHandler
        syslog_handler = SysLogHandler()
        syslog_handler.setLevel(logging.WARNING)
        app.logger.addHandler(syslog_handler)

# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}