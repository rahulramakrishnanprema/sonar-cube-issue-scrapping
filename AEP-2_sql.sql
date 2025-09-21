-- AEP-2: Authentication SQL Schema Implementation
-- Creates tables for user authentication, registration, and session management

-- Drop existing tables if they exist (for clean setup)
DROP TABLE IF EXISTS user_login_attempts;
DROP TABLE IF EXISTS user_sessions;
DROP TABLE IF EXISTS users;

-- Users table for storing authentication credentials
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    salt VARCHAR(50) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    verification_token VARCHAR(100),
    reset_token VARCHAR(100),
    reset_token_expires TIMESTAMP,
    failed_login_attempts INTEGER DEFAULT 0,
    account_locked_until TIMESTAMP,
    last_login TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User sessions table for JWT token management
CREATE TABLE user_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_token VARCHAR(500) NOT NULL,
    refresh_token VARCHAR(500) NOT NULL,
    device_info VARCHAR(255),
    ip_address VARCHAR(45),
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_revoked BOOLEAN DEFAULT FALSE,
    UNIQUE(session_token)
);

-- Login attempts tracking for security
CREATE TABLE user_login_attempts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    username VARCHAR(50) NOT NULL,
    ip_address VARCHAR(45),
    user_agent VARCHAR(255),
    success BOOLEAN NOT NULL,
    failure_reason VARCHAR(100),
    attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance optimization
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_verification_token ON users(verification_token);
CREATE INDEX idx_users_reset_token ON users(reset_token);
CREATE INDEX idx_user_sessions_token ON user_sessions(session_token);
CREATE INDEX idx_user_sessions_user_id ON user_sessions(user_id);
CREATE INDEX idx_user_sessions_expires ON user_sessions(expires_at);
CREATE INDEX idx_login_attempts_user_id ON user_login_attempts(user_id);
CREATE INDEX idx_login_attempts_username ON user_login_attempts(username);
CREATE INDEX idx_login_attempts_attempted_at ON user_login_attempts(attempted_at);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger for automatic updated_at updates
CREATE TRIGGER update_users_updated_at 
    BEFORE UPDATE ON users 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function to register a new user
CREATE OR REPLACE FUNCTION register_user(
    p_username VARCHAR(50),
    p_email VARCHAR(255),
    p_password_hash VARCHAR(255),
    p_salt VARCHAR(50),
    p_verification_token VARCHAR(100)
) RETURNS INTEGER AS $$
DECLARE
    v_user_id INTEGER;
BEGIN
    -- Validate input parameters
    IF p_username IS NULL OR LENGTH(TRIM(p_username)) = 0 THEN
        RAISE EXCEPTION 'Username cannot be empty';
    END IF;
    
    IF p_email IS NULL OR LENGTH(TRIM(p_email)) = 0 THEN
        RAISE EXCEPTION 'Email cannot be empty';
    END IF;
    
    IF p_password_hash IS NULL OR LENGTH(TRIM(p_password_hash)) = 0 THEN
        RAISE EXCEPTION 'Password hash cannot be empty';
    END IF;
    
    IF p_salt IS NULL OR LENGTH(TRIM(p_salt)) = 0 THEN
        RAISE EXCEPTION 'Salt cannot be empty';
    END IF;

    -- Check if username already exists
    IF EXISTS (SELECT 1 FROM users WHERE username = p_username) THEN
        RAISE EXCEPTION 'Username already exists';
    END IF;

    -- Check if email already exists
    IF EXISTS (SELECT 1 FROM users WHERE email = p_email) THEN
        RAISE EXCEPTION 'Email already registered';
    END IF;

    -- Insert new user
    INSERT INTO users (username, email, password_hash, salt, verification_token)
    VALUES (p_username, p_email, p_password_hash, p_salt, p_verification_token)
    RETURNING id INTO v_user_id;

    RETURN v_user_id;
EXCEPTION
    WHEN unique_violation THEN
        RAISE EXCEPTION 'User registration failed due to duplicate entry';
    WHEN OTHERS THEN
        RAISE EXCEPTION 'User registration failed: %', SQLERRM;
END;
$$ LANGUAGE plpgsql;

