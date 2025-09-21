#!/bin/bash

# AEP-1: Setup Database Schema
# This script creates the database schema, migration scripts, and test data

set -euo pipefail
IFS=$'\n\t'

# Configuration
DB_URL="postgresql://admin:admin@localhost:5432/training_db"
LOG_FILE="schema_setup.log"
MIGRATION_DIR="migrations"
BACKUP_DIR="backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Logging function
log_message() {
    local level=$1
    local message=$2
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${timestamp} [${level}] ${message}" | tee -a "$LOG_FILE"
}

# Error handling function
error_exit() {
    log_message "ERROR" "$1"
    exit 1
}

# Validate PostgreSQL connection
validate_db_connection() {
    log_message "INFO" "Validating database connection..."
    if ! psql "$DB_URL" -c "SELECT 1;" > /dev/null 2>&1; then
        error_exit "Cannot connect to PostgreSQL database. Please check if PostgreSQL is running and credentials are correct."
    fi
    log_message "INFO" "Database connection validated successfully"
}

# Create migration directory structure
create_directories() {
    log_message "INFO" "Creating directory structure..."
    mkdir -p "$MIGRATION_DIR" "$BACKUP_DIR" || error_exit "Failed to create directories"
}

# Backup existing database (if any)
backup_database() {
    log_message "INFO" "Creating database backup..."
    local backup_file="${BACKUP_DIR}/backup_${TIMESTAMP}.sql"
    if pg_dump "$DB_URL" > "$backup_file" 2>/dev/null; then
        log_message "INFO" "Database backup created: $backup_file"
    else
        log_message "WARNING" "Failed to create database backup (database might not exist)"
    fi
}

