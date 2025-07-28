"""
Authentication API endpoints
Handles user registration, login, JWT tokens, and API key authentication
"""

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, create_refresh_token
from flask_limiter import Limiter
from functools import wraps
import logging
from datetime import datetime, timezone

from app import db, limiter
from app.models.user import User

auth_bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)

def authenticate_api_key(f):
    """Decorator for API key authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        
        if not api_key:
            return jsonify({
                'error': 'Missing API key',
                'message': 'API key required in X-API-Key header'
            }), 401
        
        user = User.query.filter_by(api_key=api_key, is_active=True).first()
        
        if not user:
            return jsonify({
                'error': 'Invalid API key',
                'message': 'API key not found or inactive'
            }), 401
        
        if user.is_account_locked():
            return jsonify({
                'error': 'Account locked',
                'message': 'Account is temporarily locked due to security reasons'
            }), 423
        
        if user.is_rate_limited():
            return jsonify({
                'error': 'Rate limit exceeded',
                'message': f'API rate limit of {user.api_rate_limit} requests per hour exceeded'
            }), 429
        
        # Update usage tracking
        user.increment_api_usage()
        db.session.commit()
        
        # Add user to request context
        request.current_user = user
        
        return f(*args, **kwargs)
    
    return decorated_function

def get_current_user():
    """Get current authenticated user from request context."""
    return getattr(request, 'current_user', None)

@auth_bp.route('/register', methods=['POST'])
@limiter.limit("5 per minute")
def register():
    """Register a new user."""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['email', 'password', 'first_name', 'last_name']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'error': 'Missing required field',
                    'message': f'{field} is required'
                }), 400
        
        # Check if user already exists
        if User.query.filter_by(email=data['email']).first():
            return jsonify({
                'error': 'User already exists',
                'message': 'A user with this email already exists'
            }), 409
        
        # Create new user
        user = User(
            email=data['email'],
            first_name=data['first_name'],
            last_name=data['last_name'],
            phone=data.get('phone'),
            tenant_id=data.get('tenant_id', 'default'),
            role=data.get('role', 'user')
        )
        
        user.set_password(data['password'])
        
        db.session.add(user)
        db.session.commit()
        
        logger.info(f"New user registered: {user.email}")
        
        return jsonify({
            'message': 'User registered successfully',
            'user': user.to_dict(),
            'api_key': user.api_key
        }), 201
        
    except Exception as e:
        logger.error(f"User registration failed: {str(e)}")
        db.session.rollback()
        return jsonify({
            'error': 'Registration failed',
            'message': 'An error occurred during registration'
        }), 500

@auth_bp.route('/login', methods=['POST'])
@limiter.limit("10 per minute")
def login():
    """Authenticate user and return JWT token."""
    try:
        data = request.get_json()
        
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({
                'error': 'Missing credentials',
                'message': 'Email and password are required'
            }), 400
        
        user = User.query.filter_by(email=email).first()
        
        if not user:
            return jsonify({
                'error': 'Invalid credentials',
                'message': 'Invalid email or password'
            }), 401
        
        if user.is_account_locked():
            return jsonify({
                'error': 'Account locked',
                'message': 'Account is temporarily locked due to failed login attempts'
            }), 423
        
        if not user.is_active:
            return jsonify({
                'error': 'Account inactive',
                'message': 'Your account has been deactivated'
            }), 403
        
        if not user.check_password(password):
            user.record_failed_login()
            db.session.commit()
            
            return jsonify({
                'error': 'Invalid credentials',
                'message': 'Invalid email or password'
            }), 401
        
        # Successful login
        client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
        user.record_successful_login(client_ip)
        
        # Create JWT tokens
        access_token = create_access_token(identity=user.id)
        refresh_token = create_refresh_token(identity=user.id)
        
        db.session.commit()
        
        logger.info(f"User logged in: {user.email} from {client_ip}")
        
        return jsonify({
            'message': 'Login successful',
            'access_token': access_token,
            'refresh_token': refresh_token,
            'user': user.to_dict(),
            'expires_in': current_app.config['JWT_ACCESS_TOKEN_EXPIRES'].total_seconds()
        }), 200
        
    except Exception as e:
        logger.error(f"Login failed: {str(e)}")
        return jsonify({
            'error': 'Login failed',
            'message': 'An error occurred during login'
        }), 500

@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """Refresh JWT access token."""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user or not user.is_active:
            return jsonify({
                'error': 'Invalid user',
                'message': 'User not found or inactive'
            }), 401
        
        access_token = create_access_token(identity=user.id)
        
        return jsonify({
            'access_token': access_token,
            'expires_in': current_app.config['JWT_ACCESS_TOKEN_EXPIRES'].total_seconds()
        }), 200
        
    except Exception as e:
        logger.error(f"Token refresh failed: {str(e)}")
        return jsonify({
            'error': 'Token refresh failed',
            'message': 'An error occurred while refreshing token'
        }), 500

@auth_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    """Get current user profile."""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({
                'error': 'User not found',
                'message': 'User profile not found'
            }), 404
        
        return jsonify({
            'user': user.to_dict(include_sensitive=True)
        }), 200
        
    except Exception as e:
        logger.error(f"Get profile failed: {str(e)}")
        return jsonify({
            'error': 'Profile retrieval failed',
            'message': 'An error occurred while retrieving profile'
        }), 500

@auth_bp.route('/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    """Update user profile."""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({
                'error': 'User not found',
                'message': 'User profile not found'
            }), 404
        
        data = request.get_json()
        
        # Update allowed fields
        updatable_fields = ['first_name', 'last_name', 'phone']
        for field in updatable_fields:
            if field in data:
                setattr(user, field, data[field])
        
        user.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        
        logger.info(f"User profile updated: {user.email}")
        
        return jsonify({
            'message': 'Profile updated successfully',
            'user': user.to_dict()
        }), 200
        
    except Exception as e:
        logger.error(f"Profile update failed: {str(e)}")
        db.session.rollback()
        return jsonify({
            'error': 'Profile update failed',
            'message': 'An error occurred while updating profile'
        }), 500

@auth_bp.route('/change-password', methods=['POST'])
@jwt_required()
def change_password():
    """Change user password."""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({
                'error': 'User not found',
                'message': 'User not found'
            }), 404
        
        data = request.get_json()
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        
        if not current_password or not new_password:
            return jsonify({
                'error': 'Missing passwords',
                'message': 'Current password and new password are required'
            }), 400
        
        if not user.check_password(current_password):
            return jsonify({
                'error': 'Invalid current password',
                'message': 'Current password is incorrect'
            }), 401
        
        if len(new_password) < 8:
            return jsonify({
                'error': 'Weak password',
                'message': 'Password must be at least 8 characters long'
            }), 400
        
        user.set_password(new_password)
        user.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        
        logger.info(f"Password changed for user: {user.email}")
        
        return jsonify({
            'message': 'Password changed successfully'
        }), 200
        
    except Exception as e:
        logger.error(f"Password change failed: {str(e)}")
        db.session.rollback()
        return jsonify({
            'error': 'Password change failed',
            'message': 'An error occurred while changing password'
        }), 500

@auth_bp.route('/reset-api-key', methods=['POST'])
@jwt_required()
def reset_api_key():
    """Reset user API key."""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({
                'error': 'User not found',
                'message': 'User not found'
            }), 404
        
        old_api_key = user.api_key
        user.reset_api_key()
        user.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        
        logger.info(f"API key reset for user: {user.email}")
        
        return jsonify({
            'message': 'API key reset successfully',
            'api_key': user.api_key
        }), 200
        
    except Exception as e:
        logger.error(f"API key reset failed: {str(e)}")
        db.session.rollback()
        return jsonify({
            'error': 'API key reset failed',
            'message': 'An error occurred while resetting API key'
        }), 500

@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """Logout user (client-side token invalidation)."""
    # In a production system, you might want to implement token blacklisting
    return jsonify({
        'message': 'Logged out successfully'
    }), 200

@auth_bp.route('/verify-token', methods=['GET'])
@authenticate_api_key
def verify_api_key():
    """Verify API key is valid."""
    user = get_current_user()
    
    return jsonify({
        'message': 'API key is valid',
        'user': user.to_dict(),
        'remaining_requests': max(0, user.api_rate_limit - user.api_requests_count)
    }), 200