-- Function to authenticate user login
CREATE OR REPLACE FUNCTION authenticate_user(
    p_username VARCHAR(50),
    p_password_hash VARCHAR(255)
) RETURNS TABLE (
    user_id INTEGER,
    username VARCHAR(50),
    email VARCHAR(255),
    is_active BOOLEAN,
    is_verified BOOLEAN,
    account_locked BOOLEAN
) AS $$
DECLARE
    v_user RECORD;
    v_account_locked BOOLEAN;
BEGIN
    -- Validate input
    IF p_username IS NULL OR LENGTH(TRIM(p_username)) = 0 THEN
        RAISE EXCEPTION 'Username cannot be empty';
    END IF;
    
    IF p_password_hash IS NULL OR LENGTH(TRIM(p_password_hash)) = 0 THEN
        RAISE EXCEPTION 'Password hash cannot be empty';
    END IF;

    -- Get user data
    SELECT id, username, email, password_hash, is_active, is_verified, 
           failed_login_attempts, account_locked_until
    INTO v_user
    FROM users 
    WHERE username = p_username;

    -- Check if user exists
    IF v_user IS NULL THEN
        -- Record failed attempt for non-existent user
        INSERT INTO user_login_attempts (username, ip_address, success, failure_reason)
        VALUES (p_username, NULL, FALSE, 'User not found');
        
        RAISE EXCEPTION 'Invalid credentials';
    END IF;

    -- Check if account is locked
    IF v_user.account_locked_until IS NOT NULL AND v_user.account_locked_until > CURRENT_TIMESTAMP THEN
        INSERT INTO user_login_attempts (user_id, username, ip_address, success, failure_reason)
        VALUES (v_user.id, p_username, NULL, FALSE, 'Account locked');
        
        RAISE EXCEPTION 'Account is temporarily locked';
    END IF;

    -- Verify password hash
    IF v_user.password_hash != p_password_hash THEN
        -- Increment failed login attempts
        UPDATE users 
        SET failed_login_attempts = failed_login_attempts + 1,
            account_locked_until = CASE 
                WHEN failed_login_attempts >= 4 THEN CURRENT_TIMESTAMP + INTERVAL '15 minutes'
                ELSE account_locked_until 
            END
        WHERE id = v_user.id;

        -- Record failed attempt
        INSERT INTO user_login_attempts (user_id, username, ip_address, success, failure_reason)
        VALUES (v_user.id, p_username, NULL, FALSE, 'Invalid password');

        RAISE EXCEPTION 'Invalid credentials';
    END IF;

    -- Check if account is active
    IF NOT v_user.is_active THEN
        INSERT INTO user_login_attempts (user_id, username, ip_address, success, failure_reason)
        VALUES (v_user.id, p_username, NULL, FALSE, 'Account deactivated');
        
        RAISE EXCEPTION 'Account is deactivated';
    END IF;

    -- Check if email is verified
    IF NOT v_user.is_verified THEN
        INSERT INTO user_login_attempts (user_id, username, ip_address, success, failure_reason)
        VALUES (v_user.id, p_username, NULL, FALSE, 'Email not verified');
        
        RAISE EXCEPTION 'Email verification required';
    END IF;

    -- Reset failed login attempts and update last login
    UPDATE users 
    SET failed_login_attempts = 0,
        account_locked_until = NULL,
        last_login = CURRENT_TIMESTAMP
    WHERE id = v_user.id;

    -- Record successful login
    INSERT INTO user_login_attempts (user_id, username, ip_address, success)
    VALUES (v_user.id, p_username, NULL, TRUE);

    -- Return user data
    RETURN QUERY 
    SELECT v_user.id, v_user.username, v_user.email, 
           v_user.is_active, v_user.is_verified, FALSE;
EXCEPTION
    WHEN OTHERS THEN
        RAISE;
END;
$$ LANGUAGE plpgsql;

-- Function to create a new session
CREATE OR REPLACE FUNCTION create_user_session(
    p_user_id INTEGER,
    p_session_token VARCHAR(500),
    p_refresh_token VARCHAR(500),
    p_device_info VARCHAR(255),
    p_ip_address VARCHAR(45),
    p_expires_at TIMESTAMP
) RETURNS INTEGER AS $$
DECLARE
    v_session_id INTEGER;