# Create database tables
create_tables() {
    log_message "INFO" "Creating database tables..."
    
    local create_tables_sql=$(cat << 'EOF'
-- Create roles table
CREATE TABLE IF NOT EXISTS roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    role_id INTEGER REFERENCES roles(id),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create skills table
CREATE TABLE IF NOT EXISTS skills (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    category VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create courses table
CREATE TABLE IF NOT EXISTS courses (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    duration_hours INTEGER,
    difficulty_level VARCHAR(20),
    instructor VARCHAR(100),
    category VARCHAR(50),
    is_available BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create user_skills junction table
CREATE TABLE IF NOT EXISTS user_skills (
    user_id INTEGER REFERENCES users(id),
    skill_id INTEGER REFERENCES skills(id),
    proficiency_level INTEGER CHECK (proficiency_level BETWEEN 1 AND 5),
    acquired_date DATE,
    PRIMARY KEY (user_id, skill_id)
);

-- Create training_needs table
CREATE TABLE IF NOT EXISTS training_needs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    skill_id INTEGER REFERENCES skills(id),
    required_proficiency INTEGER CHECK (required_proficiency BETWEEN 1 AND 5),
    priority VARCHAR(20) CHECK (priority IN ('low', 'medium', 'high')),
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'completed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create course_enrollments table
CREATE TABLE IF NOT EXISTS course_enrollments (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    course_id INTEGER REFERENCES courses(id),
    enrollment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completion_date TIMESTAMP,
    status VARCHAR(20) DEFAULT 'enrolled' CHECK (status IN ('enrolled', 'in_progress', 'completed', 'cancelled')),
    UNIQUE(user_id, course_id)
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_users_role_id ON users(role_id);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_user_skills_user_id ON user_skills(user_id);
CREATE INDEX IF NOT EXISTS idx_user_skills_skill_id ON user_skills(skill_id);
CREATE INDEX IF NOT EXISTS idx_training_needs_user_id ON training_needs(user_id);
CREATE INDEX IF NOT EXISTS idx_training_needs_skill_id ON training_needs(skill_id);
CREATE INDEX IF NOT EXISTS idx_course_enrollments_user_id ON course_enrollments(user_id);
CREATE INDEX IF NOT EXISTS idx_course_enrollments_course_id ON course_enrollments(course_id);
EOF
)

    if ! psql "$DB_URL" -c "$create_tables_sql" >> "$LOG_FILE" 2>&1; then
        error_exit "Failed to create database tables"
    fi
    log_message "INFO" "Database tables created successfully"
}

# Insert sample data
insert_sample_data() {
    log_message "INFO" "Inserting sample data..."
    
    local sample_data_sql=$(cat << 'EOF'
-- Insert sample roles
INSERT INTO roles (name, description) VALUES
('admin', 'System administrator with full access'),
('manager', 'Team manager with user management capabilities'),
('employee', 'Regular employee user'),
('trainer', 'Training instructor')
ON CONFLICT (name) DO NOTHING;

-- Insert sample skills
INSERT INTO skills (name, description, category) VALUES
('Python', 'Python programming language', 'Technical'),
('JavaScript', 'JavaScript programming language', 'Technical'),
('SQL', 'Structured Query Language', 'Technical'),
('Project Management', 'Project management methodologies', 'Management'),
('Communication', 'Verbal and written communication skills', 'Soft Skills'),
('Leadership', 'Team leadership and management', 'Management')
ON CONFLICT (name) DO NOTHING;

-- Insert sample users
INSERT INTO users (username, email, password_hash, first_name, last_name, role_id) VALUES
('admin_user', 'admin@example.com', 'hashed_password_1', 'John', 'Admin', (SELECT id FROM roles WHERE name = 'admin')),
('manager_user', 'manager@example.com', 'hashed_password_2', 'Jane', 'Manager', (SELECT id FROM roles WHERE name = 'manager')),
('employee1', 'employee1@example.com', 'hashed_password_3', 'Bob', 'Employee', (SELECT id FROM roles WHERE name = 'employee')),
('employee2', 'employee2@example.com', 'hashed_password_4', 'Alice', 'Developer', (SELECT id FROM roles WHERE name = 'employee'))
ON CONFLICT (username) DO NOTHING;

-- Insert sample courses
INSERT INTO courses (title, description, duration_hours, difficulty_level, instructor, category) VALUES
('Python Fundamentals', 'Introduction to Python programming', 16, 'beginner', 'Dr. Python Expert', 'Technical'),
('Advanced SQL Techniques', 'Deep dive into SQL optimization', 24, 'intermediate', 'SQL Master', 'Technical'),
('Effective Communication', 'Improving workplace communication', 8, 'beginner', 'Communication Coach', 'Soft Skills'),
('Project Management Essentials', 'Fundamentals of project management', 20, 'intermediate', 'PM Professional', 'Management')
ON CONFLICT (title) DO NOTHING;

-- Insert sample user skills
INSERT INTO user_skills (user_id, skill_id, proficiency_level, acquired_date) VALUES
((SELECT id FROM users WHERE username = 'employee1'), (SELECT id FROM skills WHERE name = 'Python'), 3, '2023-01-15'),
((SELECT id FROM users WHERE username = 'employee1'), (SELECT id FROM skills WHERE name = 'SQL'), 2, '2023-02-20'),
((SELECT id FROM users WHERE username = 'employee2'), (SELECT id FROM skills WHERE name = 'JavaScript'), 4, '2023-03-10'),
((SELECT id FROM users WHERE username = 'manager_user'), (SELECT id FROM skills WHERE name = 'Project Management'), 4, '2023-04-05')
ON CONFLICT (user_id, skill_id) DO NOTHING;

-- Insert sample training needs
INSERT INTO training_needs (user_id, skill_id, required_proficiency, priority, status) VALUES
((SELECT id FROM users WHERE username = 'employee1'), (SELECT id FROM skills WHERE name = 'Python'), 4, 'high', 'pending'),
((SELECT id FROM users WHERE username = 'employee2'), (SELECT id FROM skills WHERE name = 'Communication'), 3, 'medium', 'in_progress'),
((SELECT id FROM users WHERE username = 'manager_user'), (SELECT id FROM skills WHERE name = 'Leadership'), 5, 'high', 'completed')
ON CONFLICT DO NOTHING;

-- Insert sample course enrollments
INSERT INTO course_enrollments (user_id, course_id, status) VALUES
((SELECT id FROM users WHERE username = 'employee1'), (SELECT id FROM courses WHERE title = 'Python Fundamentals'), 'enrolled'),
((SELECT id FROM users WHERE username = 'employee2'), (SELECT id FROM courses WHERE title = 'Effective Communication'), 'in_progress'),
((SELECT id FROM users WHERE username = 'manager_user'), (SELECT id FROM courses WHERE title = 'Project Management Essentials'), 'completed')
ON CONFLICT (user_id, course_id) DO NOTHING;
EOF
)

    if ! psql "$DB_URL" -c "$sample_data_sql" >> "$LOG_FILE" 2>&1; then
        error_exit "Failed to insert sample data"
    fi
    log_message "INFO" "Sample data inserted successfully"
}

# Create migration script
create_migration_script() {
    log_message "INFO" "Creating migration script..."
    
    local migration_file="${MIGRATION_DIR}/001_initial_schema_${TIMESTAMP}.sql"
    
    cat > "$migration_file" << EOF
-- Migration: Initial Schema Setup
-- Created: $TIMESTAMP
-- Issue: AEP-1

BEGIN;

-- Drop existing tables if they exist (for clean migration)
DROP TABLE IF EXISTS course_enrollments CASCADE;
DROP TABLE IF EXISTS training_needs CASCADE;
DROP TABLE IF EXISTS user_skills CASCADE;
DROP TABLE IF EXISTS courses CASCADE;
DROP TABLE IF EXISTS skills CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS roles CASCADE;

-- Create roles table
CREATE TABLE roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create users table
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    role_id INTEGER REFERENCES roles(id),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create skills table
CREATE TABLE skills (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    category VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create courses table
CREATE TABLE courses (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    duration_hours INTEGER,
    difficulty_level VARCHAR(20),
    instructor VARCHAR(100),
    category VARCHAR(50),
    is_available BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create user_skills junction table
CREATE TABLE user_skills (
    user_id INTEGER REFERENCES users(id),
    skill_id INTEGER REFERENCES skills(id),
    proficiency_level INTEGER CHECK (proficiency_level BETWEEN 1 AND 5),
    acquired_date DATE,
    PRIMARY KEY (user_id, skill_id)
);

-- Create training_needs table
CREATE TABLE training_needs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    skill_id INTEGER REFERENCES skills(id),
    required_proficiency INTEGER CHECK (required_proficiency BETWEEN 1 AND 5),
    priority VARCHAR(20) CHECK (priority IN ('low', 'medium', 'high')),
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'completed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create course_enrollments table
CREATE TABLE course_enrollments (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    course_id INTEGER REFERENCES courses(id),
    enrollment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completion_date TIMESTAMP,
    status VARCHAR(20) DEFAULT 'enrolled' CHECK (status IN ('enrolled', 'in_progress', 'completed', 'cancelled')),
    UNIQUE(user_id, course_id)
);

-- Create indexes for better performance
CREATE INDEX idx_users_role_id ON users(role_id);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_user_skills_user_id ON user_skills(user_id);
CREATE INDEX idx_user_skills_skill_id ON user_skills(skill_id);
CREATE INDEX idx_training_needs_user_id ON training_needs(user_id);
CREATE INDEX idx_training_needs_skill_id ON training_needs(skill_id);
CREATE INDEX idx_course_enrollments_user_id ON course_enrollments(user_id);
CREATE INDEX idx_course_enrollments_course_id ON course_enrollments(course_id);

COMMIT;
EOF

    log_message "INFO" "Migration script created: $migration_file"
}

# Validate schema
validate_schema() {
    log_message "INFO" "Validating schema..."
    
    local validation_query=$(cat << 'EOF'
SELECT 
    COUNT(*) as table_count,
    (SELECT COUNT(*) FROM roles) as roles_count,
    (SELECT COUNT(*) FROM users) as users_count,
    (SELECT COUNT(*) FROM skills) as skills_count,
    (SELECT COUNT(*) FROM courses) as courses_count,
    (SELECT COUNT(*) FROM user_skills) as user_skills_count,
    (SELECT COUNT(*) FROM training_needs) as training_needs_count,
    (SELECT COUNT(*) FROM course_enrollments) as enrollments_count
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN ('roles', 'users', 'skills', 'courses', 'user_skills', 'training_needs', 'course_enrollments');
EOF
)

    local result
    result=$(psql "$DB_URL" -t -c "$validation_query" 2>/dev/null)
    
    if [ -z "$result" ]; then
        error_exit "Schema validation failed - could not retrieve table information"
    fi
    
    log_message "INFO" "Schema validation completed: $result"
}

# Main execution
main() {
    log_message "INFO" "Starting AEP-1 database schema setup"
    
    # Check if PostgreSQL client is available
    if ! command -v psql &> /dev/null; then
        error_exit "PostgreSQL client (psql) is not installed or not in PATH"
    fi
    
    validate_db_connection
    create_directories
    backup_database
    create_tables
    insert_sample_data
    create_migration_script
    validate_schema
    
    log_message "INFO" "AEP-1 database schema setup completed successfully"
    echo -e "${GREEN}Database schema setup completed successfully!${NC}"
    echo -e "${YELLOW}Check $LOG_FILE for detailed logs${NC}"
}

# Run main function
main "$@"