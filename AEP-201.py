# Issue: AEP-201
# Generated: 2025-09-19T16:38:33.925319
# Thread: 95fdfcc7
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
import redis
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from functools import wraps
from pydantic import BaseModel, EmailStr, validator, constr
from fastapi import FastAPI, HTTPException, Depends, status, Request, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, String, Boolean, DateTime, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from configparser import ConfigParser

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("auth_service.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
config = ConfigParser()
config.read('config.ini')

# Database configuration
DATABASE_URL = config.get('database', 'url', fallback='sqlite:///./aep.db')
REDIS_URL = config.get('redis', 'url', fallback='redis://localhost:6379')

# JWT configuration
JWT_SECRET_KEY = config.get('jwt', 'secret_key', fallback=os.urandom(32).hex())
JWT_ALGORITHM = config.get('jwt', 'algorithm', fallback='HS256')
ACCESS_TOKEN_EXPIRE_MINUTES = config.getint('jwt', 'access_token_expire_minutes', fallback=30)
REFRESH_TOKEN_EXPIRE_DAYS = config.getint('jwt', 'refresh_token_expire_days', fallback=7)

# Email configuration
SMTP_SERVER = config.get('email', 'smtp_server', fallback='smtp.gmail.com')
SMTP_PORT = config.getint('email', 'smtp_port', fallback=587)
EMAIL_USERNAME = config.get('email', 'username')
EMAIL_PASSWORD = config.get('email', 'password')
FROM_EMAIL = config.get('email', 'from_email')

# Password requirements
MIN_PASSWORD_LENGTH = config.getint('security', 'min_password_length', fallback=8)
PASSWORD_COMPLEXITY = config.getboolean('security', 'password_complexity', fallback=True)

# Initialize database
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith('sqlite') else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Initialize Redis
redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    token = Column(String, unique=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    token = Column(String, unique=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked = Column(Boolean, default=False)

Base.metadata.create_all(bind=engine)

# Pydantic models
class UserRegister(BaseModel):
    email: EmailStr
    password: constr(min_length=MIN_PASSWORD_LENGTH)
    
    @validator('password')
    def validate_password_complexity(cls, v):
        if PASSWORD_COMPLEXITY:
            if not re.search(r'[A-Z]', v):
                raise ValueError('Password must contain at least one uppercase letter')
            if not re.search(r'[a-z]', v):
                raise ValueError('Password must contain at least one lowercase letter')
            if not re.search(r'\d', v):
                raise ValueError('Password must contain at least one digit')
            if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
                raise ValueError('Password must contain at least one special character')
        return v

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: constr(min_length=MIN_PASSWORD_LENGTH)
    
    @validator('new_password')
    def validate_password_complexity(cls, v):
        if PASSWORD_COMPLEXITY:
            if not re.search(r'[A-Z]', v):
                raise ValueError('Password must contain at least one uppercase letter')
            if not re.search(r'[a-z]', v):
                raise ValueError('Password must contain at least one lowercase letter')
            if not re.search(r'\d', v):
                raise ValueError('Password must contain at least one digit')
            if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
                raise ValueError('Password must contain at least one special character')
        return v

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class UserResponse(BaseModel):
    id: int
    email: str
    is_active: bool
    is_verified: bool
    created_at: datetime

# Utility functions
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@contextmanager
def get_db_context():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def generate_reset_token() -> str:
    return secrets.token_urlsafe(32)

def generate_alphanumeric_token(length: int = 6) -> str:
    characters = string.ascii_letters + string.digits
    return ''.join(secrets.choice(characters) for _ in range(length))

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

def verify_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None

def send_email(to_email: str, subject: str, body: str) -> bool:
    try:
        msg = MIMEMultipart()
        msg['From'] = FROM_EMAIL
        msg['To'] = to_email
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'html'))
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_USERNAME, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        logger.info(f"Email sent to {to_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {str(e)}")
        return False

def rate_limit(key: str, limit: int, window: int) -> bool:
    now = int(time.time())
    window_start = now - window
    redis_client.zremrangebyscore(key, 0, window_start)
    count = redis_client.zcard(key)
    if count >= limit:
        return False
    redis_client.zadd(key, {str(now): now})
    redis_client.expire(key, window)
    return True

# Security
security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)) -> User:
    token = credentials.credentials
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user

