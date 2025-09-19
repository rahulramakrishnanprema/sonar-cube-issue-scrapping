# Issue: AEP-201
# Generated: 2025-09-19T17:05:53.111360
# Thread: 6cb33746
# Enhanced: LangChain structured generation
# AI Model: deepseek/deepseek-chat-v3.1:free
# Max Length: 25000 characters

import os
import re
import logging
import secrets
import string
import time
import jwt
import bcrypt
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Optional, Dict, Any, Tuple, List
from dataclasses import dataclass
from enum import Enum
from threading import Lock

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('auth_service.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AuthError(Exception):
    """Base authentication error class"""
    def __init__(self, message: str, code: int = 400):
        self.message = message
        self.code = code
        super().__init__(self.message)

class ValidationError(AuthError):
    """Input validation error"""
    pass

class AuthenticationError(AuthError):
    """Authentication failure error"""
    pass

class AuthorizationError(AuthError):
    """Authorization failure error"""
    pass

class TokenError(AuthError):
    """Token related error"""
    pass

class PasswordStrength(Enum):
    WEAK = 1
    MEDIUM = 2
    STRONG = 3

@dataclass
class User:
    id: str
    email: str
    password_hash: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login: Optional[datetime]
    failed_login_attempts: int
    last_failed_login: Optional[datetime]

@dataclass
class TokenPayload:
    user_id: str
    email: str
    exp: datetime
    iat: datetime

class AuthConfig:
    def __init__(self):
        self.jwt_secret = os.getenv('JWT_SECRET', secrets.token_urlsafe(64))
        self.jwt_expiry_minutes = int(os.getenv('JWT_EXPIRY_MINUTES', 60))
        self.refresh_token_expiry_days = int(os.getenv('REFRESH_TOKEN_EXPIRY_DAYS', 7))
        self.max_failed_attempts = int(os.getenv('MAX_FAILED_ATTEMPTS', 5))
        self.lockout_minutes = int(os.getenv('LOCKOUT_MINUTES', 15))
        self.password_min_length = int(os.getenv('PASSWORD_MIN_LENGTH', 8))
        
        # Email configuration
        self.smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', 587))
        self.smtp_username = os.getenv('SMTP_USERNAME', '')
        self.smtp_password = os.getenv('SMTP_PASSWORD', '')
        self.from_email = os.getenv('FROM_EMAIL', 'noreply@aep.com')

class UserRepository:
    def __init__(self):
        self._users: Dict[str, User] = {}
        self._email_index: Dict[str, str] = {}
        self._lock = Lock()
        self._reset_tokens: Dict[str, Tuple[str, datetime]] = {}
        self._refresh_tokens: Dict[str, Tuple[str, datetime]] = {}

    def create_user(self, email: str, password_hash: str) -> User:
        with self._lock:
            if email.lower() in self._email_index:
                raise ValidationError("Email already registered")
            
            user_id = secrets.token_urlsafe(16)
            user = User(
                id=user_id,
                email=email.lower(),
                password_hash=password_hash,
                is_active=True,
                is_verified=False,
                created_at=datetime.now(timezone.utc),
                last_login=None,
                failed_login_attempts=0,
                last_failed_login=None
            )
            
            self._users[user_id] = user
            self._email_index[email.lower()] = user_id
            return user

    def find_by_email(self, email: str) -> Optional[User]:
        with self._lock:
            user_id = self._email_index.get(email.lower())
            if user_id:
                return self._users.get(user_id)
            return None

    def find_by_id(self, user_id: str) -> Optional[User]:
        with self._lock:
            return self._users.get(user_id)

    def update_user(self, user: User) -> None:
        with self._lock:
            if user.id not in self._users:
                raise ValidationError("User not found")
            self._users[user.id] = user

    def store_reset_token(self, email: str, token: str, expiry: datetime) -> None:
        with self._lock:
            self._reset_tokens[token] = (email.lower(), expiry)

    def get_reset_token_email(self, token: str) -> Optional[str]:
        with self._lock:
            if token in self._reset_tokens:
                email, expiry = self._reset_tokens[token]
                if expiry > datetime.now(timezone.utc):
                    return email
                del self._reset_tokens[token]
            return None

    def remove_reset_token(self, token: str) -> None:
        with self._lock:
            if token in self._reset_tokens:
                del self._reset_tokens[token]

    def store_refresh_token(self, user_id: str, token: str, expiry: datetime) -> None:
        with self._lock:
            self._refresh_tokens[token] = (user_id, expiry)

    def get_refresh_token_user(self, token: str) -> Optional[str]:
        with self._lock:
            if token in self._refresh_tokens:
                user_id, expiry = self._refresh_tokens[token]
                if expiry > datetime.now(timezone.utc):
                    return user_id
                del self._refresh_tokens[token]
            return None

    def remove_refresh_token(self, token: str) -> None:
        with self._lock:
            if token in self._refresh_tokens:
                del self._refresh_tokens[token]

    def cleanup_expired_tokens(self) -> None:
        with self._lock:
            current_time = datetime.now(timezone.utc)
            
            # Clean reset tokens
            expired_tokens = [
                token for token, (_, expiry) in self._reset_tokens.items()
                if expiry <= current_time
            ]
            for token in expired_tokens:
                del self._reset_tokens[token]
            
            # Clean refresh tokens
            expired_refresh_tokens = [
                token for token, (_, expiry) in self._refresh_tokens.items()
                if expiry <= current_time
            ]
            for token in expired_refresh_tokens:
                del self._refresh_tokens[token]

class EmailService:
    def __init__(self, config: AuthConfig):
        self.config = config

    def send_email(self, to_email: str, subject: str, body: str) -> bool:
        try:
            msg = MIMEMultipart()
            msg['From'] = self.config.from_email
            msg['To'] = to_email
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'html'))

            with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as server:
                server.starttls()
                if self.config.smtp_username and self.config.smtp_password:
                    server.login(self.config.smtp_username, self.config.smtp_password)
                server.send_message(msg)
            
            logger.info(f"Email sent to {to_email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False

    def send_welcome_email(self, to_email: str) -> bool:
        subject = "Welcome to AEP - Account Created"
        body = f"""
        <html>
            <body>
                <h2>Welcome to AEP!</h2>
                <p>Your account has been successfully created.</p>
                <p>Email: {to_email}</p>
                <p>Thank you for joining us!</p>
            </body>
        </html>
        """
        return self.send_email(to_email, subject, body)

    def send_password_reset_email(self, to_email: str, reset_token: str) -> bool:
        subject = "AEP - Password Reset Request"
        body = f"""
        <html>
            <body>
                <h2>Password Reset Request</h2>
                <p>You requested to reset your password. Use the token below:</p>
                <p><strong>Reset Token:</strong> {reset_token}</p>
                <p>This token will expire in 1 hour.</p>
                <p>If you didn't request this, please ignore this email.</p>
            </body>
        </html>
        """
        return self.send_email(to_email, subject, body)

    def send_password_changed_email(self, to_email: str) -> bool:
        subject = "AEP - Password Changed Successfully"
        body = f"""
        <html>
            <body>
                <h2>Password Changed</h2>
                <p>Your password has been successfully changed.</p>
                <p>If you didn't make this change, please contact support immediately.</p>
            </body>
        </html>
        """
        return self.send_email(to_email, subject, body)

class AuthService:
    def __init__(self):
        self.config = AuthConfig()
        self.user_repo = UserRepository()
        self.email_service = EmailService(self.config)
        
        # Cleanup expired tokens periodically
        import threading
        self.cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self.cleanup_thread.start()

    def _cleanup_loop(self):
        while True:
            time.sleep(3600)  # Cleanup every hour
            self.user_repo.cleanup_expired_tokens()

    def validate_email(self, email: str) -> bool:
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))

    def validate_password_strength(self, password: str) -> PasswordStrength:
        if len(password) < self.config.password_min_length:
            raise ValidationError(f"Password must be at least {self.config.password_min_length} characters long")
        
        score = 0
        if any(c.islower() for c in password):
            score += 1
        if any(c.isupper() for c in password):
            score += 1
        if any(c.isdigit() for c in password):
            score += 1
        if any(c in string.punctuation for c in password):
            score += 1
        
        if score >= 4:
            return PasswordStrength.STRONG
        elif score >= 3:
            return PasswordStrength.MEDIUM
        else:
            return PasswordStrength.WEAK

    def hash_password(self, password: str) -> str:
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

    def verify_password(self, password: str, password_hash: str) -> bool:
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))

    def generate_reset_token(self) -> str:
        return secrets.token_urlsafe(32)

    def generate_refresh_token(self) -> str:
        return secrets.token_urlsafe(64)

    def create_access_token(self, user_id: str, email: str) -> str:
        expiry = datetime.now(timezone.utc) + timedelta(minutes=self.config.jwt_expiry_minutes)
        payload = {
            'sub': user_id,
            'email': email,
            'exp': expiry,
            'iat': datetime.now(timezone.utc)
        }
        return jwt.encode(payload, self.config.jwt_secret, algorithm='HS256')

    def verify_access_token(self, token: str) -> TokenPayload:
        try:
            payload = jwt.decode(token, self.config.jwt_secret, algorithms=['HS256'])
            return TokenPayload(
                user_id=payload['sub'],
                email=payload['email'],
                exp=datetime.fromtimestamp(payload['exp'], timezone.utc),
                iat=datetime.fromtimestamp(payload['iat'], timezone.utc)
            )
        except jwt.ExpiredSignatureError:
            raise TokenError("Token has expired", 401)
        except jwt.InvalidTokenError:
            raise TokenError("Invalid token", 401)

    def register_user(self, email: str, password: str) -> Dict[str, Any]:
        if not self.validate_email(email):
            raise ValidationError("Invalid email format")
        
        password_strength = self.validate_password_strength(password)
        if password_strength == PasswordStrength.WEAK:
            raise ValidationError("Password is too weak. Include uppercase, lowercase, numbers, and special characters")
        
        password_hash = self.hash_password(password)
        user = self.user_repo.create_user(email, password_hash)
        
        # Send welcome email
        self.email_service.send_welcome_email(email)
        
        logger.info(f"User registered: {email}")
        return {
            'user_id': user.id,
            'email': user.email,
            'is_active': user.is_active,
            'is_verified': user.is_verified
        }

    def login_user(self, email: str, password: str) -> Dict[str, Any]:
        user = self.user_repo.find_by_email(email)
        if not user:
            raise AuthenticationError("Invalid credentials", 401)
        
        # Check if account is locked
        if user.failed_login_attempts >= self.config.max_failed_attempts:
            if user.last_failed_login and (
                datetime.now(timezone.utc) - user.last_failed_login
            ) < timedelta(minutes=self.config.lockout_minutes):
                raise AuthenticationError("Account temporarily locked due to too many failed attempts", 403)
            else:
                # Reset failed attempts after lockout period
                user.failed_login_attempts = 0
                user.last_failed_login = None
        
        if not user.is_active:
            raise AuthenticationError("Account is deactivated", 403)
        
        if not self.verify_password(password, user.password_hash):
            user.failed_login_attempts += 1
            user.last_failed_login = datetime.now(timezone.utc)
            self.user_repo.update_user(user)
            
            if user.failed_login_attempts >= self.config.max_failed_attempts:
                raise AuthenticationError("Account locked due to too many failed attempts", 403)
            else:
                raise AuthenticationError("Invalid credentials", 401)
        
        # Reset failed attempts on successful login
        user.failed_login_attempts = 0
        user.last_failed_login = None
        user.last_login = datetime.now(timezone.utc)
        self.user_repo.update_user(user)
        
        access_token = self.create_access_token(user.id, user.email)
        refresh_token = self.generate_refresh_token()
        refresh_expiry = datetime.now(timezone.utc) + timedelta(days=self.config.refresh_token_expiry_days)
        
        self.user_repo.store_refresh_token(user.id, refresh_token, refresh_expiry)
        
        logger.info(f"User logged in: {email}")
        return {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'token_type': 'bearer',
            'expires_in': self.config.jwt_expiry_minutes * 60,
            'user': {
                'id': user.id,
                'email': user.email,
                'is_verified': user.is_verified
            }
        }

    def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        user_id = self.user_repo.get_refresh_token_user(refresh_token)
        if not user_id:
            raise TokenError("Invalid refresh token", 401)
        
        user = self.user_repo.find_by_id(user_id)
        if not user or not user.is_active:
            raise AuthenticationError("User not found or inactive", 401)
        
        # Remove used refresh token
        self.user_repo.remove_refresh_token(refresh_token)
        
        # Generate new tokens
        access_token = self.create_access_token(user.id, user.email)
        new_refresh_token = self.generate_refresh_token()
        refresh_expiry = datetime.now(timezone.utc) + timedelta(days=self.config.refresh_token_expiry_days)
        
        self.user_repo.store_refresh_token(user.id, new_refresh_token, refresh_expiry)
        
        logger.info(f"Token refreshed for user: {user.email}")
        return {
            'access_token': access_token,
            'refresh_token': new_refresh_token,
            'token_type': 'bearer',
            'expires_in': self.config.jwt_expiry_minutes * 60
        }

    def logout_user(self, refresh_token: str) -> None:
        self.user_repo.remove_refresh_token(refresh_token)
        logger.info("User logged out")

    def request_password_reset(self, email: str) -> bool:
        user = self.user_repo.find_by_email(email)
        if not user or not user.is_active:
            # Don't reveal whether email exists for security
            logger.warning(f"Password reset requested for non-existent email: {email}")
            return True
        
        reset_token = self.generate_reset_token()
        expiry = datetime.now(timezone.utc) + timedelta(hours=1)
        
        self.user_repo.store_reset_token(email, reset_token, expiry)
        self.email_service.send_password_reset_email(email, reset_token)
        
        logger.info(f"Password reset requested for: {email}")
        return True

    def reset_password(self, reset_token: str, new_password: str) -> bool:
        email = self.user_repo.get_reset_token_email(reset_token)
        if not email:
            raise TokenError("Invalid or expired reset token", 401)
        
        user = self.user_repo.find_by_email(email)
        if not user or not user.is_active:
            raise AuthenticationError("User not found or inactive", 401)
        
        password_strength = self.validate_password_strength(new_password)
        if password_strength == PasswordStrength.WEAK:
            raise ValidationError("Password is too weak")
        
        password_hash = self.hash_password(new_password)
        user.password_hash = password_hash
        user.failed_login_attempts = 0
        user.last_failed_login = None
        
        self.user_repo.update_user(user)
        self.user_repo.remove_reset_token(reset_token)
        self.email_service.send_password_changed_email(email)
        
        logger.info(f"Password reset for: {email}")
        return True

    def change_password(self, user_id: str, current_password: str, new_password: str) -> bool:
        user = self.user_repo.find_by_id(user_id)
        if not user or not user.is_active:
            raise AuthenticationError("User not found or inactive", 401)
        
        if not self.verify_password(current_password, user.password_hash):
            raise AuthenticationError("Current password is incorrect", 401)
        
        password_strength = self.validate_password_strength(new_password)
        if password_strength == PasswordStrength.WEAK:
            raise ValidationError("New password is too weak")
        
        password_hash = self.hash_password(new_password)
        user.password_hash = password_hash
        user.failed_login_attempts = 0
        user.last_failed_login = None
        
        self.user_repo.update_user(user)
        self.email_service.send_password_changed_email(user.email)
        
        logger.info(f"Password changed for user: {user.email}")
        return True

    def verify_token(self, token: str) -> TokenPayload:
        return self.verify_access_token(token)

    def get_user_profile(self, user_id: str) -> Dict[str, Any]:
        user = self.user_repo.find_by_id(user_id)
        if not user or not user.is_active:
            raise AuthenticationError("User not found or inactive", 401)
        
        return {
            'id': user.id,
            'email': user.email,
            'is_verified': user.is_verified,
            'created_at': user.created_at.isoformat(),
            'last_login': user.last_login.isoformat() if user.last_login else None
        }

def auth_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        auth_header = kwargs.get('authorization') or args[0].get('authorization', '') if args else ''
        
        if not auth_header.startswith('Bearer '):
            raise AuthorizationError("Authorization header required", 401)
        
        token = auth_header[7:]
        auth_service = AuthService()
        
        try:
            payload = auth_service.verify_token(token)
            kwargs['user_id'] = payload.user_id
            kwargs['user_email'] = payload.email
            return func(*args, **kwargs)
        except TokenError as e:
            raise AuthorizationError(e.message, e.code)
    
    return wrapper

# Example usage and test cases
if __name__ == "__main__":
    # Initialize auth service
    auth_service = AuthService()
    
    # Test registration
    try:
        user = auth_service.register_user("test@example.com", "StrongPassword123!")
        print("Registration successful:", user)
    except Exception as e:
        print("Registration failed:", str(e))
    
    # Test login
    try:
        result = auth_service.login_user("test@example.com", "StrongPassword123!")
        print("Login successful:", result['access_token'])
    except Exception as e:
        print("Login failed:", str(e))
    
    # Test token verification
    try:
        token = result['access_token']
        payload = auth_service.verify_token(token)
        print("Token verified for user:", payload.email)
    except Exception as e:
        print("Token verification failed:", str(e))