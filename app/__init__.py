"""
Commercial Invoice Extraction System
Production-ready Flask application with enterprise features
"""

import os
import logging
from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate
import structlog
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

from app.config import Config

# Initialize extensions
db = SQLAlchemy()
jwt = JWTManager()
cors = CORS()
limiter = Limiter(key_func=get_remote_address)
migrate = Migrate()

def create_app(config_class=Config):
    """Application factory pattern for creating Flask app."""
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize Sentry for error tracking
    if app.config.get('SENTRY_DSN'):
        sentry_sdk.init(
            dsn=app.config['SENTRY_DSN'],
            integrations=[
                FlaskIntegration(),
                SqlalchemyIntegration(),
            ],
            traces_sample_rate=1.0,
            environment=app.config.get('FLASK_ENV', 'production')
        )
    
    # Setup structured logging
    setup_logging(app)
    
    # Initialize extensions
    db.init_app(app)
    jwt.init_app(app)
    cors.init_app(app)
    limiter.init_app(app)
    migrate.init_app(app, db)
    
    # Register blueprints
    register_blueprints(app)
    
    # Register error handlers
    register_error_handlers(app)
    
    # Register security headers
    register_security_headers(app)
    
    # Register health check
    register_health_check(app)
    
    return app

def setup_logging(app):
    """Configure structured logging for production."""
    log_level = getattr(logging, app.config.get('LOG_LEVEL', 'INFO'))
    
    if app.config.get('LOG_FORMAT') == 'json':
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer()
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
    
    logging.basicConfig(level=log_level)

def register_blueprints(app):
    """Register all application blueprints."""
    from app.api.auth import auth_bp
    from app.api.invoice_routes import invoice_bp
    from app.api.data_routes import data_bp
    from app.api.admin_routes import admin_bp
    
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(invoice_bp, url_prefix='/api')
    app.register_blueprint(data_bp, url_prefix='/api')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')

def register_error_handlers(app):
    """Register global error handlers."""
    
    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({
            'error': 'Bad Request',
            'message': 'The request was malformed or invalid',
            'status_code': 400
        }), 400
    
    @app.errorhandler(401)
    def unauthorized(error):
        return jsonify({
            'error': 'Unauthorized',
            'message': 'Authentication required',
            'status_code': 401
        }), 401
    
    @app.errorhandler(403)
    def forbidden(error):
        return jsonify({
            'error': 'Forbidden',
            'message': 'Insufficient permissions',
            'status_code': 403
        }), 403
    
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            'error': 'Not Found',
            'message': 'The requested resource was not found',
            'status_code': 404
        }), 404
    
    @app.errorhandler(413)
    def file_too_large(error):
        return jsonify({
            'error': 'File Too Large',
            'message': f'File size exceeds maximum limit of {app.config["MAX_CONTENT_LENGTH"]} bytes',
            'status_code': 413
        }), 413
    
    @app.errorhandler(429)
    def rate_limit_exceeded(error):
        return jsonify({
            'error': 'Rate Limit Exceeded',
            'message': 'Too many requests. Please try again later.',
            'status_code': 429
        }), 429
    
    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f'Internal server error: {str(error)}')
        return jsonify({
            'error': 'Internal Server Error',
            'message': 'An unexpected error occurred',
            'status_code': 500
        }), 500

def register_security_headers(app):
    """Add security headers to all responses."""
    
    @app.after_request
    def add_security_headers(response):
        # Prevent XSS attacks
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        
        # HTTPS enforcement
        if app.config.get('SECURE_SSL_REDIRECT'):
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        
        # Content Security Policy
        response.headers['Content-Security-Policy'] = "default-src 'self'"
        
        # Referrer Policy
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        return response

def register_health_check(app):
    """Register health check endpoint."""
    
    @app.route('/health')
    def health_check():
        """Health check endpoint for load balancers and monitoring."""
        try:
            # Check database connection
            db.session.execute('SELECT 1')
            db_status = 'healthy'
        except Exception as e:
            app.logger.error(f'Database health check failed: {str(e)}')
            db_status = 'unhealthy'
        
        health_data = {
            'status': 'healthy' if db_status == 'healthy' else 'unhealthy',
            'timestamp': structlog.get_logger().info('Health check requested'),
            'services': {
                'database': db_status,
                'application': 'healthy'
            },
            'version': '1.0.0'
        }
        
        status_code = 200 if health_data['status'] == 'healthy' else 503
        return jsonify(health_data), status_code