#!/bin/bash
# AEP-1: Database Schema Setup Script

set -euo pipefail
IFS=$'\n\t'

# Configuration
DB_URL="${DB_URL:-postgresql://admin:admin@localhost:5432/training_db}"
LOG_FILE="AEP-1_schema_setup.log"
MIGRATION_DIR="migrations"
BACKUP_DIR="backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
    exit 1
}

# Validate PostgreSQL connection
validate_db_connection() {
    if ! command -v psql &> /dev/null; then
        log_error "PostgreSQL client (psql) is not installed"
    fi
    
    if ! PGPASSWORD="admin" psql -h localhost -p 5432 -U admin -d postgres -c "\q" 2>/dev/null; then
        log_error "Cannot connect to PostgreSQL database. Check if PostgreSQL is running and credentials are correct."
    fi
}

# Create database if it doesn't exist
create_database() {
    log_info "Checking if database training_db exists..."
    if ! PGPASSWORD="admin" psql -h localhost -p 5432 -U admin -d postgres -lqt | cut -d \| -f 1 | grep -qw training_db; then
        log_info "Creating database training_db..."
        PGPASSWORD="admin" psql -h localhost -p 5432 -U admin -d postgres -c "CREATE DATABASE training_db;" || log_error "Failed to create database"
    fi
}

# Create migration directory structure
setup_migration_dirs() {
    mkdir -p "$MIGRATION_DIR" "$BACKUP_DIR" || log_error "Failed to create directories"
}

# Backup existing database
backup_database() {
    log_info "Creating database backup..."
    local backup_file="$BACKUP_DIR/backup_${TIMESTAMP}.sql"
    if PGPASSWORD="admin" pg_dump -h localhost -p 5432 -U admin training_db > "$backup_file" 2>/dev/null; then
        log_info "Backup created: $backup_file"
    else
        log_warn "Failed to create backup (database might be empty)"
    fi
}

# Execute SQL file with error handling
execute_sql_file() {
    local sql_file="$1"
    local description="$2"
    
    if [ ! -f "$sql_file" ]; then
        log_error "SQL file not found: $sql_file"
    fi
    
    log_info "Executing $description..."
    if PGPASSWORD="admin" psql -h localhost -p 5432 -U admin -d training_db -f "$sql_file" 2>&1 | tee -a "$LOG_FILE"; then
        log_info "$description completed successfully"
    else
        log_error "Failed to execute $description"
    fi
}

