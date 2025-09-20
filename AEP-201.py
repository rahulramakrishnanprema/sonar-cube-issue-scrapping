# Issue: AEP-201
# Generated: 2025-09-20T06:20:29.494860
# Thread: f1d8c784
# Enhanced: LangChain structured generation
# AI Model: deepseek/deepseek-chat-v3.1:free
# Max Length: 25000 characters

import os
import re
import logging
import bcrypt
import jwt
import uuid
import datetime
from datetime import timezone
from typing import Optional, Dict, Any, Tuple
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
from functools import wraps
from flask import Flask, request, jsonify, current_app
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import SQLAlchemyError
from marshmallow import Schema, fields, ValidationError, validate, validates_schema

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'fallback-secret-key-for-dev')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///aep.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = datetime.timedelta(hours=1)
app.config['JWT_REFRESH_TOKEN_EXPIRES'] = datetime.timedelta(days=7)
app.config['SMTP_SERVER'] = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
app.config['SMTP_PORT'] = int(os.environ.get('SMTP_PORT', 587))
app.config['SMTP_USERNAME'] = os.environ.get('SMTP_USERNAME', '')
app.config['SMTP_PASSWORD'] = os.environ.get('SMTP_PASSWORD', '')

db = SQLAlchemy(app)

# Database Models
class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(128), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    is_verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=datetime.datetime.now(timezone.utc), 
                          onupdate=datetime.datetime.now(timezone.utc))
    
    def set_password(self, password: str) -> None:
        salt = bcrypt.gensalt()
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    def check_password(self, password: str) -> bool:
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))

class RefreshToken(db.Model):
    __tablename__ = 'refresh_tokens'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)
    token = db.Column(db.String(512), nullable=False, unique=True, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.now(timezone.utc))
    revoked = db.Column(db.Boolean, default=False)
    
    user = db.relationship('User', backref=db.backref('refresh_tokens', lazy=True))

class PasswordResetToken(db.Model):
    __tablename__ = 'password_reset_tokens'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)
    token = db.Column(db.String(128), nullable=False, unique=True, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.now(timezone.utc))
    
    user = db.relationship('User', backref=db.backref('password_reset_tokens', lazy=True))

# Schemas
class RegistrationSchema(Schema):
    email = fields.Email(required=True)
    password = fields.Str(required=True, validate=validate.Length(min=8))
    confirm_password = fields.Str(required=True)
    
    @validates_schema
    def validate_passwords(self, data, **kwargs):
        if data['password'] != data['confirm_password']:
            raise ValidationError("Passwords do not match", "confirm_password")
        
        if not re.match(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]', data['password']):
            raise ValidationError("Password must contain at least one uppercase letter, one lowercase letter, one number and one special character", "password")

class LoginSchema(Schema):
    email = fields.Email(required=True)
    password = fields.Str(required=True)

class PasswordResetRequestSchema(Schema):
    email = fields.Email(required=True)

class PasswordResetSchema(Schema):
    token = fields.Str(required=True)
    password = fields.Str(required=True, validate=validate.Length(min=8))
    confirm_password = fields.Str(required=True)
    
    @validates_schema
    def validate_passwords(self, data, **kwargs):
        if data['password'] != data['confirm_password']:
            raise ValidationError("Passwords do not match", "confirm_password")
        
        if not re.match(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]', data['password']):
            raise ValidationError("Password must contain at least one uppercase letter, one lowercase letter, one number and one special character", "password")

class RefreshTokenSchema(Schema):
    refresh_token = fields.Str(required=True)

# Utility Functions
def generate_jwt_tokens(user_id: str) -> Tuple[str, str]:
    access_token = jwt.encode({
        'user_id': user_id,
        'exp': datetime.datetime.now(timezone.utc) + current_app.config['JWT_ACCESS_TOKEN_EXPIRES'],
        'iat': datetime.datetime.now(timezone.utc),
        'type': 'access'
    }, current_app.config['SECRET_KEY'], algorithm='HS256')
    
    refresh_token = jwt.encode({
        'user_id': user_id,
        'exp': datetime.datetime.now(timezone.utc) + current_app.config['JWT_REFRESH_TOKEN_EXPIRES'],
        'iat': datetime.datetime.now(timezone.utc),
        'type': 'refresh',
        'jti': str(uuid.uuid4())
    }, current_app.config['SECRET_KEY'], algorithm='HS256')
    
    return access_token, refresh_token

