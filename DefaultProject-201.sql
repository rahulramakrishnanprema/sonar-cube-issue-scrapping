# Generated for DefaultProject-201 | 2025-09-21 06:29:43 | Developer Agent v2.0
# AutoFlow-Dashboard Enhanced Code Generation
# Thread: ce6dd025 | LangChain: Template-Enhanced Generation
# Workflow Stage: Code Generation (NO PR creation)

-- DefaultProject-201: User Authentication System SQL Implementation
-- Created: 2025-09-21 | Developer Agent v2.0

-- Drop existing tables if they exist (for clean setup)
DROP TABLE IF EXISTS user_password_reset_tokens CASCADE;
DROP TABLE IF EXISTS user_refresh_tokens CASCADE;
DROP TABLE IF EXISTS user_login_attempts CASCADE;
DROP TABLE IF EXISTS user_sessions CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- Create users table
CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    is_locked BOOLEAN DEFAULT FALSE,
    failed_login_attempts INTEGER DEFAULT 0,
    last_login TIMESTAMP,
    verification_token VARCHAR(255),
    verification_token_expires TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_password_change TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_username_length CHECK (LENGTH(username) >= 3 AND LENGTH(username) <= 50),
    CONSTRAINT chk_email_format CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
);

-- Create user_sessions table for JWT token management
CREATE TABLE user_sessions (
    session_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    access_token VARCHAR(512) NOT NULL,
    refresh_token VARCHAR(512) NOT NULL,
    device_info TEXT,
    ip_address VARCHAR(45),
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    revoked_at TIMESTAMP NULL,
    CONSTRAINT unq_access_token UNIQUE (access_token),
    CONSTRAINT unq_refresh_token UNIQUE (refresh_token)
);

-- Create user_login_attempts table for security monitoring
CREATE TABLE user_login_attempts (
    attempt_id SERIAL PRIMARY KEY,
    user_id INTEGER NULL REFERENCES users(user_id) ON DELETE CASCADE,
    username VARCHAR(50),
    ip_address VARCHAR(45),
    user_agent TEXT,
    attempt_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    success BOOLEAN DEFAULT FALSE,
    failure_reason TEXT
);

-- Create user_refresh_tokens table for token rotation
CREATE TABLE user_refresh_tokens (
    token_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    revoked_at TIMESTAMP NULL,
    replaced_by_token_id INTEGER NULL REFERENCES user_refresh_tokens(token_id),
    CONSTRAINT unq_token_hash UNIQUE (token_hash)
);

-- Create user_password_reset_tokens table
CREATE TABLE user_password_reset_tokens (
    reset_token_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    used_at TIMESTAMP NULL,
    CONSTRAINT unq_token_hash UNIQUE (token_hash)
);

-- Indexes for performance
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_verification_token ON users(verification_token);
CREATE INDEX idx_user_sessions_user_id ON user_sessions(user_id);
CREATE INDEX idx_user_sessions_access_token ON user_sessions(access_token);
CREATE INDEX idx_user_sessions_refresh_token ON user_sessions(refresh_token);
CREATE INDEX idx_user_sessions_expires ON user_sessions(expires_at);
CREATE INDEX idx_user_login_attempts_user_id ON user_login_attempts(user_id);
CREATE INDEX idx_user_login_attempts_time ON user_login_attempts(attempt_time);
CREATE INDEX idx_user_refresh_tokens_user_id ON user_refresh_tokens(user_id);
CREATE INDEX idx_user_refresh_tokens_expires ON user_refresh_tokens(expires_at);
CREATE INDEX idx_user_password_reset_tokens_user_id ON user_password_reset_tokens(user_id);
CREATE INDEX idx_user_password_reset_tokens_expires ON user_password_reset_tokens(expires_at);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for users table
CREATE TRIGGER trigger_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Function to log login attempts
CREATE OR REPLACE FUNCTION log_login_attempt(
    p_user_id INTEGER,
    p_username VARCHAR(50),
    p_ip_address VARCHAR(45),
    p_user_agent TEXT,
    p_success BOOLEAN,
    p_failure_reason TEXT
) RETURNS VOID AS $$
BEGIN
    INSERT INTO user_login_attempts (
        user_id, username, ip_address, user_agent, success, failure_reason
    ) VALUES (
        p_user_id, p_username, p_ip_address, p_user_agent, p_success, p_failure_reason
    );