# FastAPI app
app = FastAPI(title="AEP Authentication Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserRegister, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    # Rate limiting
    if not rate_limit(f"register:{user_data.email}", 3, 3600):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many registration attempts"
        )
    
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
    
    try:
        # Create new user
        hashed_password = hash_password(user_data.password)
        user = User(
            email=user_data.email,
            password_hash=hashed_password,
            is_verified=False
        )
        
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # Send verification email in background
        verification_token = generate_alphanumeric_token()
        redis_client.setex(f"verify:{user.id}", 3600, verification_token)
        
        verification_url = f"https://yourapp.com/verify?token={verification_token}&user_id={user.id}"
        email_body = f"""
        <h1>Welcome to AEP!</h1>
        <p>Please click the link below to verify your email address:</p>
        <a href="{verification_url}">Verify Email</a>
        <p>This link will expire in 1 hour.</p>
        """
        
        background_tasks.add_task(send_email, user.email, "Verify your AEP account", email_body)
        
        logger.info(f"User registered successfully: {user.email}")
        return user
        
    except Exception as e:
        db.rollback()
        logger.error(f"Registration failed for {user_data.email}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )

@app.post("/login", response_model=TokenResponse)
async def login(user_data: UserLogin, db: Session = Depends(get_db)):
    # Rate limiting
    if not rate_limit(f"login:{user_data.email}", 5, 900):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts"
        )
    
    user = db.query(User).filter(User.email == user_data.email, User.is_active == True).first()
    if not user or not verify_password(user_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified"
        )
    
    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()
    
    # Create tokens
    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token({"sub": str(user.id)})
    
    # Store refresh token
    refresh_token_entry = RefreshToken(
        user_id=user.id,
        token=refresh_token,
        expires_at=datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    )
    db.add(refresh_token_entry)
    db.commit()
    
    logger.info(f"User logged in successfully: {user.email}")
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

@app.post("/refresh", response_model=TokenResponse)
async def refresh_token(refresh_token: str, db: Session = Depends(get_db)):
    # Verify refresh token
    payload = verify_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )
    
    # Check if refresh token exists and is not revoked
    token_entry = db.query(RefreshToken).filter(
        RefreshToken.token == refresh_token,
        RefreshToken.revoked == False,
        RefreshToken.expires_at > datetime.utcnow()
    ).first()
    
    if not token_entry:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not found or expired"
        )
    
    # Get user
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    # Revoke old refresh token
    token_entry.revoked = True
    db.commit()
    
    # Create new tokens
    access_token = create_access_token({"sub": str(user.id)})
    new_refresh_token = create_refresh_token({"sub": str(user.id)})
    
    # Store new refresh token
    new_refresh_token_entry = RefreshToken(
        user_id=user.id,
        token=new_refresh_token,
        expires_at=datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    )
    db.add(new_refresh_token_entry)
    db.commit()
    
    logger.info(f"Token refreshed for user: {user.email}")
    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer"
    }

@app.post("/password-reset/request")
async def password_reset_request(data: PasswordResetRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email, User.is_active == True).first()
    if user:
        # Rate limiting
        if not rate_limit(f"password_reset:{user.id}", 3, 3600):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many password reset attempts"
            )
        
        # Generate reset token
        reset_token = generate_reset_token()
        expires_at = datetime.utcnow() + timedelta(hours=1)
        
        # Store reset token
        reset_token_entry = PasswordResetToken(
            user_id=user.id,
            token=reset_token,
            expires_at=expires_at
        )
        db.add(reset_token_entry)
        db.commit()
        
        # Send reset email
        reset_url = f"https://yourapp.com/password-reset?token={reset_token}"
        email_body = f"""
        <h1>Password Reset Request</h1>
        <p>Click the link below to reset your password:</p>
        <a href="{reset_url}">Reset Password</a>
        <p>This link will expire in 1 hour.</p>
        <p>If you didn't request this, please ignore this email.</p>
        """
        
        background_tasks.add_task(send_email, user.email, "Password Reset Request", email_body)
    
    # Always return success to prevent email enumeration
    logger.info(f"Password reset requested for: {data.email}")
    return {"message": "If the email exists, a reset link has been sent"}

