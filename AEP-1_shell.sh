#!/bin/bash

# AEP-1: Setup Database Schema
# Database schema setup script for training management system

set -euo pipefail
IFS=$'\n\t'

# Configuration
DB_URL="${DB_URL:-postgresql://admin:admin@localhost:5432/training_db}"
LOG_FILE="schema_setup.log"
MIGRATION_DIR="migrations"
BACKUP_DIR="backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Validation functions
validate_db_connection() {
    if ! command -v psql &> /dev/null; then
        log_error "psql command not found. Please install PostgreSQL client tools."
        exit 1
    fi
    
    if ! PGPASSWORD="admin" psql -h localhost -p 5432 -U admin -d training_db -c "SELECT 1;" &> /dev/null; then
        log_error "Cannot connect to PostgreSQL database. Please check if PostgreSQL is running and credentials are correct."
        exit 1
    fi
}

validate_migration_files() {
    local required_files=("001_create_tables.sql" "002_insert_sample_data.sql")
    
    for file in "${required_files[@]}"; do
        if [[ ! -f "$MIGRATION_DIR/$file" ]]; then
            log_error "Missing required migration file: $MIGRATION_DIR/$file"
            exit 1
        fi
    done
}

# Backup function
backup_database() {
    log_info "Creating database backup..."
    local backup_file="$BACKUP_DIR/backup_${TIMESTAMP}.sql"
    
    if ! mkdir -p "$BACKUP_DIR"; then
        log_error "Failed to create backup directory"
        exit 1
    fi
    
    if PGPASSWORD="admin" pg_dump -h localhost -p 5432 -U admin training_db > "$backup_file" 2>> "$LOG_FILE"; then
        log_success "Database backup created: $backup_file"
    else
        log_error "Failed to create database backup"
        exit 1
    fi
}

# Migration functions
create_migration_tables() {
    log_info "Creating migration tracking table..."
    
    local migration_table_sql="
    CREATE TABLE IF NOT EXISTS schema_migrations (
        version VARCHAR(255) PRIMARY KEY,
        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        checksum VARCHAR(64)
    );"
    
    if ! PGPASSWORD="admin" psql -h localhost -p 5432 -U admin -d training_db -c "$migration_table_sql" >> "$LOG_FILE" 2>&1; then
        log_error "Failed to create migration tracking table"
        exit 1
    fi
}

run_migration() {
    local migration_file="$1"
    local version=$(basename "$migration_file" .sql)
    
    log_info "Running migration: $version"
    
    # Check if migration has already been applied
    local check_migration="SELECT 1 FROM schema_migrations WHERE version = '$version';"
    local result=$(PGPASSWORD="admin" psql -h localhost -p 5432 -U admin -d training_db -t -c "$check_migration" 2>/dev/null)
    
    if [[ -n "$result" ]]; then
        log_warning "Migration $version already applied, skipping"
        return 0
    fi
    
    # Calculate checksum
    local checksum=$(sha256sum "$migration_file" | cut -d' ' -f1)
    
    # Run migration
    if PGPASSWORD="admin" psql -h localhost -p 5432 -U admin -d training_db -f "$migration_file" >> "$LOG_FILE" 2>&1; then
        # Record migration
        local record_migration="INSERT INTO schema_migrations (version, checksum) VALUES ('$version', '$checksum');"
        PGPASSWORD="admin" psql -h localhost -p 5432 -U admin -d training_db -c "$record_migration" >> "$LOG_FILE" 2>&1
        
        log_success "Migration $version applied successfully"
        return 0
    else
        log_error "Failed to apply migration $version"
        return 1
    fi
}

# Main execution
main() {
    log_info "Starting AEP-1 database schema setup"
    
    # Validate environment
    validate_db_connection
    validate_migration_files
    
    # Create necessary directories
    mkdir -p "$MIGRATION_DIR" "$BACKUP_DIR"
    
    # Create migration files if they don't exist
    create_migration_files
    
    # Backup existing database
    backup_database
    
    # Create migration tracking table
    create_migration_tables
    
    # Run migrations in order
    local migration_files=(
        "$MIGRATION_DIR/001_create_tables.sql"
        "$MIGRATION_DIR/002_insert_sample_data.sql"
    )
    
    for migration_file in "${migration_files[@]}"; do
        if ! run_migration "$migration_file"; then
            log_error "Schema setup failed during migration: $(basename "$migration_file")"
            exit 1
        fi
    done
    
    # Verify schema creation
    verify_schema
    
    log_success "AEP-1 database schema setup completed successfully"
}