BEGIN
    -- Validate input
    IF p_user_id IS NULL THEN
        RAISE EXCEPTION 'User ID cannot be null';
    END IF;
    
    IF p_session_token IS NULL OR LENGTH(TRIM(p_session_token)) = 0 THEN
        RAISE EXCEPTION 'Session token cannot be empty';
    END IF;
    
    IF p_refresh_token IS NULL OR LENGTH(TRIM(p_refresh_token)) = 0 THEN
        RAISE EXCEPTION 'Refresh token cannot be empty';
    END IF;
    
    IF p_expires_at IS NULL OR p_expires_at <= CURRENT_TIMESTAMP THEN
        RAISE EXCEPTION 'Invalid expiration time';
    END IF;

    -- Check if user exists and is active
    IF NOT EXISTS (SELECT 1 FROM users WHERE id = p_user_id AND is_active = TRUE) THEN
        RAISE EXCEPTION 'User not found or inactive';
    END IF;

    -- Insert new session
    INSERT INTO user_sessions (user_id, session_token, refresh_token, device_info, ip_address, expires_at)
    VALUES (p_user_id, p_session_token, p_refresh_token, p_device_info, p_ip_address, p_expires_at)
    RETURNING id INTO v_session_id;

    RETURN v_session_id;
EXCEPTION
    WHEN unique_violation THEN
        RAISE EXCEPTION 'Session token already exists';
    WHEN OTHERS THEN
        RAISE EXCEPTION 'Session creation failed: %', SQLERRM;
END;
$$ LANGUAGE plpgsql;

-- Function to validate session token
CREATE OR REPLACE FUNCTION validate_session_token(
    p_session_token VARCHAR(500)
) RETURNS TABLE (
    user_id INTEGER,
    username VARCHAR(50),
    email VARCHAR(255),
    is_active BOOLEAN
) AS $$
DECLARE
    v_session RECORD;
BEGIN
    -- Validate input
    IF p_session_token IS NULL OR LENGTH(TRIM(p_session_token)) = 0 THEN
        RAISE EXCEPTION 'Session token cannot be empty';
    END IF;

    -- Get session data
    SELECT us.*, u.username, u.email, u.is_active
    INTO v_session
    FROM user_sessions us
    JOIN users u ON us.user_id = u.id
    WHERE us.session_token = p_session_token 
      AND us.expires_at > CURRENT_TIMESTAMP 
      AND us.is_revoked = FALSE;

    -- Check if session exists and is valid
    IF v_session IS NULL THEN
        RAISE EXCEPTION 'Invalid or expired session token';
    END IF;

    -- Return user data
    RETURN QUERY 
    SELECT v_session.user_id, v_session.username, v_session.email, v_session.is_active;
EXCEPTION
    WHEN OTHERS THEN
        RAISE;
END;
$$ LANGUAGE plpgsql;

-- Function to revoke session
CREATE OR REPLACE FUNCTION revoke_session(
    p_session_token VARCHAR(500)
) RETURNS BOOLEAN AS $$
BEGIN
    -- Validate input
    IF p_session_token IS NULL OR LENGTH(TRIM(p_session_token)) = 0 THEN
        RAISE EXCEPTION 'Session token cannot be empty';
    END IF;

    -- Update session as revoked
    UPDATE user_sessions 
    SET is_revoked = TRUE 
    WHERE session_token = p_session_token;

    RETURN FOUND;
EXCEPTION
    WHEN OTHERS THEN
        RAISE EXCEPTION 'Session revocation failed: %', SQLERRM;
END;
$$ LANGUAGE plpgsql;

-- Function to revoke all user sessions
CREATE OR REPLACE FUNCTION revoke_all_user_sessions(
    p_user_id INTEGER
) RETURNS INTEGER AS $$
DECLARE
    v_revoked_count INTEGER;
BEGIN
    -- Validate input
    IF p_user_id IS NULL THEN
        RAISE EXCEPTION 'User ID cannot be null';
    END IF;

    -- Revoke all active sessions for user
    UPDATE user_sessions 
    SET is_revoked = TRUE 
    WHERE user_id = p_user_id 
      AND is_revoked = FALSE 
      AND expires_at > CURRENT_TIMESTAMP;
    
    GET DIAGNOSTICS v_revoked_count = ROW_COUNT;

    RETURN v_revoked_count;
