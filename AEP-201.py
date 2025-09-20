# Issue: AEP-201
# Generated: 2025-09-20T07:51:16.614403
# Thread: e2fc322d
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
from functools import wraps
from typing import Optional, Dict, Any, Tuple
from pydantic import BaseModel, EmailStr, Field, validator
from fastapi import FastAPI, HTTPException, Depends, status, Request, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, String, Boolean, DateTime, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AEP Authentication Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/aep_db")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
JWT_SECRET = os.getenv("JWT_SECRET", secrets.token_urlsafe(64))
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")

engine = create_engine(DATABASE_URL, pool_size=20, max_overflow=0)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
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

class PasswordReset(BaseModel):
    token: str
    new_password: str

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    email: Optional[str] = None

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
    finally:
        db.close()

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def generate_reset_token() -> str:
    return secrets.token_urlsafe(32)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)

def create_refresh_token(data: dict) -> str:
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = data.copy()
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None

class JWTBearer(HTTPBearer):
    def __init__(self, auto_error: bool = True):
        super().__init__(auto_error=auto_error)

    async def __call__(self, request: Request) -> HTTPAuthorizationCredentials:
        credentials = await super().__call__(request)
        if credentials:
            if not credentials.scheme == "Bearer":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Invalid authentication scheme."
                )
            token_data = self.verify_jwt(credentials.credentials)
            if not token_data:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Invalid token or expired token."
                )
            return credentials
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid authorization code."
            )

    def verify_jwt(self, jwtoken: str) -> bool:
        try:
            payload = verify_token(jwtoken)
            return payload is not None
        except Exception:
            return False

def get_current_user(token: str = Depends(JWTBearer())) -> TokenData:
    payload = verify_token(token.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    email: str = payload.get("sub")
    if email is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenData(email=email)

def send_email_async(to_email: str, subject: str, body: str):
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_USERNAME
        msg['To'] = to_email
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'html'))
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        logger.info(f"Email sent successfully to {to_email}")
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {str(e)}")
        raise

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

@app.post("/register", status_code=status.HTTP_201_CREATED)
async def register_user(user: UserCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    if not rate_limit(f"register:{user.email}", 3, 3600):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many registration attempts. Please try again later."
        )
    
    existing_user = db.query(User).filter(User.email == user.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
    
    hashed_password = hash_password(user.password)
    db_user = User(email=user.email, password_hash=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    verification_token = create_access_token({"sub": user.email})
    verification_url = f"https://yourapp.com/verify-email?token={verification_token}"
    
    email_body = f"""
    <h1>Welcome to AEP!</h1>
    <p>Please click the link below to verify your email address:</p>
    <a href="{verification_url}">Verify Email</a>
    <p>This link will expire in 24 hours.</p>
    """
    
    background_tasks.add_task(
        send_email_async,
        user.email,
        "Verify your AEP account",
        email_body
    )
    
    logger.info(f"User registered successfully: {user.email}")
    return {"message": "User created successfully. Please check your email for verification instructions."}

@app.post("/login")
async def login_user(user: UserLogin, db: Session = Depends(get_db)):
    if not rate_limit(f"login:{user.email}", 5, 900):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later."
        )
    
    db_user = db.query(User).filter(User.email == user.email).first()
    if not db_user or not verify_password(user.password, db_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    if not db_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is deactivated"
        )
    
    access_token = create_access_token({"sub": db_user.email})
    refresh_token = create_refresh_token({"sub": db_user.email})
    
    redis_client.setex(f"refresh_token:{db_user.email}", 
                      REFRESH_TOKEN_EXPIRE_DAYS * 86400, 
                      refresh_token)
    
    logger.info(f"User logged in successfully: {user.email}")
    return Token(access_token=access_token, refresh_token=refresh_token)

@app.post("/refresh")
async def refresh_token(refresh_token: str, db: Session = Depends(get_db)):
    payload = verify_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    email = payload.get("sub")
    stored_refresh_token = redis_client.get(f"refresh_token:{email}")
    
    if not stored_refresh_token or stored_refresh_token != refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    db_user = db.query(User).filter(User.email == email).first()
    if not db_user or not db_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    new_access_token = create_access_token({"sub": db_user.email})
    new_refresh_token = create_refresh_token({"sub": db_user.email})
    
    redis_client.setex(f"refresh_token:{db_user.email}", 
                      REFRESH_TOKEN_EXPIRE_DAYS * 86400, 
                      new_refresh_token)
    
    logger.info(f"Token refreshed for user: {email}")
    return Token(access_token=new_access_token, refresh_token=new_refresh_token)

@app.post("/password-reset-request")
async def password_reset_request(
    reset_request: PasswordResetRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    db_user = db.query(User).filter(User.email == reset_request.email).first()
    if db_user:
        reset_token = generate_reset_token()
        redis_client.setex(f"password_reset:{reset_token}", 3600, db_user.email)
        
        reset_url = f"https://yourapp.com/reset-password?token={reset_token}"
        
        email_body = f"""
        <h1>Password Reset Request</h1>
        <p>Click the link below to reset your password:</p>
        <a href="{reset_url}">Reset Password</a>
        <p>This link will expire in 1 hour.</p>
        <p>If you didn't request this reset, please ignore this email.</p>
        """
        
        background_tasks.add_task(
            send_email_async,
            reset_request.email,
            "Password Reset Request",
            email_body
        )
    
    logger.info(f"Password reset requested for: {reset_request.email}")
    return {"message": "If the email exists, a password reset link has been sent"}

@app.post("/password-reset")
async def password_reset(reset_data: PasswordReset, db: Session = Depends(get_db)):
    email = redis_client.get(f"password_reset:{reset_data.token}")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    
    db_user = db.query(User).filter(User.email == email).first()
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found"
        )
    
    hashed_password = hash_password(reset_data.new_password)
    db_user.password_hash = hashed_password
    db.commit()
    
    redis_client.delete(f"password_reset:{reset_data.token}")
    redis_client.delete(f"refresh_token:{email}")
    
    logger.info(f"Password reset successfully for: {email}")
    return {"message": "Password reset successfully"}

@app.post("/logout")
async def logout_user(current_user: TokenData = Depends(get_current_user)):
    redis_client.delete(f"refresh_token:{current_user.email}")
    logger.info(f"User logged out: {current_user.email}")
    return {"message": "Logged out successfully"}

@app.get("/verify-email/{token}")
async def verify_email(token: str, db: Session = Depends(get_db)):
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification token"
        )
    
    email = payload.get("sub")
    db_user = db.query(User).filter(User.email == email).first()
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found"
        )
    
    db_user.is_verified = True
    db.commit()
    
    logger.info(f"Email verified for user: {email}")
    return {"message": "Email verified successfully"}

@app.get("/me")
async def get_current_user_info(current_user: TokenData = Depends(get_current_user), db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == current_user.email).first()
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return {
        "email": db_user.email,
        "is_active": db_user.is_active,
        "is_verified": db_user.is_verified,
        "created_at": db_user.created_at
    }

@app.on_event("startup")
async def startup_event():
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")

@app.on_event("shutdown")
async def shutdown_event():
    redis_client.close()
    logger.info("Redis connection closed")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)