# Generate migration scripts
generate_migration_scripts() {
    # Schema creation script
    cat > "$MIGRATION_DIR/001_create_schema.sql" << 'EOF'
-- AEP-1: Database Schema Creation
-- Created: $(date '+%Y-%m-%d %H:%M:%S')

-- Drop existing tables if they exist
DROP TABLE IF EXISTS user_courses CASCADE;
DROP TABLE IF EXISTS training_needs CASCADE;
DROP TABLE IF EXISTS courses CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS roles CASCADE;

-- Create roles table
CREATE TABLE roles (
    role_id SERIAL PRIMARY KEY,
    role_name VARCHAR(50) NOT NULL UNIQUE,
    role_description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create users table
CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    role_id INTEGER REFERENCES roles(role_id),
    department VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_user_role FOREIGN KEY (role_id) REFERENCES roles(role_id)
);

-- Create courses table
CREATE TABLE courses (
    course_id SERIAL PRIMARY KEY,
    course_code VARCHAR(50) NOT NULL UNIQUE,
    course_name VARCHAR(255) NOT NULL,
    description TEXT,
    duration_hours INTEGER,
    category VARCHAR(100),
    instructor VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create training_needs table
CREATE TABLE training_needs (
    need_id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(user_id),
    skill_required VARCHAR(255) NOT NULL,
    priority_level VARCHAR(20) CHECK (priority_level IN ('Low', 'Medium', 'High')),
    status VARCHAR(20) DEFAULT 'Pending' CHECK (status IN ('Pending', 'Approved', 'Rejected', 'Completed')),
    requested_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    target_completion_date DATE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_training_user FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- Create user_courses junction table
CREATE TABLE user_courses (
    user_course_id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(user_id),
    course_id INTEGER REFERENCES courses(course_id),
    enrollment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completion_date TIMESTAMP NULL,
    status VARCHAR(20) DEFAULT 'Enrolled' CHECK (status IN ('Enrolled', 'In Progress', 'Completed', 'Dropped')),
    grade VARCHAR(10) NULL,
    feedback TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_user_course UNIQUE (user_id, course_id),
    CONSTRAINT fk_user_course_user FOREIGN KEY (user_id) REFERENCES users(user_id),
    CONSTRAINT fk_user_course_course FOREIGN KEY (course_id) REFERENCES courses(course_id)
);

-- Create indexes for better performance
CREATE INDEX idx_users_role_id ON users(role_id);
CREATE INDEX idx_training_needs_user_id ON training_needs(user_id);
CREATE INDEX idx_user_courses_user_id ON user_courses(user_id);
CREATE INDEX idx_user_courses_course_id ON user_courses(course_id);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_courses_category ON courses(category);

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_roles_updated_at BEFORE UPDATE ON roles FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_courses_updated_at BEFORE UPDATE ON courses FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_training_needs_updated_at BEFORE UPDATE ON training_needs FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_user_courses_updated_at BEFORE UPDATE ON user_courses FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

EOF

    # Test data insertion script
    cat > "$MIGRATION_DIR/002_insert_test_data.sql" << 'EOF'
-- AEP-1: Test Data Insertion
-- Created: $(date '+%Y-%m-%d %H:%M:%S')

-- Insert sample roles
INSERT INTO roles (role_name, role_description) VALUES
('Administrator', 'System administrator with full access'),
('Manager', 'Department manager with team management privileges'),
('Developer', 'Software development role'),
('HR Specialist', 'Human resources specialist'),
('Trainer', 'Training and development specialist')
ON CONFLICT (role_name) DO NOTHING;

-- Insert sample users
INSERT INTO users (username, email, first_name, last_name, role_id, department) VALUES
('admin_user', 'admin@company.com', 'Admin', 'User', 1, 'IT'),
('john_doe', 'john.doe@company.com', 'John', 'Doe', 2, 'Engineering'),
('jane_smith', 'jane.smith@company.com', 'Jane', 'Smith', 3, 'Development'),
('bob_wilson', 'bob.wilson@company.com', 'Bob', 'Wilson', 4, 'HR'),
('sarah_trainer', 'sarah.trainer@company.com', 'Sarah', 'Johnson', 5, 'Training')
ON CONFLICT (email) DO NOTHING;

-- Insert sample courses
INSERT INTO courses (course_code, course_name, description, duration_hours, category, instructor) VALUES
('DEV-101', 'Introduction to Programming', 'Basic programming concepts and fundamentals', 40, 'Development', 'Dr. Alan Turing'),
('MGMT-201', 'Leadership Skills', 'Developing effective leadership and management skills', 24, 'Management', 'Prof. John Maxwell'),
('HR-301', 'Recruitment Strategies', 'Modern recruitment and talent acquisition techniques', 16, 'HR', 'Sarah Wilson'),
('DEV-202', 'Advanced Database Design', 'Advanced database concepts and optimization techniques', 32, 'Development', 'Dr. Maria Stone'),
('COMM-102', 'Effective Communication', 'Improving workplace communication skills', 20, 'Soft Skills', 'Lisa Chen')
ON CONFLICT (course_code) DO NOTHING;

-- Insert sample training needs
INSERT INTO training_needs (user_id, skill_required, priority_level, status, target_completion_date, notes) VALUES
(3, 'Advanced Python Programming', 'High', 'Approved', '2024-03-15', 'Required for upcoming project'),
(2, 'Project Management', 'Medium', 'Pending', '2024-06-30', 'For team leadership role'),
(4, 'Employment Law', 'High', 'Approved', '2024-02-28', 'Compliance training requirement'),
(3, 'Cloud Infrastructure', 'Medium', 'Rejected', '2024-04-01', 'Not currently prioritized'),
(5, 'Training Delivery Methods', 'High', 'Completed', '2023-12-15', 'Completed last quarter')
ON CONFLICT DO NOTHING;

-- Insert sample user course enrollments
INSERT INTO user_courses (user_id, course_id, enrollment_date, completion_date, status, grade, feedback) VALUES
(3, 1, '2024-01-15', '2024-02-15', 'Completed', 'A', 'Excellent course content'),
(2, 2, '2024-01-20', NULL, 'In Progress', NULL, NULL),
(4, 3, '2024-01-10', '2024-01-26', 'Completed', 'B+', 'Very informative'),
(3, 4, '2024-02-01', NULL, 'Enrolled', NULL, NULL),
(5, 5, '2024-01-05', '2024-01-25', 'Completed', 'A-', 'Great practical exercises')
ON CONFLICT DO NOTHING;

EOF

    # Validation script
    cat > "$MIGRATION_DIR/003_validate_schema.sql" << 'EOF'
-- AEP-1: Schema Validation
-- Created: $(date '+%Y-%m-%d %H:%M:%S')

-- Validate table counts
SELECT 'Roles count: ' || COUNT(*) FROM roles;
SELECT 'Users count: ' || COUNT(*) FROM users;
SELECT 'Courses count: ' || COUNT(*) FROM courses;
SELECT 'Training needs count: ' || COUNT(*) FROM training_needs;
SELECT 'User courses count: ' || COUNT(*) FROM user_courses;

-- Validate foreign key relationships
SELECT 'Users with valid roles: ' || COUNT(*) FROM users u JOIN roles r ON u.role_id = r.role_id;
SELECT 'Training needs with valid users: ' || COUNT(*) FROM training_needs tn JOIN users u ON tn.user_id = u.user_id;
SELECT 'User courses with valid users: ' || COUNT(*) FROM user_courses uc JOIN users u ON uc.user_id = u.user_id;
SELECT 'User courses with valid courses: ' || COUNT(*) FROM user_courses uc JOIN courses c ON uc.course_id = c.course_id;

-- Sample data validation queries
SELECT 'Sample user: ' || username || ' - ' || first_name || ' ' || last_name FROM users LIMIT 5;
SELECT 'Sample course: ' || course_code || ' - ' || course_name FROM courses LIMIT 5;

EOF
}

# Validate schema with test data
validate_schema() {
    log_info "Validating schema with test data..."
    if PGPASSWORD="admin" psql -h localhost -p 5432 -U admin -d training_db -f "$MIGRATION_DIR/003_validate_schema.sql" 2>&1 | tee -a "$LOG_FILE"; then
        log_info "Schema validation completed successfully"
    else
        log_error "Schema validation failed"
    fi
}

# Main execution function
main() {
    log_info "Starting AEP-1 Database Schema Setup"
    
    # Validate environment
    validate_db_connection
    create_database
    setup_migration_dirs
    backup_database
    
    # Generate and execute migration scripts
    generate_migration_scripts
    execute_sql_file "$MIGRATION_DIR/001_create_schema.sql" "schema creation"
    execute_sql_file "$MIGRATION_DIR/002_insert_test_data.sql" "test data insertion"
    
    # Validate the setup
    validate_schema
    
    log_info "AEP-1 Database Schema Setup completed successfully"
    log_info "Log file: $LOG_FILE"
    log_info "Backup directory: $BACKUP_DIR"
    log_info "Migration scripts: $MIGRATION_DIR"
}

# Handle script arguments
case "${1:-}" in
    --validate)
        validate_schema
        ;;
    --backup)
        backup_database
        ;;
    --help)
        echo "Usage: $0 [--validate|--backup|--help]"
        echo "  --validate   Validate existing schema"
        echo "  --backup     Create database backup"
        echo "  --help       Show this help message"
        ;;
    *)
        main
        ;;
esac