EXCEPTION
    WHEN OTHERS THEN
        RAISE EXCEPTION 'Session revocation failed: %', SQLERRM;
END;
$$ LANGUAGE plpgsql;

-- Function to clean up expired sessions
CREATE OR REPLACE FUNCTION cleanup_expired_sessions() RETURNS INTEGER AS $$
DECLARE
    v_cleaned_count INTEGER;
BEGIN
    -- Delete expired sessions
    DELETE FROM user_sessions 
    WHERE expires_at <= CURRENT_TIMESTAMP;
    
    GET DIAGNOSTICS v_cleaned_count = ROW_COUNT;

    RETURN v_cleaned_count;
EXCEPTION
    WHEN OTHERS THEN
        RAISE EXCEPTION 'Session cleanup failed: %', SQLERRM;
END;
$$ LANGUAGE plpgsql;

-- Function to verify email
CREATE OR REPLACE FUNCTION verify_user_email(
    p_verification_token VARCHAR(100)
) RETURNS BOOLEAN AS $$
BEGIN
    -- Validate input
    IF p_verification_token IS NULL OR LENGTH(TRIM(p_verification_token)) = 0 THEN
        RAISE EXCEPTION 'Verification token cannot be empty';
    END IF;

    -- Update user verification status
    UPDATE users 
    SET is_verified = TRUE, 
        verification_token = NULL 
    WHERE verification_token = p_verification_token;

    RETURN FOUND;
EXCEPTION
    WHEN OTHERS THEN
        RAISE EXCEPTION 'Email verification failed: %', SQLERRM;
END;
$$ LANGUAGE plpgsql;

-- Function to update password
CREATE OR REPLACE FUNCTION update_user_password(
    p_user_id INTEGER,
    p_new_password_hash VARCHAR(255),
    p_new_salt VARCHAR(50)
) RETURNS BOOLEAN AS $$
BEGIN
    -- Validate input
    IF p_user_id IS NULL THEN
        RAISE EXCEPTION 'User ID cannot be null';
    END IF;
    
    IF p_new_password_hash IS NULL OR LENGTH(TRIM(p_new_password_hash)) = 0 THEN
        RAISE EXCEPTION 'New password hash cannot be empty';
    END IF;
    
    IF p_new_salt IS NULL OR LENGTH(TRIM(p_new_salt)) = 0 THEN
        RAISE EXCEPTION 'New salt cannot be empty';
    END IF;

    -- Update password and salt
    UPDATE users 
    SET password_hash = p_new_password_hash,
        salt = p_new_salt,
        reset_token = NULL,
        reset_token_expires = NULL,
        failed_login_attempts = 0,
        account_locked_until = NULL
    WHERE id = p_user_id;

    -- Revoke all existing sessions for security
    PERFORM revoke_all_user_sessions(p_user_id);

    RETURN FOUND;
EXCEPTION
    WHEN OTHERS THEN
        RAISE EXCEPTION 'Password update failed: %', SQLERRM;
END;
$$ LANGUAGE plpgsql;

-- Function to set password reset token
CREATE OR REPLACE FUNCTION set_password_reset_token(
    p_email VARCHAR(255),
    p_reset_token VARCHAR(100),
    p_expires_at TIMESTAMP
) RETURNS BOOLEAN AS $$
BEGIN
    -- Validate input
    IF p_email IS NULL OR LENGTH(TRIM(p_email)) = 0 THEN
        RAISE EXCEPTION 'Email cannot be empty';
    END IF;
    
    IF p_reset_token IS NULL OR LENGTH(TRIM(p_reset_token)) = 0 THEN
        RAISE EXCEPTION 'Reset token cannot be empty';
    END IF;
    
    IF p_expires_at IS NULL OR p_expires_at <= CURRENT_TIMESTAMP THEN
        RAISE EXCEPTION 'Invalid expiration time';
    END IF;

    -- Set reset token
    UPDATE users 
    SET reset_token = p_reset_token,
        reset_token_expires = p_expires_at
    WHERE email = p_email;

    RETURN FOUND;
EXCEPTION
    WHEN OTHERS THEN
        RAISE EXCEPTION 'Reset token setting failed: %', SQLERRM;
END;
$$ LANGUAGE plpgsql;