# Create migration files
create_migration_files() {
    # Create tables migration
    if [[ ! -f "$MIGRATION_DIR/001_create_tables.sql" ]]; then
        cat > "$MIGRATION_DIR/001_create_tables.sql" << 'EOF'
-- AEP-1: Create database tables

-- Roles table
CREATE TABLE IF NOT EXISTS roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Users table
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

-- Courses table
CREATE TABLE IF NOT EXISTS courses (
    id SERIAL PRIMARY KEY,
    code VARCHAR(20) NOT NULL UNIQUE,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    duration_hours INTEGER,
    category VARCHAR(50),
    level VARCHAR(20),
    is_available BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Training needs table
CREATE TABLE IF NOT EXISTS training_needs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    skill_category VARCHAR(100) NOT NULL,
    skill_name VARCHAR(100) NOT NULL,
    priority_level INTEGER CHECK (priority_level BETWEEN 1 AND 5),
    status VARCHAR(20) DEFAULT 'PENDING',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User courses table (junction table)
CREATE TABLE IF NOT EXISTS user_courses (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    course_id INTEGER REFERENCES courses(id),
    enrollment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completion_date TIMESTAMP,
    status VARCHAR(20) DEFAULT 'ENROLLED',
    progress_percentage INTEGER DEFAULT 0 CHECK (progress_percentage BETWEEN 0 AND 100),
    UNIQUE(user_id, course_id)
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_users_role_id ON users(role_id);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_training_needs_user_id ON training_needs(user_id);
CREATE INDEX IF NOT EXISTS idx_user_courses_user_id ON user_courses(user_id);
CREATE INDEX IF NOT EXISTS idx_user_courses_course_id ON user_courses(course_id);
CREATE INDEX IF NOT EXISTS idx_courses_category ON courses(category);
CREATE INDEX IF NOT EXISTS idx_courses_level ON courses(level);

-- Create updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at
DO $$ 
BEGIN
    -- Users table trigger
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_users_updated_at') THEN
        CREATE TRIGGER update_users_updated_at
            BEFORE UPDATE ON users
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;

    -- Roles table trigger
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_roles_updated_at') THEN
        CREATE TRIGGER update_roles_updated_at
            BEFORE UPDATE ON roles
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;

    -- Courses table trigger
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_courses_updated_at') THEN
        CREATE TRIGGER update_courses_updated_at
            BEFORE UPDATE ON courses
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;

    -- Training needs table trigger
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_training_needs_updated_at') THEN
        CREATE TRIGGER update_training_needs_updated_at
            BEFORE UPDATE ON training_needs
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
END $$;
EOF
    fi

    # Insert sample data migration
    if [[ ! -f "$MIGRATION_DIR/002_insert_sample_data.sql" ]]; then
        cat > "$MIGRATION_DIR/002_insert_sample_data.sql" << 'EOF'
-- AEP-1: Insert sample data for testing

-- Insert sample roles
INSERT INTO roles (name, description) VALUES
('Administrator', 'System administrator with full access'),
('Manager', 'Department manager who can approve training requests'),
('Employee', 'Regular employee who can request training'),
('Trainer', 'Training instructor who delivers courses')
ON CONFLICT (name) DO NOTHING;

-- Insert sample users
INSERT INTO users (username, email, password_hash, first_name, last_name, role_id) VALUES
('admin', 'admin@company.com', '$2b$10$examplehash', 'System', 'Administrator', 1),
('jdoe', 'jdoe@company.com', '$2b$10$examplehash', 'John', 'Doe', 2),
('jsmith', 'jsmith@company.com', '$2b$10$examplehash', 'Jane', 'Smith', 3),
('trainer1', 'trainer1@company.com', '$2b$10$examplehash', 'Bob', 'Trainer', 4)
ON CONFLICT (username) DO NOTHING;

-- Insert sample courses
INSERT INTO courses (code, title, description, duration_hours, category, level) VALUES
('DEV-101', 'Introduction to Programming', 'Basic programming concepts and fundamentals', 40, 'Technical', 'Beginner'),
('MGMT-201', 'Leadership Skills', 'Developing effective leadership and management skills', 24, 'Management', 'Intermediate'),
('COMM-101', 'Effective Communication', 'Improving workplace communication skills', 16, 'Soft Skills', 'Beginner'),
('DATA-301', 'Advanced Data Analysis', 'Advanced techniques for data analysis and visualization', 32, 'Technical', 'Advanced')
ON CONFLICT (code) DO NOTHING;

-- Insert sample training needs
INSERT INTO training_needs (user_id, skill_category, skill_name, priority_level, status) VALUES
(3, 'Technical', 'Python Programming', 3, 'APPROVED'),
(3, 'Soft Skills', 'Public Speaking', 2, 'PENDING'),
(2, 'Management', 'Team Leadership', 4, 'COMPLETED')
ON CONFLICT DO NOTHING;

-- Insert sample user course enrollments
INSERT INTO user_courses (user_id, course_id, status, progress_percentage) VALUES
(3, 1, 'IN_PROGRESS', 75),
(2, 2, 'COMPLETED', 100),
(3, 3, 'ENROLLED', 0)
ON CONFLICT DO NOTHING;
EOF
    fi
}

# Verify schema creation
verify_schema() {
    log_info "Verifying schema creation..."
    
    local verification_query="
    SELECT 
        (SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public') as table_count,
        (SELECT COUNT(*) FROM roles) as roles_count,
        (SELECT COUNT(*) FROM users) as users_count,
        (SELECT COUNT(*) FROM courses) as courses_count,
        (SELECT COUNT(*) FROM training_needs) as needs_count,
        (SELECT COUNT(*) FROM user_courses) as enrollments_count;
    "
    
    local result
    result=$(PGPASSWORD="admin" psql -h localhost -p 5432 -U admin -d training_db -t -c "$verification_query" 2>/dev/null)
    
    if [[ -n "$result" ]]; then
        log_success "Schema verification successful: $result"
    else
        log_error "Schema verification failed"
        exit 1
    fi
}

# Cleanup function
cleanup() {
    log_info "Cleaning up temporary files..."
    # Add any cleanup operations here
}

# Error handling
trap 'log_error "Script interrupted by user"; cleanup; exit 1' INT
trap 'log_error "Script failed with error: $?"; cleanup; exit 1' ERR

# Execute main function
main "$@"

# Cleanup and exit
cleanup
exit 0