def store_refresh_token(user_id: str, token: str) -> None:
    try:
        expires_at = datetime.datetime.now(timezone.utc) + current_app.config['JWT_REFRESH_TOKEN_EXPIRES']
        refresh_token = RefreshToken(
            user_id=user_id,
            token=token,
            expires_at=expires_at
        )
        db.session.add(refresh_token)
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Failed to store refresh token: {str(e)}")
        raise

def revoke_refresh_token(token: str) -> None:
    try:
        refresh_token = RefreshToken.query.filter_by(token=token).first()
        if refresh_token:
            refresh_token.revoked = True
            db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Failed to revoke refresh token: {str(e)}")
        raise

def send_email(to_email: str, subject: str, body: str) -> bool:
    try:
        msg = MIMEMultipart()
        msg['From'] = current_app.config['SMTP_USERNAME']
        msg['To'] = to_email
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'html'))
        
        server = smtplib.SMTP(current_app.config['SMTP_SERVER'], current_app.config['SMTP_PORT'])
        server.starttls()
        server.login(current_app.config['SMTP_USERNAME'], current_app.config['SMTP_PASSWORD'])
        server.send_message(msg)
        server.quit()
        
        return True
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}")
        return False

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            try:
                auth_header = request.headers['Authorization']
                token = auth_header.split(" ")[1]
            except IndexError:
                return jsonify({'error': 'Bearer token malformed'}), 401
        
        if not token:
            return jsonify({'error': 'Token is missing'}), 401
        
        try:
            data = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
            if data['type'] != 'access':
                return jsonify({'error': 'Invalid token type'}), 401
                
            current_user = User.query.get(data['user_id'])
            if not current_user or not current_user.is_active:
                return jsonify({'error': 'User not found or inactive'}), 401
                
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Token is invalid'}), 401
        
        return f(current_user, *args, **kwargs)
    
    return decorated

