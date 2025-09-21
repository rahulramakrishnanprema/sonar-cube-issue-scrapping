# Generated for DefaultProject-201 | 2025-09-21 06:33:50 | Developer Agent v2.0
# AutoFlow-Dashboard Enhanced Code Generation
# Thread: d44a8b52 | LangChain: Template-Enhanced Generation
# Workflow Stage: Code Generation (NO PR creation)

-- DefaultProject-201: User Authentication System SQL Schema
-- Created: 2025-09-21
-- Description: Complete user authentication system including registration, login, password reset, and JWT token management

-- Drop existing tables if they exist (for clean setup)
DROP TABLE IF EXISTS user_password_reset_tokens;
DROP TABLE IF EXISTS user_refresh_tokens;
DROP TABLE IF EXISTS user_login_attempts;
DROP TABLE IF EXISTS users;

-- Users table for storing user registration information
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    is_email_verified BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    is_locked BOOLEAN DEFAULT FALSE,
    failed_login_attempts INTEGER DEFAULT 0,
    last_login_at TIMESTAMP WITH TIME ZONE,
    email_verification_token VARCHAR(255),
    email_verification_expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_email_format CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'),
    CONSTRAINT chk_username_length CHECK (LENGTH(username) >= 3 AND LENGTH(username) <= 50),
    CONSTRAINT chk_password_length CHECK (LENGTH(password_hash) >= 60)
);

-- User login attempts tracking for security
CREATE TABLE user_login_attempts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    ip_address VARCHAR(45) NOT NULL,
    user_agent TEXT,
    attempt_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_successful BOOLEAN DEFAULT FALSE,
    failure_reason VARCHAR(255),
    CONSTRAINT fk_login_attempt_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Refresh tokens for JWT token management
CREATE TABLE user_refresh_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    token VARCHAR(255) NOT NULL UNIQUE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    revoked_at TIMESTAMP WITH TIME ZONE,
    replaced_by_token VARCHAR(255),
    CONSTRAINT fk_refresh_token_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Password reset tokens table
CREATE TABLE user_password_reset_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    token VARCHAR(255) NOT NULL UNIQUE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_used BOOLEAN DEFAULT FALSE,
    used_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT fk_password_reset_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Indexes for performance optimization
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_is_active ON users(is_active);
CREATE INDEX idx_refresh_tokens_token ON user_refresh_tokens(token);
CREATE INDEX idx_refresh_tokens_user_id ON user_refresh_tokens(user_id);
CREATE INDEX idx_refresh_tokens_expires_at ON user_refresh_tokens(expires_at);
CREATE INDEX idx_password_reset_tokens_token ON user_password_reset_tokens(token);
CREATE INDEX idx_password_reset_tokens_user_id ON user_password_reset_tokens(user_id);
CREATE INDEX idx_login_attempts_user_id ON user_login_attempts(user_id);
CREATE INDEX idx_login_attempts_attempt_time ON user_login_attempts(attempt_time);

-- Function to update updated_at timestamp automatically
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for automatic updated_at updates on users table
CREATE TRIGGER trigger_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Function to handle user registration with validation
CREATE OR REPLACE FUNCTION register_user(
    p_email VARCHAR(255),
    p_username VARCHAR(50),
    p_password_hash VARCHAR(255),
    p_first_name VARCHAR(100),
    p_last_name VARCHAR(100)
)
RETURNS INTEGER AS $$
DECLARE
    v_user_id INTEGER;
BEGIN
    -- Validate input parameters
    IF p_email IS NULL OR p_username IS NULL OR p_password_hash IS NULL OR p_first_name IS NULL OR p_last_name IS NULL THEN
        RAISE EXCEPTION 'All registration fields are required';
    END IF;

    IF LENGTH(p_password_hash) < 60 THEN
        RAISE EXCEPTION 'Invalid password hash format';
    END IF;

    -- Check if email already exists
    IF EXISTS (SELECT 1 FROM users WHERE email = p_email) THEN
        RAISE EXCEPTION 'Email already registered';
    END IF;

    -- Check if username already exists
    IF EXISTS (SELECT 1 FROM users WHERE username = p_username) THEN
        RAISE EXCEPTION 'Username already taken';
    END IF;

    -- Insert new user
    INSERT INTO users (email, username, password_hash, first_name, last_name, email_verification_token)
    VALUES (p_email, p_username, p_password_hash, p_first_name, p_last_name, 
            encode(gen_random_bytes(32), 'hex'))
    RETURNING id INTO v_user_id;

    RETURN v_user_id;
EXCEPTION
    WHEN unique_violation THEN
        RAISE EXCEPTION 'User already exists with provided credentials';
    WHEN check_violation THEN
        RAISE EXCEPTION 'Invalid input data format';
    WHEN OTHERS THEN
        RAISE EXCEPTION 'Registration failed: %', SQLERRM;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to verify user credentials for login