@app.post("/password-reset/confirm")
async def password_reset_confirm(data: PasswordResetConfirm, db: Session = Depends(get_db)):
    # Find valid reset token
    reset_token_entry = db.query(PasswordResetToken).filter(
        PasswordResetToken.token == data.token,
        PasswordResetToken.used == False,
        PasswordResetToken.expires_at > datetime.utcnow()
    ).first()
    
    if not reset_token_entry:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    
    # Get user
    user = db.query(User).filter(User.id == reset_token_entry.user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found"
        )
    
    try:
        # Update password
        user.password_hash = hash_password(data.new_password)
        reset_token_entry.used = True
        
        # Revoke all refresh tokens
        db.query(RefreshToken).filter(RefreshToken.user_id == user.id).update({"revoked": True})
        
        db.commit()
        
        logger.info(f"Password reset successful for user: {user.email}")
        return {"message": "Password reset successfully"}
    
    except Exception as e:
        db.rollback()
        logger.error(f"Password reset failed for user {user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password reset failed"
        )

@app.post("/verify-email")
async def verify_email(token: str, user_id: int, db: Session = Depends(get_db)):
    # Check verification token
    stored_token = redis_client.get(f"verify:{user_id}")
    if not stored_token or stored_token != token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification token"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found"
        )
    
    if user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already verified"
        )
    
    user.is_verified = True
    db.commit()
    
    # Remove verification token
    redis_client.delete(f"verify:{user_id}")
    
    logger.info(f"Email verified for user: {user.email}")
    return {"message": "Email verified successfully"}

@app.post("/logout")
async def logout(refresh_token: str, db: Session = Depends(get_db)):
    # Revoke refresh token
    token_entry = db.query(RefreshToken).filter(RefreshToken.token == refresh_token).first()
    if token_entry:
        token_entry.revoked = True
        db.commit()
        logger.info(f"User logged out: {token_entry.user_id}")
    
    return {"message": "Logged out successfully"}

@app.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    return current_user

@app.post("/change-password")
async def change_password(
    current_password: str,
    new_password: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Verify current password
    if not verify_password(current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Validate new password
    if len(new_password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"New password must be at least {MIN_PASSWORD_LENGTH} characters long"
        )
    
    if PASSWORD_COMPLEXITY:
        if not re.search(r'[A-Z]', new_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Password must contain at least one uppercase letter'
            )
        if not re.search(r'[a-z]', new_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Password must contain at least one lowercase letter'
            )
        if not re.search(r'\d', new_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Password must contain at least one digit'
            )
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', new_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Password must contain at least one special character'
            )
    
    try:
        # Update password
        current_user.password_hash = hash_password(new_password)
        
        # Revoke all refresh tokens
        db.query(RefreshToken).filter(RefreshToken.user_id == current_user.id).update({"revoked": True})
        
        db.commit()
        
        logger.info(f"Password changed successfully for user: {current_user.email}")
        return {"message": "Password changed successfully"}
    
    except Exception as e:
        db.rollback()
        logger.error(f"Password change failed for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password change failed"
        )

# Health check endpoint
@app.get("/health")
async def health_check():
    try:
        # Check database connection
        with get_db_context() as db:
            db.execute("SELECT 1")
        
        # Check Redis connection
        redis_client.ping()
        
        return {"status": "healthy", "database": "connected", "redis": "connected"}
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service unhealthy"
        )

# Token cleanup background task (should be run periodically)
def cleanup_expired_tokens():
    with get_db_context() as db:
        try:
            # Clean up expired refresh tokens
            db.query(RefreshToken).filter(RefreshToken.expires_at < datetime.utcnow()).delete()
            
            # Clean up expired password reset tokens
            db.query(PasswordResetToken).filter(PasswordResetToken.expires_at < datetime.utcnow()).delete()
            
            db.commit()
            logger.info("Expired tokens cleaned up successfully")
        except Exception as e:
            logger.error(f"Token cleanup failed: {str(e)}")
            db.rollback()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)