# Routes
@app.route('/api/auth/register', methods=['POST'])
def register():
    try:
        data = RegistrationSchema().load(request.get_json())
    except ValidationError as err:
        return jsonify({'error': 'Validation failed', 'details': err.messages}), 400
    
    try:
        if User.query.filter_by(email=data['email']).first():
            return jsonify({'error': 'User already exists'}), 409
        
        user = User(email=data['email'])
        user.set_password(data['password'])
        
        db.session.add(user)
        db.session.commit()
        
        # Send verification email
        verification_token = str(uuid.uuid4())
        verification_url = f"{request.host_url}verify-email?token={verification_token}"
        email_body = f"""
        <h1>Welcome to AEP</h1>
        <p>Please click the link below to verify your email address:</p>
        <a href="{verification_url}">Verify Email</a>
        """
        
        if not send_email(data['email'], "Verify your AEP account", email_body):
            logger.warning(f"Failed to send verification email to {data['email']}")
        
        return jsonify({'message': 'User created successfully. Please check your email for verification.'}), 201
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Registration failed: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    try:
        data = LoginSchema().load(request.get_json())
    except ValidationError as err:
        return jsonify({'error': 'Validation failed', 'details': err.messages}), 400
    
    try:
        user = User.query.filter_by(email=data['email']).first()
        
        if not user or not user.check_password(data['password']):
            return jsonify({'error': 'Invalid credentials'}), 401
        
        if not user.is_active:
            return jsonify({'error': 'Account is deactivated'}), 401
        
        access_token, refresh_token = generate_jwt_tokens(user.id)
        store_refresh_token(user.id, refresh_token)
        
        return jsonify({
            'access_token': access_token,
            'refresh_token': refresh_token,
            'user_id': user.id,
            'email': user.email
        }), 200
        
    except SQLAlchemyError as e:
        logger.error(f"Login failed: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/auth/refresh', methods=['POST'])
def refresh_token():
    try:
        data = RefreshTokenSchema().load(request.get_json())
    except ValidationError as err:
        return jsonify({'error': 'Validation failed', 'details': err.messages}), 400
    
    try:
        # Verify refresh token
        try:
            payload = jwt.decode(data['refresh_token'], current_app.config['SECRET_KEY'], algorithms=['HS256'])
            if payload['type'] != 'refresh':
                return jsonify({'error': 'Invalid token type'}), 401
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Refresh token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid refresh token'}), 401
        
        # Check if refresh token exists in database and is not revoked
        refresh_token_record = RefreshToken.query.filter_by(
            token=data['refresh_token'], 
            revoked=False
        ).first()
        
        if not refresh_token_record or refresh_token_record.expires_at < datetime.datetime.now(timezone.utc):
            return jsonify({'error': 'Invalid or expired refresh token'}), 401
        
        # Generate new tokens
        access_token, new_refresh_token = generate_jwt_tokens(payload['user_id'])
        
        # Revoke old refresh token and store new one
        revoke_refresh_token(data['refresh_token'])
        store_refresh_token(payload['user_id'], new_refresh_token)
        
        return jsonify({
            'access_token': access_token,
            'refresh_token': new_refresh_token
        }), 200
        
    except SQLAlchemyError as e:
        logger.error(f"Token refresh failed: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/auth/logout', methods=['POST'])
@token_required
def logout(current_user):
    try:
        data = RefreshTokenSchema().load(request.get_json())
        revoke_refresh_token(data['refresh_token'])
        return jsonify({'message': 'Successfully logged out'}), 200
    except ValidationError as err:
        return jsonify({'error': 'Validation failed', 'details': err.messages}), 400
    except SQLAlchemyError as e:
        logger.error(f"Logout failed: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/auth/password-reset-request', methods=['POST'])
def password_reset_request():
    try:
        data = PasswordResetRequestSchema().load(request.get_json())
    except ValidationError as err:
        return jsonify({'error': 'Validation failed', 'details': err.messages}), 400
    
    try:
        user = User.query.filter_by(email=data['email']).first()
        if user and user.is_active:
            # Create password reset token
            reset_token = str(uuid.uuid4())
            expires_at = datetime.datetime.now(timezone.utc) + datetime.timedelta(hours=1)
            
            reset_token_record = PasswordResetToken(
                user_id=user.id,
                token=reset_token,
                expires_at=expires_at
            )
            
            db.session.add(reset_token_record)
            db.session.commit()
            
            # Send reset email
            reset_url = f"{request.host_url}reset-password?token={reset_token}"
            email_body = f"""
            <h1>Password Reset Request</h1>
            <p>Click the link below to reset your password:</p>
            <a href="{reset_url}">Reset Password</a>
            <p>This link will expire in 1 hour.</p>
            """
            
            if not send_email(data['email'], "Reset your AEP password", email_body):
                logger.warning(f"Failed to send password reset email to {data['email']}")
        
        return jsonify({'message': 'If the email exists, a password reset link has been sent'}), 200
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Password reset request failed: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/auth/password-reset', methods=['POST'])
def password_reset():
    try:
        data = PasswordResetSchema().load(request.get_json())
    except ValidationError as err:
        return jsonify({'error': 'Validation failed', 'details': err.messages}), 400
    
    try:
        # Validate reset token
        reset_token_record = PasswordResetToken.query.filter_by(
            token=data['token'],
            used=False
        ).first()
        
        if not reset_token_record or reset_token_record.expires_at < datetime.datetime.now(timezone.utc):
            return jsonify({'error': 'Invalid or expired reset token'}), 400
        
        # Update password
        user = User.query.get(reset_token_record.user_id)
        user.set_password(data['password'])
        
        # Mark token as used
        reset_token_record.used = True
        
        db.session.commit()
        
        return jsonify({'message': 'Password successfully reset'}), 200
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Password reset failed: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/auth/verify-email', methods=['POST'])
@token_required
def verify_email(current_user):
    try:
        if current_user.is_verified:
            return jsonify({'message': 'Email already verified'}), 200
        
        current_user.is_verified = True
        db.session.commit()
        
        return jsonify({'message': 'Email successfully verified'}), 200
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Email verification failed: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/auth/me', methods=['GET'])
@token_required
def get_current_user(current_user):
    return jsonify({
        'user_id': current_user.id,
        'email': current_user.email,
        'is_verified': current_user.is_verified,
        'created_at': current_user.created_at.isoformat()
    }), 200

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({'error': 'Internal server error'}), 500

# Database initialization
def init_db():
    db.create_all()

if __name__ == '__main__':
    init_db()
    app.run(debug=os.environ.get('FLASK_DEBUG', False))