END;
$$ LANGUAGE plpgsql;

-- Function to handle user registration
CREATE OR REPLACE FUNCTION register_user(
    p_username VARCHAR(50),
    p_email VARCHAR(255),
    p_password_hash VARCHAR(255),
    p_first_name VARCHAR(100),
    p_last_name VARCHAR(100),
    p_verification_token VARCHAR(255)
) RETURNS INTEGER AS $$
DECLARE
    v_user_id INTEGER;
BEGIN
    -- Validate input
    IF LENGTH(p_username) < 3 OR LENGTH(p_username) > 50 THEN
        RAISE EXCEPTION 'Username must be between 3 and 50 characters';
    END IF;
    
    IF p_email IS NULL OR p_email !~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$' THEN
        RAISE EXCEPTION 'Invalid email format';
    END IF;
    
    IF LENGTH(p_password_hash) < 60 THEN
        RAISE EXCEPTION 'Invalid password hash';
    END IF;

    -- Insert new user
    INSERT INTO users (
        username, email, password_hash, first_name, last_name, verification_token,
        verification_token_expires
    ) VALUES (
        p_username, p_email, p_password_hash, p_first_name, p_last_name, p_verification_token,
        CURRENT_TIMESTAMP + INTERVAL '24 hours'
    ) RETURNING user_id INTO v_user_id;

    RETURN v_user_id;
EXCEPTION
    WHEN unique_violation THEN
        IF EXISTS (SELECT 1 FROM users WHERE username = p_username) THEN
            RAISE EXCEPTION 'Username already exists';
        ELSE
            RAISE EXCEPTION 'Email already exists';
        END IF;
    WHEN OTHERS THEN
        RAISE;
END;
$$ LANGUAGE plpgsql;

-- Function to verify user email
CREATE OR REPLACE FUNCTION verify_user_email(
    p_verification_token VARCHAR(255)
) RETURNS BOOLEAN AS $$
DECLARE
    v_user_id INTEGER;
BEGIN
    -- Find user with valid verification token
    SELECT user_id INTO v_user_id
    FROM users 
    WHERE verification_token = p_verification_token 
    AND verification_token_expires > CURRENT_TIMESTAMP
    AND is_verified = FALSE;

    IF v_user_id IS NULL THEN
        RETURN FALSE;
    END IF;

    -- Update user as verified
    UPDATE users 
    SET is_verified = TRUE,
        verification_token = NULL,
        verification_token_expires = NULL,
        updated_at = CURRENT_TIMESTAMP
    WHERE user_id = v_user_id;

    RETURN TRUE;
EXCEPTION
    WHEN OTHERS THEN
        RETURN FALSE;
END;
$$ LANGUAGE plpgsql;

-- Function to handle user login
CREATE OR REPLACE FUNCTION authenticate_user(
    p_username VARCHAR(50),
    p_password_hash VARCHAR(255),
    p_device_info TEXT,
    p_ip_address VARCHAR(45)
) RETURNS TABLE (
    user_id INTEGER,
    username VARCHAR(50),
    email VARCHAR(255),
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    access_token VARCHAR(512),
    refresh_token VARCHAR(512),
    expires_at TIMESTAMP
) AS $$
DECLARE
    v_user RECORD;
    v_access_token VARCHAR(512);
    v_refresh_token VARCHAR(512);
    v_expires_at TIMESTAMP;
