# Issue: AEP-201
# Generated: 2025-09-20T07:44:19.876971
# Thread: 45c5c760
# Enhanced: LangChain structured generation
# AI Model: deepseek/deepseek-chat-v3.1:free
# Max Length: 25000 characters

import os
import re
import logging
import secrets
import string
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from functools import wraps

import jwt
import bcrypt
import redis
from pydantic import BaseModel, EmailStr, validator, constr
from fastapi import FastAPI, HTTPException, Depends, status, Request, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from jose import JWTError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

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

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./aep.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Redis configuration for token blacklist
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
redis_client = redis.from_url(REDIS_URL)

# JWT configuration
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# Password requirements
MIN_PASSWORD_LENGTH = 8
PASSWORD_COMPLEXITY = re.compile(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]')

# Initialize FastAPI app
app = FastAPI(title="AEP Authentication Service", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database models
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, index=True, nullable=False)
    token = Column(String, unique=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    is_used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

# Create tables
Base.metadata.create_all(bind=engine)

# Pydantic models
class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None

class UserCreate(UserBase):
    password: constr(min_length=MIN_PASSWORD_LENGTH)
    
    @validator('password')
    def validate_password_complexity(cls, v):
        if not PASSWORD_COMPLEXITY.match(v):
            raise ValueError('Password must contain at least one uppercase letter, one lowercase letter, one number, and one special character')
        return v

class UserResponse(UserBase):
    id: int
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: constr(min_length=MIN_PASSWORD_LENGTH)
    
    @validator('new_password')
    def validate_password_complexity(cls, v):
        if not PASSWORD_COMPLEXITY.match(v):
            raise ValueError('Password must contain at least one uppercase letter, one lowercase letter, one number, and one special character')
        return v

class RefreshTokenRequest(BaseModel):
    refresh_token: str

# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Password utilities
def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

# Token utilities
def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: Dict[str, Any]) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

def is_token_blacklisted(token: str) -> bool:
    return redis_client.exists(f"blacklist:{token}") > 0

def add_token_to_blacklist(token: str, expire_in: int) -> None:
    redis_client.setex(f"blacklist:{token}", expire_in, "1")

# Auth dependencies
class JWTBearer(HTTPBearer):
    def __init__(self, auto_error: bool = True):
        super(JWTBearer, self).__init__(auto_error=auto_error)

    async def __call__(self, request: Request):
        credentials: HTTPAuthorizationCredentials = await super(JWTBearer, self).__call__(request)
        if credentials:
            if not credentials.scheme == "Bearer":
                raise HTTPException(status_code=403, detail="Invalid authentication scheme.")
            token = credentials.credentials
            if is_token_blacklisted(token):
                raise HTTPException(status_code=403, detail="Token has been revoked.")
            payload = verify_token(token)
            if payload.get("type") == "refresh":
                raise HTTPException(status_code=403, detail="Refresh token not allowed for access.")
            return payload
        else:
            raise HTTPException(status_code=403, detail="Invalid authorization code.")

def get_current_user(payload: Dict[str, Any] = Depends(JWTBearer()), db: Session = Depends(get_db)) -> User:
    email = payload.get("sub")
    if email is None:
        raise HTTPException(status_code=403, detail="Invalid token payload.")
    
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user.")
    return user

# Route handlers
@app.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    try:
        # Check if user already exists
        existing_user = db.query(User).filter(User.email == user_data.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists."
            )
        
        # Hash password and create user
        hashed_password = hash_password(user_data.password)
        db_user = User(
            email=user_data.email,
            hashed_password=hashed_password,
            full_name=user_data.full_name
        )
        
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        
        logger.info(f"User registered successfully: {user_data.email}")
        return db_user
        
    except IntegrityError:
        db.rollback()
        logger.error(f"Integrity error during registration for: {user_data.email}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists."
        )
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during registration: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during registration."
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error during registration: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error."
        )

@app.post("/login", response_model=TokenResponse)
async def login(login_data: LoginRequest, db: Session = Depends(get_db)):
    try:
        user = db.query(User).filter(User.email == login_data.email).first()
        if not user or not verify_password(login_data.password, user.hashed_password):
            logger.warning(f"Failed login attempt for: {login_data.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password."
            )
        
        if not user.is_active:
            logger.warning(f"Login attempt for inactive user: {login_data.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is deactivated."
            )
        
        access_token = create_access_token({"sub": user.email})
        refresh_token = create_refresh_token({"sub": user.email})
        
        logger.info(f"User logged in successfully: {login_data.email}")
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }
        
    except SQLAlchemyError as e:
        logger.error(f"Database error during login: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during login."
        )
    except Exception as e:
        logger.error(f"Unexpected error during login: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error."
        )