CREATE OR REPLACE FUNCTION verify_user_credentials(
    p_identifier VARCHAR(255),
    p_password_hash VARCHAR(255)
)
RETURNS TABLE (
    user_id INTEGER,
    email VARCHAR(255),
    username VARCHAR(50),
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    is_email_verified BOOLEAN,
    is_active BOOLEAN,
    is_locked BOOLEAN
) AS $$
BEGIN
    -- Validate input
    IF p_identifier IS NULL OR p_password_hash IS NULL THEN
        RAISE EXCEPTION 'Email/username and password are required';
    END IF;

    -- Return user data if credentials match
    RETURN QUERY
    SELECT u.id, u.email, u.username, u.first_name, u.last_name, 
           u.is_email_verified, u.is_active, u.is_locked
    FROM users u
    WHERE (u.email = p_identifier OR u.username = p_identifier)
      AND u.password_hash = p_password_hash
      AND u.is_active = TRUE;
    
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Invalid credentials or user not active';
    END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to record login attempt
CREATE OR REPLACE FUNCTION record_login_attempt(
    p_user_id INTEGER,
    p_ip_address VARCHAR(45),
    p_user_agent TEXT,
    p_is_successful BOOLEAN,
    p_failure_reason VARCHAR(255)
)
RETURNS VOID AS $$
BEGIN
    INSERT INTO user_login_attempts (user_id, ip_address, user_agent, is_successful, failure_reason)
    VALUES (p_user_id, p_ip_address, p_user_agent, p_is_successful, p_failure_reason);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to update user login status
CREATE OR REPLACE FUNCTION update_user_login_status(
    p_user_id INTEGER,
    p_is_successful BOOLEAN
)
RETURNS VOID AS $$
BEGIN
    IF p_is_successful THEN
        -- Reset failed attempts and update last login on successful login
        UPDATE users 
        SET failed_login_attempts = 0, 
            last_login_at = CURRENT_TIMESTAMP,
            is_locked = FALSE
        WHERE id = p_user_id;
    ELSE
        -- Increment failed attempts and potentially lock account
        UPDATE users 
        SET failed_login_attempts = failed_login_attempts + 1,
            is_locked = (failed_login_attempts + 1 >= 5)
        WHERE id = p_user_id;
    END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to create refresh token
CREATE OR REPLACE FUNCTION create_refresh_token(
    p_user_id INTEGER,
    p_token VARCHAR(255),
    p_expires_at TIMESTAMP WITH TIME ZONE
)
RETURNS INTEGER AS $$
DECLARE
    v_token_id INTEGER;
BEGIN
    INSERT INTO user_refresh_tokens (user_id, token, expires_at)
    VALUES (p_user_id, p_token, p_expires_at)
    RETURNING id INTO v_token_id;
    
    RETURN v_token_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to revoke refresh token
CREATE OR REPLACE FUNCTION revoke_refresh_token(
    p_token VARCHAR(255),
    p_replaced_by_token VARCHAR(255) DEFAULT NULL
)
RETURNS VOID AS $$
BEGIN
    UPDATE user_refresh_tokens 
    SET revoked_at = CURRENT_TIMESTAMP,
        replaced_by_token = p_replaced_by_token
    WHERE token = p_token;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to validate refresh token
