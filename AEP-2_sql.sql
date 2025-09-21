-- AEP-2: Authentication System SQL Schema
-- Creates tables for user authentication, sessions, and audit logging

-- Users table for storing authentication credentials
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    salt VARCHAR(50) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    failed_login_attempts INTEGER DEFAULT 0,
    last_login TIMESTAMP,
    account_locked_until TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User profiles table (separate from auth data)
CREATE TABLE user_profiles (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    phone_number VARCHAR(20),
    date_of_birth DATE,
    avatar_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- JWT tokens table for managing active sessions
CREATE TABLE jwt_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR(500) NOT NULL,
    refresh_token VARCHAR(500) NOT NULL,
    device_info VARCHAR(255),
    ip_address VARCHAR(45),
    expires_at TIMESTAMP NOT NULL,
    refresh_expires_at TIMESTAMP NOT NULL,
    is_revoked BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Password reset tokens table
CREATE TABLE password_reset_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR(100) NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    used BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Email verification tokens table
CREATE TABLE email_verification_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR(100) NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    used BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Audit log table for security events
CREATE TABLE audit_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    event_type VARCHAR(50) NOT NULL,
    description TEXT,
    ip_address VARCHAR(45),
    user_agent TEXT,
    success BOOLEAN DEFAULT FALSE,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance optimization
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_jwt_tokens_user_id ON jwt_tokens(user_id);
CREATE INDEX idx_jwt_tokens_token ON jwt_tokens(token);
CREATE INDEX idx_jwt_tokens_refresh_token ON jwt_tokens(refresh_token);
CREATE INDEX idx_password_reset_tokens_token ON password_reset_tokens(token);
CREATE INDEX idx_email_verification_tokens_token ON email_verification_tokens(token);
CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_event_type ON audit_logs(event_type);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers for automatic updated_at updates
CREATE TRIGGER update_users_updated_at 
    BEFORE UPDATE ON users 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_profiles_updated_at 
    BEFORE UPDATE ON user_profiles 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function to log authentication events
CREATE OR REPLACE FUNCTION log_auth_event(
    p_user_id INTEGER,
    p_event_type VARCHAR(50),
    p_description TEXT,
    p_ip_address VARCHAR(45),
    p_user_agent TEXT,
    p_success BOOLEAN,
    p_metadata JSONB DEFAULT NULL
) RETURNS VOID AS $$
BEGIN
    INSERT INTO audit_logs (
        user_id, event_type, description, ip_address, 
        user_agent, success, metadata
    ) VALUES (
        p_user_id, p_event_type, p_description, p_ip_address,
        p_user_agent, p_success, p_metadata
    );
END;
$$ LANGUAGE plpgsql;

-- Function to handle failed login attempts
CREATE OR REPLACE FUNCTION handle_failed_login(
    p_username VARCHAR(50),
    p_ip_address VARCHAR(45),
    p_user_agent TEXT
) RETURNS TABLE(user_id INTEGER, is_locked BOOLEAN, failed_attempts INTEGER) AS $$
DECLARE
    v_user_id INTEGER;
    v_failed_attempts INTEGER;
    v_is_locked BOOLEAN;
BEGIN
    -- Get user ID
    SELECT id, failed_login_attempts, 
           (account_locked_until IS NOT NULL AND account_locked_until > CURRENT_TIMESTAMP)
    INTO v_user_id, v_failed_attempts, v_is_locked
    FROM users 
    WHERE username = p_username OR email = p_username;
    
    IF v_user_id IS NOT NULL THEN
        -- Increment failed attempts
        v_failed_attempts := v_failed_attempts + 1;
        
        -- Lock account after 5 failed attempts for 30 minutes
        IF v_failed_attempts >= 5 THEN
            UPDATE users 
            SET failed_login_attempts = v_failed_attempts,
                account_locked_until = CURRENT_TIMESTAMP + INTERVAL '30 minutes'
            WHERE id = v_user_id;
            v_is_locked := TRUE;
        ELSE
            UPDATE users 
            SET failed_login_attempts = v_failed_attempts
            WHERE id = v_user_id;
        END IF;
        
        -- Log the failed attempt
        PERFORM log_auth_event(
            v_user_id, 
            'LOGIN_FAILED', 
            'Failed login attempt', 
            p_ip_address, 
            p_user_agent, 
            FALSE,
            jsonb_build_object('failed_attempts', v_failed_attempts)
        );
    END IF;
    
    RETURN QUERY SELECT v_user_id, v_is_locked, v_failed_attempts;
END;
$$ LANGUAGE plpgsql;

-- Function to handle successful login
CREATE OR REPLACE FUNCTION handle_successful_login(
    p_user_id INTEGER,
    p_ip_address VARCHAR(45),
    p_user_agent TEXT
) RETURNS VOID AS $$
BEGIN
    -- Reset failed attempts and unlock account
    UPDATE users 
    SET failed_login_attempts = 0,
        account_locked_until = NULL,
        last_login = CURRENT_TIMESTAMP
    WHERE id = p_user_id;
    
    -- Log the successful login
    PERFORM log_auth_event(
        p_user_id, 
        'LOGIN_SUCCESS', 
        'Successful login', 
        p_ip_address, 
        p_user_agent, 
        TRUE
    );
END;
$$ LANGUAGE plpgsql;

-- Function to create a new user with validation
CREATE OR REPLACE FUNCTION create_user(
    p_username VARCHAR(50),
    p_email VARCHAR(255),
    p_password_hash VARCHAR(255),
    p_salt VARCHAR(50),
    p_first_name VARCHAR(100) DEFAULT NULL,
    p_last_name VARCHAR(100) DEFAULT NULL,
    p_ip_address VARCHAR(45) DEFAULT NULL,
    p_user_agent TEXT DEFAULT NULL
) RETURNS TABLE(user_id INTEGER, success BOOLEAN, message TEXT) AS $$
DECLARE
    v_user_id INTEGER;
    v_email_exists BOOLEAN;
    v_username_exists BOOLEAN;
BEGIN
    -- Check if email already exists
    SELECT EXISTS(SELECT 1 FROM users WHERE email = p_email) INTO v_email_exists;
    IF v_email_exists THEN
        RETURN QUERY SELECT NULL::INTEGER, FALSE, 'Email already exists';
        RETURN;
    END IF;
    
    -- Check if username already exists
    SELECT EXISTS(SELECT 1 FROM users WHERE username = p_username) INTO v_username_exists;
    IF v_username_exists THEN
        RETURN QUERY SELECT NULL::INTEGER, FALSE, 'Username already exists';
        RETURN;
    END IF;
    
    -- Insert new user
    INSERT INTO users (username, email, password_hash, salt)
    VALUES (p_username, p_email, p_password_hash, p_salt)
    RETURNING id INTO v_user_id;
    
    -- Create user profile
    INSERT INTO user_profiles (user_id, first_name, last_name)
    VALUES (v_user_id, p_first_name, p_last_name);
    
    -- Log registration event
    PERFORM log_auth_event(
        v_user_id, 
        'REGISTRATION', 
        'User registration', 
        p_ip_address, 
        p_user_agent, 
        TRUE
    );
    
    RETURN QUERY SELECT v_user_id, TRUE, 'User created successfully';
END;
$$ LANGUAGE plpgsql;

-- Function to store JWT token
CREATE OR REPLACE FUNCTION store_jwt_token(
    p_user_id INTEGER,
    p_token VARCHAR(500),
    p_refresh_token VARCHAR(500),
    p_device_info VARCHAR(255),
    p_ip_address VARCHAR(45),
    p_expires_at TIMESTAMP,
    p_refresh_expires_at TIMESTAMP
) RETURNS VOID AS $$
BEGIN
    -- Revoke any existing tokens for the same device
    UPDATE jwt_tokens 
    SET is_revoked = TRUE 
    WHERE user_id = p_user_id 
    AND device_info = p_device_info 
    AND is_revoked = FALSE;
    
    -- Store new token
    INSERT INTO jwt_tokens (
        user_id, token, refresh_token, device_info, 
        ip_address, expires_at, refresh_expires_at
    ) VALUES (
        p_user_id, p_token, p_refresh_token, p_device_info,
        p_ip_address, p_expires_at, p_refresh_expires_at
    );
    
    -- Log token creation
    PERFORM log_auth_event(
        p_user_id, 
        'TOKEN_CREATED', 
        'JWT token created', 
        p_ip_address, 
        p_device_info, 
        TRUE
    );
END;
$$ LANGUAGE plpgsql;

-- Function to validate JWT token
CREATE OR REPLACE FUNCTION validate_jwt_token(
    p_token VARCHAR(500)
) RETURNS TABLE(user_id INTEGER, is_valid BOOLEAN, message TEXT) AS $$
DECLARE
    v_user_id INTEGER;
    v_expires_at TIMESTAMP;
    v_is_revoked BOOLEAN;
BEGIN
    SELECT user_id, expires_at, is_revoked 
    INTO v_user_id, v_expires_at, v_is_revoked
    FROM jwt_tokens 
    WHERE token = p_token;
    
    IF v_user_id IS NULL THEN
        RETURN QUERY SELECT NULL::INTEGER, FALSE, 'Token not found';
    ELSIF v_is_revoked THEN
        RETURN QUERY SELECT v_user_id, FALSE, 'Token revoked';
    ELSIF v_expires_at < CURRENT_TIMESTAMP THEN
        RETURN QUERY SELECT v_user_id, FALSE, 'Token expired';
    ELSE
        RETURN QUERY SELECT v_user_id, TRUE, 'Token valid';
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Function to revoke JWT token
CREATE OR REPLACE FUNCTION revoke_jwt_token(
    p_token VARCHAR(500),
    p_ip_address VARCHAR(45),
    p_user_agent TEXT
) RETURNS BOOLEAN AS $$
DECLARE
    v_user_id INTEGER;
BEGIN
    UPDATE jwt_tokens 
    SET is_revoked = TRUE 
    WHERE token = p_token 
    RETURNING user_id INTO v_user_id;
    
    IF v_user_id IS NOT NULL THEN
        PERFORM log_auth_event(
            v_user_id, 
            'TOKEN_REVOKED', 
            'JWT token revoked', 
            p_ip_address, 
            p_user_agent, 
            TRUE
        );
        RETURN TRUE;
    END IF;
    
    RETURN FALSE;
END;
$$ LANGUAGE plpgsql;

-- Function to create password reset token
CREATE OR REPLACE FUNCTION create_password_reset_token(
    p_email VARCHAR(255),
    p_token VARCHAR(100),
    p_expires_at TIMESTAMP,
    p_ip_address VARCHAR(45),
    p_user_agent TEXT
) RETURNS TABLE(success BOOLEAN, message TEXT) AS $$
DECLARE
    v_user_id INTEGER;
BEGIN
    -- Get user ID from email
    SELECT id INTO v_user_id FROM users WHERE email = p_email AND is_active = TRUE;
    
    IF v_user_id IS NULL THEN
        RETURN QUERY SELECT FALSE, 'User not found or inactive';
        RETURN;
    END IF;
    
    -- Invalidate any existing reset tokens
    UPDATE password_reset_tokens 
    SET used = TRUE 
    WHERE user_id = v_user_id AND used = FALSE;
    
    -- Create new reset token
    INSERT INTO password_reset_tokens (user_id, token, expires_at)
    VALUES (v_user_id, p_token, p_expires_at);
    
    -- Log token creation
    PERFORM log_auth_event(
        v_user_id, 
        'PASSWORD_RESET_REQUESTED', 
        'Password reset token created', 
        p_ip_address, 
        p_user_agent, 
        TRUE
    );
    
    RETURN QUERY SELECT TRUE, 'Password reset token created successfully';
END;
$$ LANGUAGE plpgsql;

-- Function to use password reset token
CREATE OR REPLACE FUNCTION use_password_reset_token(
    p_token VARCHAR(100),
    p_new_password_hash VARCHAR(255),
    p_new_salt VARCHAR(50),
    p_ip_address VARCHAR(45),
    p_user_agent TEXT
) RETURNS TABLE(success BOOLEAN, message TEXT) AS $$
DECLARE
    v_user_id INTEGER;
    v_expires_at TIMESTAMP;
    v_used BOOLEAN;
BEGIN
    SELECT user_id, expires_at, used 
    INTO v_user_id, v_expires_at, v_used
    FROM password_reset_tokens 
    WHERE token = p_token;
    
    IF v_user_id IS NULL THEN
        RETURN QUERY SELECT FALSE, 'Invalid reset token';
    ELSIF v_used THEN
        RETURN QUERY SELECT FALSE, 'Reset token already used';
    ELSIF v_expires_at < CURRENT_TIMESTAMP THEN
        RETURN QUERY SELECT FALSE, 'Reset token expired';
    ELSE
        -- Mark token as used
        UPDATE password_reset_tokens SET used = TRUE WHERE token = p_token;
        
        -- Update user password
        UPDATE users 
        SET password_hash = p_new_password_hash, 
            salt = p_new_salt,
            failed_login_attempts = 0,
            account_locked_until = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = v_user_id;
        
        -- Revoke all active tokens
        UPDATE jwt_tokens SET is_revoked = TRUE WHERE user_id = v_user_id;
        
        -- Log password reset
        PERFORM log_auth_event(
            v_user_id, 
            'PASSWORD_RESET', 
            'Password reset successfully', 
            p_ip_address, 
            p_user_agent, 
            TRUE
        );
        
        RETURN QUERY SELECT TRUE, 'Password reset successfully';
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Function to create email verification token
CREATE OR REPLACE FUNCTION create_email_verification_token(
    p_user_id INTEGER,
    p_token VARCHAR(100),
    p_expires_at TIMESTAMP,
    p_ip_address VARCHAR(45),
    p_user_agent TEXT
) RETURNS VOID AS $$
BEGIN
    -- Invalidate any existing verification tokens
    UPDATE email_verification_tokens 
    SET used = TRUE 
    WHERE user_id = p_user_id AND used = FALSE;
    
    -- Create new verification token
    INSERT INTO email_verification_tokens (user_id, token, expires_at)
    VALUES (p_user_id, p_token, p_expires_at);
    
    -- Log token creation
    PERFORM log_auth_event(
        p_user_id, 
        'EMAIL_VERIFICATION_SENT', 
        'Email verification token created', 
        p_ip_address, 
        p_user_agent, 
        TRUE
    );
END;
$$ LANGUAGE plpgsql;

-- Function to verify email using token
CREATE OR REPLACE FUNCTION verify_email(
    p_token VARCHAR(100),
    p_ip_address VARCHAR(45),
    p_user_agent TEXT
) RETURNS TABLE(success BOOLEAN, message TEXT) AS $$
DECLARE
    v_user_id INTEGER;
    v_expires_at TIMESTAMP;
    v_used BOOLEAN;
BEGIN
    SELECT user_id, expires_at, used 
    INTO v_user_id, v_expires_at, v_used
    FROM email_verification_tokens 
    WHERE token = p_token;
    
    IF v_user_id IS NULL THEN
        RETURN QUERY SELECT FALSE, 'Invalid verification token';
    ELSIF v_used THEN
        RETURN QUERY SELECT FALSE, 'Verification token already used';
    ELSIF v_expires_at < CURRENT_TIMESTAMP THEN
        RETURN QUERY SELECT FALSE, 'Verification token expired';
    ELSE
        -- Mark token as used
        UPDATE email_verification_tokens SET used = TRUE WHERE token = p_token;
        
        -- Verify user email
        UPDATE users 
        SET is_verified = TRUE,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = v_user_id;
        
        -- Log email verification
        PERFORM log_auth_event(
            v_user_id, 
            'EMAIL_VERIFIED', 
            'Email verified successfully', 
            p_ip_address, 
            p_user_agent, 
            TRUE
        );
        
        RETURN QUERY SELECT TRUE, 'Email verified successfully';
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Function to get user by ID with profile
CREATE OR REPLACE FUNCTION get_user_with_profile(
    p_user_id INTEGER
) RETURNS TABLE(
    user_id INTEGER,
    username VARCHAR(50),
    email VARCHAR(255),
    is_active BOOLEAN,
    is_verified BOOLEAN,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    phone_number VARCHAR(20),
    date_of_birth DATE,
    avatar_url VARCHAR(500),
    created_at TIMESTAMP
) AS $$
BEGIN
    RETURN QUERY 
    SELECT 
        u.id,
        u.username,
        u.email,
        u.is_active,
        u.is_verified,
        up.first_name,
        up.last_name,
        up.phone_number,
        up.date_of_birth,
        up.avatar_url,
        u.created_at
    FROM users u
    LEFT JOIN user_profiles up ON u.id = up.user_id
    WHERE u.id = p_user_id;
END;
$$ LANGUAGE plpgsql;

-- Function to clean up expired tokens (should be run periodically)
CREATE OR REPLACE FUNCTION cleanup_expired_tokens() RETURNS INTEGER AS $$
DECLARE
    v_count INTEGER;
BEGIN
    -- Clean up expired JWT tokens
    DELETE FROM jwt_tokens 
    WHERE expires_at < CURRENT_TIMESTAMP - INTERVAL '7 days';
    
    GET DIAGNOSTICS v_count = ROW_COUNT;
    
    -- Clean up expired password reset tokens
    DELETE FROM password_reset_tokens 
    WHERE expires_at < CURRENT_TIMESTAMP - INTERVAL '1 day';
    
    GET DIAGNOSTICS v_count = v_count + ROW_COUNT;
    
    -- Clean up expired email verification tokens
    DELETE FROM email_verification_tokens 
    WHERE expires_at < CURRENT_TIMESTAMP - INTERVAL '1 day';
    
    GET DIAGNOSTICS v_count = v_count + ROW_COUNT;
    
    RETURN v_count;
END;
$$ LANGUAGE plpgsql;

-- Insert default admin user (for testing purposes - remove in production)
INSERT INTO users (username, email, password_hash, salt, is_active, is_verified)
VALUES (
    'admin',
    'admin@example.com',
    -- password: admin123 (hashed with bcrypt)
    '$2a$10$N9qo8uLOickgx2ZMRZoMye3Z6gY8Yq1Q1Q1Q1Q1Q1Q1Q1Q1Q1Q1Q1',
    'salt123',
    TRUE,
    TRUE
) ON CONFLICT DO NOTHING;