@app.post("/refresh", response_model=TokenResponse)
async def refresh_token(refresh_data: RefreshTokenRequest):
    try:
        payload = verify_token(refresh_data.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token."
            )
        
        if is_token_blacklisted(refresh_data.refresh_token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has been revoked."
            )
        
        email = payload.get("sub")
        if not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token payload."
            )
        
        # Add refresh token to blacklist
        expire_in = int((datetime.utcfromtimestamp(payload["exp"]) - datetime.utcnow()).total_seconds())
        add_token_to_blacklist(refresh_data.refresh_token, expire_in)
        
        access_token = create_access_token({"sub": email})
        new_refresh_token = create_refresh_token({"sub": email})
        
        logger.info(f"Token refreshed successfully for user: {email}")
        return {
            "access_token": access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer"
        }
        
    except JWTError:
        logger.warning("Invalid refresh token provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token."
        )
    except Exception as e:
        logger.error(f"Unexpected error during token refresh: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error."
        )

@app.post("/logout")
async def logout(
    authorization: Optional[str] = Header(None),
    refresh_token: Optional[str] = None
):
    try:
        tokens_to_blacklist = []
        
        if authorization and authorization.startswith("Bearer "):
            access_token = authorization[7:]
            payload = verify_token(access_token)
            expire_in = int((datetime.utcfromtimestamp(payload["exp"]) - datetime.utcnow()).total_seconds())
            tokens_to_blacklist.append((access_token, expire_in))
        
        if refresh_token:
            try:
                payload = verify_token(refresh_token)
                expire_in = int((datetime.utcfromtimestamp(payload["exp"]) - datetime.utcnow()).total_seconds())
                tokens_to_blacklist.append((refresh_token, expire_in))
            except HTTPException:
                pass  # Ignore invalid refresh tokens during logout
        
        for token, expire_in in tokens_to_blacklist:
            add_token_to_blacklist(token, expire_in)
        
        logger.info("User logged out successfully")
        return {"message": "Successfully logged out"}
        
    except Exception as e:
        logger.error(f"Unexpected error during logout: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during logout."
        )

@app.post("/password-reset-request")
async def password_reset_request(reset_data: PasswordResetRequest, db: Session = Depends(get_db)):
    try:
        user = db.query(User).filter(User.email == reset_data.email).first()
        if user:
            # Generate reset token
            reset_token = secrets.token_urlsafe(32)
            expires_at = datetime.utcnow() + timedelta(hours=1)
            
            # Store reset token in database
            db_reset_token = PasswordResetToken(
                email=reset_data.email,
                token=reset_token,
                expires_at=expires_at
            )
            db.add(db_reset_token)
            db.commit()
            
            # In production, you would send an email here
            logger.info(f"Password reset token generated for: {reset_data.email}")
        
        # Always return success to prevent email enumeration
        return {"message": "If the email exists, a reset link has been sent."}
        
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during password reset request: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error."
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error during password reset request: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error."
        )

@app.post("/password-reset-confirm")
async def password_reset_confirm(confirm_data: PasswordResetConfirm, db: Session = Depends(get_db)):
    try:
        # Find valid reset token
        reset_token = db.query(PasswordResetToken).filter(
            PasswordResetToken.token == confirm_data.token,
            PasswordResetToken.expires_at > datetime.utcnow(),
            PasswordResetToken.is_used == False
        ).first()
        
        if not reset_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset token."
            )
        
        # Find user
        user = db.query(User).filter(User.email == reset_token.email).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User not found."
            )
        
        # Update password
        user.hashed_password = hash_password(confirm_data.new_password)
        reset_token.is_used = True
        
        db.commit()
        
        # Invalidate all existing tokens for this user
        user_tokens = db.query(PasswordResetToken).filter(
            PasswordResetToken.email == user.email,
            PasswordResetToken.is_used == False
        ).all()
        
        for token in user_tokens:
            token.is_used = True
        
        db.commit()
        
        logger.info(f"Password reset successfully for: {user.email}")
        return {"message": "Password has been reset successfully."}
        
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during password reset confirm: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error."
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error during password reset confirm: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error."
        )

@app.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    return current_user

@app.post("/change-password")
async def change_password(
    old_password: str,
    new_password: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        if not verify_password(old_password, current_user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect."
            )
        
        if not PASSWORD_COMPLEXITY.match(new_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password must contain at least one uppercase letter, one lowercase letter, one number, and one special character"
            )
        
        current_user.hashed_password = hash_password(new_password)
        db.commit()
        
        logger.info(f"Password changed successfully for: {current_user.email}")
        return {"message": "Password changed successfully."}
        
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during password change: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error."
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error during password change: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error."
        )

# Health check endpoint
@app.get("/health")
async def health_check():
    try:
        # Test database connection
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        
        # Test Redis connection
        redis_client.ping()
        
        return {"status": "healthy", "database": "connected", "redis": "connected"}
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {"status": "unhealthy", "error": str(e)}, status.HTTP_503_SERVICE_UNAVAILABLE

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)