-- Function to reset password using token
CREATE OR REPLACE FUNCTION reset_password_with_token(
    p_reset_token VARCHAR(100),
    p_new_password_hash VARCHAR(255),
    p_new_salt VARCHAR(50)
) RETURNS BOOLEAN AS $$
BEGIN
    -- Validate input
    IF p_reset_token IS NULL OR LENGTH(TRIM(p_reset_token)) = 0 THEN
        RAISE EXCEPTION 'Reset token cannot be empty';
    END IF;
    
    IF p_new_password_hash IS NULL OR LENGTH(TRIM(p_new_password_hash)) = 0 THEN
        RAISE EXCEPTION 'New password hash cannot be empty';
    END IF;
    
    IF p_new_salt IS NULL OR LENGTH(TRIM(p_new_salt)) = 0 THEN
        RAISE EXCEPTION 'New salt cannot be empty';
    END IF;

    -- Reset password using token
    UPDATE users 
    SET password_hash = p_new_password_hash,
        salt = p_new_salt,
        reset_token = NULL,
        reset_token_expires = NULL,
        failed_login_attempts = 0,
        account_locked_until = NULL
    WHERE reset_token = p_reset_token 
      AND reset_token_expires > CURRENT_TIMESTAMP;

    -- Revoke all sessions for the user
    PERFORM revoke_all_user_sessions(
        (SELECT id FROM users WHERE reset_token = p_reset_token)
    );

    RETURN FOUND;
EXCEPTION
    WHEN OTHERS THEN
        RAISE EXCEPTION 'Password reset failed: %', SQLERRM;
END;
$$ LANGUAGE plpgsql;

-- Function to get user by ID
CREATE OR REPLACE FUNCTION get_user_by_id(
    p_user_id INTEGER
) RETURNS TABLE (
    id INTEGER,
    username VARCHAR(50),
    email VARCHAR(255),
    is_active BOOLEAN,
    is_verified BOOLEAN,
    created_at TIMESTAMP,
    last_login TIMESTAMP
) AS $$
BEGIN
    -- Validate input
    IF p_user_id IS NULL THEN
        RAISE EXCEPTION 'User ID cannot be null';
    END IF;

    -- Return user data
    RETURN QUERY 
    SELECT u.id, u.username, u.email, u.is_active, u.is_verified, u.created_at, u.last_login
    FROM users u
    WHERE u.id = p_user_id;
EXCEPTION
    WHEN OTHERS THEN
        RAISE;
END;
$$ LANGUAGE plpgsql;

-- Function to check if username exists
CREATE OR REPLACE FUNCTION username_exists(
    p_username VARCHAR(50)
) RETURNS BOOLEAN AS $$
BEGIN
    -- Validate input
    IF p_username IS NULL OR LENGTH(TRIM(p_username)) = 0 THEN
        RAISE EXCEPTION 'Username cannot be empty';
    END IF;

    RETURN EXISTS (SELECT 1 FROM users WHERE username = p_username);
EXCEPTION
    WHEN OTHERS THEN
        RAISE;
END;
$$ LANGUAGE plpgsql;

-- Function to check if email exists
CREATE OR REPLACE FUNCTION email_exists(
    p_email VARCHAR(255)
) RETURNS BOOLEAN AS $$
BEGIN
    -- Validate input
    IF p_email IS NULL OR LENGTH(TRIM(p_email)) = 0 THEN
        RAISE EXCEPTION 'Email cannot be empty';
    END IF;

    RETURN EXISTS (SELECT 1 FROM users WHERE email = p_email);
EXCEPTION
    WHEN OTHERS THEN
        RAISE;
END;
$$ LANGUAGE plpgsql;

-- Create cleanup job for expired sessions
CREATE OR REPLACE FUNCTION schedule_session_cleanup() RETURNS VOID AS $$
BEGIN
    -- This would typically be set up as a cron job or scheduled task
    -- For SQL, we create the function and recommend setting up a periodic job
    NULL;
END;
$$ LANGUAGE plpgsql;

-- Insert initial admin user (for testing purposes - remove in production)
INSERT INTO users (username, email, password_hash, salt, is_verified)
VALUES ('admin', 'admin@example.com', 'hashed_password', 'salt_value', TRUE)
ON CONFLICT (username) DO NOTHING;