BEGIN
    -- Get user by username
    SELECT u.user_id, u.username, u.email, u.first_name, u.last_name, u.is_active, 
           u.is_verified, u.is_locked, u.failed_login_attempts
    INTO v_user
    FROM users u
    WHERE u.username = p_username OR u.email = p_username;

    -- Check if user exists and is active/verified
    IF v_user.user_id IS NULL THEN
        PERFORM log_login_attempt(NULL, p_username, p_ip_address, p_device_info, FALSE, 'User not found');
        RAISE EXCEPTION 'Invalid credentials';
    END IF;

    IF NOT v_user.is_active THEN
        PERFORM log_login_attempt(v_user.user_id, p_username, p_ip_address, p_device_info, FALSE, 'Account inactive');
        RAISE EXCEPTION 'Account is inactive';
    END IF;

    IF NOT v_user.is_verified THEN
        PERFORM log_login_attempt(v_user.user_id, p_username, p_ip_address, p_device_info, FALSE, 'Email not verified');
        RAISE EXCEPTION 'Email not verified';
    END IF;

    IF v_user.is_locked THEN
        PERFORM log_login_attempt(v_user.user_id, p_username, p_ip_address, p_device_info, FALSE, 'Account locked');
        RAISE EXCEPTION 'Account is locked due to too many failed attempts';
    END IF;

    -- Verify password (assuming password_hash is already hashed)
    IF NOT EXISTS (
        SELECT 1 FROM users 
        WHERE user_id = v_user.user_id AND password_hash = p_password_hash
    ) THEN
        -- Increment failed login attempts
        UPDATE users 
        SET failed_login_attempts = failed_login_attempts + 1,
            is_locked = CASE WHEN failed_login_attempts + 1 >= 5 THEN TRUE ELSE FALSE END,
            updated_at = CURRENT_TIMESTAMP
        WHERE user_id = v_user.user_id;

        PERFORM log_login_attempt(v_user.user_id, p_username, p_ip_address, p_device_info, FALSE, 'Invalid password');
        RAISE EXCEPTION 'Invalid credentials';
    END IF;

    -- Reset failed login attempts on successful login
    UPDATE users 
    SET failed_login_attempts = 0,
        last_login = CURRENT_TIMESTAMP,
        updated_at = CURRENT_TIMESTAMP
    WHERE user_id = v_user.user_id;

    -- Generate tokens (in real implementation, these would be JWT tokens)
    v_access_token := encode(gen_random_bytes(64), 'base64');
    v_refresh_token := encode(gen_random_bytes(64), 'base64');
    v_expires_at := CURRENT_TIMESTAMP + INTERVAL '1 hour';

    -- Store session
    INSERT INTO user_sessions (
        user_id, access_token, refresh_token, device_info, ip_address, expires_at
    ) VALUES (
        v_user.user_id, v_access_token, v_refresh_token, p_device_info, p_ip_address, v_expires_at
    );

    -- Log successful attempt
    PERFORM log_login_attempt(v_user.user_id, p_username, p_ip_address, p_device_info, TRUE, NULL);

    -- Return user info and tokens
    RETURN QUERY SELECT 
        v_user.user_id, v_user.username, v_user.email, v_user.first_name, v_user.last_name,
        v_access_token, v_refresh_token, v_expires_at;
EXCEPTION
    WHEN OTHERS THEN
        RAISE;
END;
$$ LANGUAGE plpgsql;

-- Function to refresh access token
CREATE OR REPLACE FUNCTION refresh_access_token(
    p_refresh_token VARCHAR(512),
    p_device_info TEXT,
    p_ip_address VARCHAR(45)
) RETURNS TABLE (
    access_token VARCHAR(512),
    refresh_token VARCHAR(512),
    expires_at TIMESTAMP
) AS $$
DECLARE
    v_session RECORD;
    v_new_access_token VARCHAR(512);
    v_new_refresh_token VARCHAR(512);
    v_new_expires_at TIMESTAMP;