CREATE OR REPLACE FUNCTION validate_refresh_token(
    p_token VARCHAR(255)
)
RETURNS TABLE (
    user_id INTEGER,
    is_valid BOOLEAN,
    is_revoked BOOLEAN,
    is_expired BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        rt.user_id,
        (rt.revoked_at IS NULL AND rt.expires_at > CURRENT_TIMESTAMP) AS is_valid,
        (rt.revoked_at IS NOT NULL) AS is_revoked,
        (rt.expires_at <= CURRENT_TIMESTAMP) AS is_expired
    FROM user_refresh_tokens rt
    WHERE rt.token = p_token;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to create password reset token
CREATE OR REPLACE FUNCTION create_password_reset_token(
    p_user_id INTEGER,
    p_token VARCHAR(255),
    p_expires_at TIMESTAMP WITH TIME ZONE
)
RETURNS INTEGER AS $$
DECLARE
    v_token_id INTEGER;
BEGIN
    -- Invalidate any existing tokens for this user
    UPDATE user_password_reset_tokens 
    SET is_used = TRUE,
        used_at = CURRENT_TIMESTAMP
    WHERE user_id = p_user_id AND is_used = FALSE;
    
    -- Create new token
    INSERT INTO user_password_reset_tokens (user_id, token, expires_at)
    VALUES (p_user_id, p_token, p_expires_at)
    RETURNING id INTO v_token_id;
    
    RETURN v_token_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to validate password reset token
CREATE OR REPLACE FUNCTION validate_password_reset_token(
    p_token VARCHAR(255
)
RETURNS TABLE (
    user_id INTEGER,
    is_valid BOOLEAN,
    is_used BOOLEAN,
    is_expired BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        prt.user_id,
        (prt.is_used = FALSE AND prt.expires_at > CURRENT_TIMESTAMP) AS is_valid,
        prt.is_used AS is_used,
        (prt.expires_at <= CURRENT_TIMESTAMP) AS is_expired
    FROM user_password_reset_tokens prt
    WHERE prt.token = p_token;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to use password reset token and update password
CREATE OR REPLACE FUNCTION use_password_reset_token(
    p_token VARCHAR(255),
    p_new_password_hash VARCHAR(255)
)
RETURNS VOID AS $$
DECLARE
    v_user_id INTEGER;
BEGIN
    -- Validate new password hash
    IF LENGTH(p_new_password_hash) < 60 THEN
        RAISE EXCEPTION 'Invalid password hash format';
    END IF;

    -- Get user ID from token and mark token as used
    UPDATE user_password_reset_tokens 
    SET is_used = TRUE,
        used_at = CURRENT_TIMESTAMP
    WHERE token = p_token 
      AND is_used = FALSE 
      AND expires_at > CURRENT_TIMESTAMP
    RETURNING user_id INTO v_user_id;

    IF v_user_id IS NULL THEN
        RAISE EXCEPTION 'Invalid or expired reset token';
    END IF;

    -- Update user password
    UPDATE users 
    SET password_hash = p_new_password_hash,
        failed_login_attempts = 0,
        is_locked = FALSE
    WHERE id = v_user_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to verify email using verification token
CREATE OR REPLACE FUNCTION verify_email(
    p_token VARCHAR(255)
)
RETURNS VOID AS $$
DECLARE
    v_user_id INTEGER;
BEGIN
    -- Find user with matching verification token that hasn't expired
    UPDATE users 
    SET is_email_verified = TRUE,
        email_verification_token = NULL,
        email_verification_expires_at = NULL
    WHERE email_verification_token = p_token 
      AND email_verification_expires_at > CURRENT_TIMESTAMP
    RETURNING id INTO v_user_id;

    IF v_user_id IS NULL THEN
        RAISE EXCEPTION 'Invalid or expired verification token';
    END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to get user by ID
CREATE OR REPLACE FUNCTION get_user_by_id(
    p_user_id INTEGER
)
RETURNS TABLE (
    id INTEGER,
    email VARCHAR(255),
    username VARCHAR(50),
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    is_email_verified BOOLEAN,
    is_active BOOLEAN,
    is_locked BOOLEAN,
    created_at TIMESTAMP WITH TIME ZONE,
    last_login_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        u.id, u.email, u.username, u.first_name, u.last_name,
        u.is_email_verified, u.is_active, u.is_locked,
        u.created_at, u.last_login_at
    FROM users u
    WHERE u.id = p_user_id AND u.is_active = TRUE;
    
    IF NOT FOUND THEN
        RAISE EXCEPTION 'User not found or inactive';
    END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to clean up expired tokens (should be run periodically)
CREATE OR REPLACE FUNCTION cleanup_expired_tokens()
RETURNS INTEGER AS $$
DECLARE
    v_deleted_count INTEGER;
BEGIN
    -- Delete expired refresh tokens
    DELETE FROM user_refresh_tokens 
    WHERE expires_at < CURRENT_TIMESTAMP - INTERVAL '7 days';
    
    -- Delete expired password reset tokens
    GET DIAGNOSTICS v_deleted_count = ROW_COUNT;
    
    DELETE FROM user_password_reset_tokens 
    WHERE expires_at < CURRENT_TIMESTAMP - INTERVAL '1 day';
    
    GET DIAGNOSTICS v_deleted_count = v_deleted_count + ROW_COUNT;
    
    RETURN v_deleted_count;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Insert default admin user (for initial setup)
INSERT INTO users (email, username, password_hash, first_name, last_name, is_email_verified, is_active)
VALUES ('admin@defaultproject.com', 'admin', '$2b$10$examplehashforadminpassword', 'System', 'Administrator', TRUE, TRUE)
ON CONFLICT (email) DO NOTHING;

-- Comments for documentation
COMMENT ON TABLE users IS 'Stores user registration and authentication information for DefaultProject-201';
COMMENT ON TABLE user_login_attempts IS 'Tracks user login attempts for security monitoring in DefaultProject-201';
COMMENT ON TABLE user_refresh_tokens IS 'Manages JWT refresh tokens for DefaultProject-201 authentication system';
COMMENT ON TABLE user_password_reset_tokens IS 'Stores password reset tokens for DefaultProject-201 user authentication';

COMMENT ON FUNCTION register_user IS 'Registers a new user with validation checks for DefaultProject-201';
COMMENT ON FUNCTION verify_user_credentials IS 'Verifies user credentials for login in DefaultProject-201';
COMMENT ON FUNCTION record_login_attempt IS 'Records login attempt for security logging in DefaultProject-201';
COMMENT ON FUNCTION update_user_login_status IS 'Updates user login status and handles account locking in DefaultProject-201';