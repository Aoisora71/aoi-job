#!/usr/bin/env python3
"""
Authentication service for user login and JWT token management
"""

import jwt
import bcrypt
import os
from datetime import datetime, timedelta
from typing import Optional, Dict
from dotenv import load_dotenv
from db import get_session
from models import User
from logging_utils import get_logger

# Load environment variables from .env file
load_dotenv()

logger = get_logger('auth_service')

# JWT secret key - must be set in .env file or environment variable
JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your-secret-key-change-in-production')
if JWT_SECRET_KEY == 'your-secret-key-change-in-production':
    logger.warning("⚠️ Using default JWT_SECRET_KEY. Set JWT_SECRET_KEY in .env file for production!")

JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = 24 * 7  # 7 days

class AuthService:
    def __init__(self):
        self.secret_key = JWT_SECRET_KEY
        self.algorithm = JWT_ALGORITHM
        self.expiration_hours = JWT_EXPIRATION_HOURS

    def hash_password(self, password: str) -> str:
        """Hash a password using bcrypt"""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')

    def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify a password against its hash"""
        try:
            return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
        except Exception as e:
            logger.error(f"Error verifying password: {e}")
            return False

    def generate_token(self, user_id: int, email: str) -> str:
        """Generate a JWT token for a user"""
        payload = {
            'user_id': user_id,
            'email': email,
            'exp': datetime.utcnow() + timedelta(hours=self.expiration_hours),
            'iat': datetime.utcnow()
        }
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        return token

    def verify_token(self, token: str) -> Optional[Dict]:
        """Verify and decode a JWT token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return None

    def register_user(self, email: str, password: str, display_name: Optional[str] = None) -> Dict:
        """Register a new user - DISABLED: Single-user mode only"""
        return {
            'success': False,
            'error': 'Registration is disabled. This application is in single-user mode.'
        }

    def login_user(self, email: str, password: str) -> Dict:
        """Authenticate a user and return a token"""
        try:
            with get_session() as session:
                user = session.query(User).filter(User.email == email).first()
                if not user:
                    return {
                        'success': False,
                        'error': 'Invalid email or password'
                    }

                # Check if user has a password (for existing users without passwords)
                if not user.password_hash:
                    # Allow login for existing users without password (migration case)
                    # In production, you might want to force password reset
                    logger.warning(f"User {email} has no password hash, allowing login")
                    token = self.generate_token(user.id, user.email)
                    return {
                        'success': True,
                        'user': {
                            'id': user.id,
                            'email': user.email,
                            'display_name': user.display_name
                        },
                        'token': token,
                        'warning': 'Please set a password in settings'
                    }

                # Verify password
                if not self.verify_password(password, user.password_hash):
                    return {
                        'success': False,
                        'error': 'Invalid email or password'
                    }

                # Generate token
                token = self.generate_token(user.id, user.email)

                logger.info(f"User logged in: {email} (ID: {user.id})")
                return {
                    'success': True,
                    'user': {
                        'id': user.id,
                        'email': user.email,
                        'display_name': user.display_name
                    },
                    'token': token
                }
        except Exception as e:
            logger.error(f"Error logging in user: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get a user by ID"""
        try:
            with get_session() as session:
                return session.query(User).filter(User.id == user_id).first()
        except Exception as e:
            logger.error(f"Error getting user: {e}")
            return None

    def change_password(self, user_id: int, old_password: str, new_password: str) -> Dict:
        """Change user password"""
        try:
            if len(new_password) < 6:
                return {
                    'success': False,
                    'error': 'Password must be at least 6 characters'
                }
            
            with get_session() as session:
                user = session.query(User).filter(User.id == user_id).first()
                if not user:
                    return {
                        'success': False,
                        'error': 'User not found'
                    }

                # Verify old password (allow if no password set yet)
                if user.password_hash and not self.verify_password(old_password, user.password_hash):
                    return {
                        'success': False,
                        'error': 'Current password is incorrect'
                    }

                # Update password
                user.password_hash = self.hash_password(new_password)
                session.commit()

                logger.info(f"Password changed for user ID: {user_id}")
                return {
                    'success': True,
                    'message': 'Password changed successfully'
                }
        except Exception as e:
            logger.error(f"Error changing password: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def update_profile(self, user_id: int, email: Optional[str] = None, display_name: Optional[str] = None) -> Dict:
        """Update user profile (email and/or display name)"""
        try:
            with get_session() as session:
                user = session.query(User).filter(User.id == user_id).first()
                if not user:
                    return {
                        'success': False,
                        'error': 'User not found'
                    }
                
                # Update email if provided
                if email:
                    email = email.strip().lower()
                    if not email or '@' not in email:
                        return {
                            'success': False,
                            'error': 'Invalid email address'
                        }
                    
                    # Check if email is already taken by another user
                    existing_user = session.query(User).filter(
                        User.email == email,
                        User.id != user_id
                    ).first()
                    if existing_user:
                        return {
                            'success': False,
                            'error': 'Email is already in use'
                        }
                    
                    user.email = email
                
                # Update display name if provided
                if display_name is not None:
                    user.display_name = display_name.strip() if display_name else None
                
                session.commit()
                
                logger.info(f"Profile updated for user ID: {user_id}")
                return {
                    'success': True,
                    'user': {
                        'id': user.id,
                        'email': user.email,
                        'display_name': user.display_name
                    },
                    'message': 'Profile updated successfully'
                }
        except Exception as e:
            logger.error(f"Error updating profile: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_user_profile(self, user_id: int) -> Optional[Dict]:
        """Get user profile information"""
        try:
            with get_session() as session:
                user = session.query(User).filter(User.id == user_id).first()
                if not user:
                    return None
                
                return {
                    'id': user.id,
                    'email': user.email,
                    'display_name': user.display_name,
                    'created_at': user.created_at.isoformat() if user.created_at else None
                }
        except Exception as e:
            logger.error(f"Error getting user profile: {e}")
            return None

# Global auth service instance
auth_service = AuthService()