BEGIN
    -- Find valid session
    SELECT s.session_id, s.user_id, s.expires_at
    INTO v_session
    FROM user_sessions s
    WHERE s.refresh_token = p_refresh_token 
    AND s.expires_at > CURRENT_TIMESTAMP 
    AND s.revoked_at IS NULL;

    IF v_session.session_id IS NULL THEN
        RAISE EXCEPTION 'Invalid or expired refresh token';
    END IF;

    -- Generate new tokens
    v_new_access_token := encode(gen_random_bytes(64), 'base64');
    v_new_refresh_token := encode(gen_random_bytes(64), 'base64');
    v_new_expires_at := CURRENT_TIMESTAMP + INTERVAL '1 hour';

    -- Update session with new tokens
    UPDATE user_sessions 
    SET access_token = v_new_access_token,
        refresh_token = v_new_refresh_token,
        expires_at = v_new_expires_at,
        device_info = p_device_info,
        ip_address = p_ip_address,
        updated_at = CURRENT_TIMESTAMP
    WHERE session_id = v_session.session_id;

    RETURN QUERY SELECT v_new_access_token, v_new_refresh_token, v_new_expires_at;
EXCEPTION
    WHEN OTHERS THEN
        RAISE;
END;
$$ LANGUAGE plpgsql;

-- Function to create password reset token
CREATE OR REPLACE FUNCTION create_password_reset_token(
    p_email VARCHAR(255)
) RETURNS VARCHAR(255) AS $$
DECLARE
    v_user_id INTEGER;
    v_reset_token VARCHAR(255);
    v_token_hash VARCHAR(255);
BEGIN
    -- Find user by email
    SELECT user_id INTO v_user_id
    FROM users 
    WHERE email = p_email AND is_active = TRUE AND is_verified = TRUE;

    IF v_user_id IS NULL THEN
        RETURN NULL;
    END IF;

    -- Generate reset token
    v_reset_token := encode(gen_random_bytes(32), 'base64');
    v_token_hash := encode(sha256(v_reset_token::bytea), 'hex');

    -- Store reset token
    INSERT INTO user_password_reset_tokens (
        user_id, token_hash, expires_at
    ) VALUES (
        v_user_id, v_token_hash, CURRENT_TIMESTAMP + INTERVAL '1 hour'
    );

    RETURN v_reset_token;
EXCEPTION
    WHEN OTHERS THEN
        RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Function to reset password using token
CREATE OR REPLACE FUNCTION reset_password_with_token(
    p_reset_token VARCHAR(255),
    p_new_password_hash VARCHAR(255)
) RETURNS BOOLEAN AS $$
DECLARE
    v_token_hash VARCHAR(255);
    v_reset_token RECORD;
BEGIN
    -- Hash the provided token
    v_token_hash := encode(sha256(p_reset_token::bytea), 'hex');

    -- Find valid reset token
    SELECT r.reset_token_id, r.user_id, r.expires_at, r.used_at
    INTO v_reset_token
    FROM user_password_reset_tokens r
    WHERE r.token_hash = v_token_hash 
    AND r.expires_at > CURRENT_TIMESTAMP 
    AND r.used_at IS NULL;

    IF v_reset_token.reset_token_id IS NULL THEN
        RETURN FALSE;
    END IF;

    -- Update user password
    UPDATE users 
    SET password_hash = p_new_password_hash,
        last_password_change = CURRENT_TIMESTAMP,
        failed_login_attempts = 0,
        is_locked = FALSE,
        updated_at = CURRENT_TIMESTAMP
    WHERE user_id = v_reset_token.user_id;

    -- Mark reset token as used
    UPDATE user_password_reset_tokens 
    SET used_at = CURRENT_TIMESTAMP
    WHERE reset_token_id = v_reset_token.reset_token_id;

    -- Revoke all existing sessions
    UPDATE user_sessions 
    SET revoked_at = CURRENT_TIMESTAMP
    WHERE user_id = v_reset_token.user_id AND revoked_at IS NULL;

    RETURN TRUE;
EXCEPTION
    WHEN OTHERS THEN
        RETURN FALSE;
END;
$$ LANGUAGE plpgsql;

-- Function to logout user (revoke session)
CREATE OR REPLACE FUNCTION logout_user(
    p_access_token VARCHAR(512)
) RETURNS BOOLEAN AS $$
BEGIN
    UPDATE user_sessions 
    SET revoked_at = CURRENT_TIMESTAMP
    WHERE access_token = p_access_token AND revoked_at IS NULL;

    RETURN FOUND;
EXCEPTION
    WHEN OTHERS THEN
        RETURN FALSE;
END;
$$ LANGUAGE plpgsql;

-- Function to cleanup expired sessions and tokens
CREATE OR REPLACE FUNCTION cleanup_expired_auth_data()
RETURNS INTEGER AS $$
DECLARE
    v_deleted_count INTEGER := 0;
BEGIN
    -- Delete expired sessions
    DELETE FROM user_sessions 
    WHERE expires_at < CURRENT_TIMESTAMP - INTERVAL '7 days';
    
    GET DIAGNOSTICS v_deleted_count = ROW_COUNT;

    -- Delete expired password reset tokens
    DELETE FROM user_password_reset_tokens 
    WHERE expires_at < CURRENT_TIMESTAMP - INTERVAL '1 day';
    
    -- Delete expired refresh tokens
    DELETE FROM user_refresh_tokens 
    WHERE expires_at < CURRENT_TIMESTAMP - INTERVAL '30 days';

    -- Delete old login attempts
    DELETE FROM user_login_attempts 
    WHERE attempt_time < CURRENT_TIMESTAMP - INTERVAL '90 days';

    RETURN v_deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Function to get user by ID
CREATE OR REPLACE FUNCTION get_user_by_id(p_user_id INTEGER)
RETURNS TABLE (
    user_id INTEGER,
    username VARCHAR(50),
    email VARCHAR(255),
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    is_active BOOLEAN,
    is_verified BOOLEAN,
    created_at TIMESTAMP,
    last_login TIMESTAMP
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        u.user_id, u.username, u.email, u.first_name, u.last_name,
        u.is_active, u.is_verified, u.created_at, u.last_login
    FROM users u
    WHERE u.user_id = p_user_id AND u.is_active = TRUE;
END;
$$ LANGUAGE plpgsql;

-- Function to validate session
CREATE OR REPLACE FUNCTION validate_session(p_access_token VARCHAR(512))
RETURNS TABLE (
    user_id INTEGER,
    username VARCHAR(50),
    email VARCHAR(255),
    is_valid BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        u.user_id, u.username, u.email,
        (s.session_id IS NOT NULL AND s.expires_at > CURRENT_TIMESTAMP AND s.revoked_at IS NULL) as is_valid
    FROM user_sessions s
    INNER JOIN users u ON s.user_id = u.user_id
    WHERE s.access_token = p_access_token
    AND u.is_active = TRUE
    AND u.is_verified = TRUE;
END;
$$ LANGUAGE plpgsql;

-- Insert default admin user (for demonstration purposes)
INSERT INTO users (
    username, email, password_hash, first_name, last_name, is_active, is_verified
) VALUES (
    'admin', 'admin@defaultproject.com', 
    '$2b$10$EXAMPLEHASHEDPASSWORD1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ', 
    'System', 'Administrator', TRUE, TRUE
) ON CONFLICT (username) DO NOTHING;

-- Create scheduled job for cleanup (would be set up in actual production)
COMMENT ON FUNCTION cleanup_expired_auth_data() IS 'DefaultProject-201: Cleanup expired authentication data';

-- Grant necessary permissions (adjust based on your security requirements)
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO application_user;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO application_user;