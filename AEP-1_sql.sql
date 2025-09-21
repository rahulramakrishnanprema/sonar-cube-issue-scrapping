-- Issue AEP-1: Setup Database Schema
-- Database: PostgreSQL

-- Drop existing tables if they exist (for clean migration)
DROP TABLE IF EXISTS training_needs CASCADE;
DROP TABLE IF EXISTS user_roles CASCADE;
DROP TABLE IF EXISTS user_skills CASCADE;
DROP TABLE IF EXISTS course_prerequisites CASCADE;
DROP TABLE IF EXISTS course_instructors CASCADE;
DROP TABLE IF EXISTS course_enrollments CASCADE;
DROP TABLE IF EXISTS courses CASCADE;
DROP TABLE IF EXISTS skills CASCADE;
DROP TABLE IF EXISTS roles CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- Create users table
CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    department VARCHAR(100),
    position VARCHAR(100),
    hire_date DATE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_email_format CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'),
    CONSTRAINT chk_username_length CHECK (LENGTH(username) >= 3)
);

-- Create roles table
CREATE TABLE roles (
    role_id SERIAL PRIMARY KEY,
    role_name VARCHAR(50) UNIQUE NOT NULL,
    role_description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_role_name CHECK (role_name ~* '^[A-Za-z0-9_]+$')
);

-- Create user_roles junction table
CREATE TABLE user_roles (
    user_role_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    role_id INTEGER NOT NULL,
    assigned_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    CONSTRAINT fk_user_roles_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    CONSTRAINT fk_user_roles_role FOREIGN KEY (role_id) REFERENCES roles(role_id) ON DELETE CASCADE,
    CONSTRAINT uq_user_role UNIQUE (user_id, role_id)
);

-- Create skills table
CREATE TABLE skills (
    skill_id SERIAL PRIMARY KEY,
    skill_name VARCHAR(100) UNIQUE NOT NULL,
    skill_description TEXT,
    category VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_skill_name CHECK (LENGTH(skill_name) >= 2)
);

-- Create user_skills junction table
CREATE TABLE user_skills (
    user_skill_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    skill_id INTEGER NOT NULL,
    proficiency_level INTEGER CHECK (proficiency_level BETWEEN 1 AND 5),
    acquired_date DATE,
    is_current BOOLEAN DEFAULT TRUE,
    CONSTRAINT fk_user_skills_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    CONSTRAINT fk_user_skills_skill FOREIGN KEY (skill_id) REFERENCES skills(skill_id) ON DELETE CASCADE,
    CONSTRAINT uq_user_skill UNIQUE (user_id, skill_id)
);

-- Create courses table
CREATE TABLE courses (
    course_id SERIAL PRIMARY KEY,
    course_code VARCHAR(20) UNIQUE NOT NULL,
    course_name VARCHAR(200) NOT NULL,
    course_description TEXT,
    duration_hours INTEGER CHECK (duration_hours > 0),
    category VARCHAR(100),
    difficulty_level VARCHAR(20) CHECK (difficulty_level IN ('Beginner', 'Intermediate', 'Advanced')),
    is_available BOOLEAN DEFAULT TRUE,
    max_capacity INTEGER CHECK (max_capacity > 0),
    start_date DATE,
    end_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_dates CHECK (end_date IS NULL OR start_date IS NULL OR end_date >= start_date)
);

-- Create course_instructors junction table
CREATE TABLE course_instructors (
    course_instructor_id SERIAL PRIMARY KEY,
    course_id INTEGER NOT NULL,
    instructor_id INTEGER NOT NULL,
    is_primary BOOLEAN DEFAULT FALSE,
    CONSTRAINT fk_course_instructors_course FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE,
    CONSTRAINT fk_course_instructors_instructor FOREIGN KEY (instructor_id) REFERENCES users(user_id) ON DELETE CASCADE,
    CONSTRAINT uq_course_instructor UNIQUE (course_id, instructor_id)
);

-- Create course_prerequisites junction table
CREATE TABLE course_prerequisites (
    prerequisite_id SERIAL PRIMARY KEY,
    course_id INTEGER NOT NULL,
    required_course_id INTEGER NOT NULL,
    min_grade INTEGER CHECK (min_grade BETWEEN 1 AND 100),
    CONSTRAINT fk_course_prerequisites_course FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE,
    CONSTRAINT fk_course_prerequisites_required FOREIGN KEY (required_course_id) REFERENCES courses(course_id) ON DELETE CASCADE,
    CONSTRAINT chk_not_self_prerequisite CHECK (course_id != required_course_id)
);

-- Create training_needs table
CREATE TABLE training_needs (
    training_need_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    skill_id INTEGER NOT NULL,
    required_proficiency INTEGER CHECK (required_proficiency BETWEEN 1 AND 5),
    priority VARCHAR(20) CHECK (priority IN ('Low', 'Medium', 'High')),
    status VARCHAR(20) DEFAULT 'Pending' CHECK (status IN ('Pending', 'In Progress', 'Completed', 'Cancelled')),
    deadline DATE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_training_needs_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    CONSTRAINT fk_training_needs_skill FOREIGN KEY (skill_id) REFERENCES skills(skill_id) ON DELETE CASCADE,
    CONSTRAINT uq_user_skill_need UNIQUE (user_id, skill_id)
);

-- Create course_enrollments table
CREATE TABLE course_enrollments (
    enrollment_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    course_id INTEGER NOT NULL,
    enrollment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completion_date TIMESTAMP NULL,
    grade INTEGER CHECK (grade BETWEEN 0 AND 100),
    status VARCHAR(20) DEFAULT 'Enrolled' CHECK (status IN ('Enrolled', 'In Progress', 'Completed', 'Dropped')),
    CONSTRAINT fk_course_enrollments_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    CONSTRAINT fk_course_enrollments_course FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE,
    CONSTRAINT uq_user_course_enrollment UNIQUE (user_id, course_id),
    CONSTRAINT chk_completion_date CHECK (completion_date IS NULL OR completion_date >= enrollment_date)
);

-- Create indexes for better performance
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_user_roles_user ON user_roles(user_id);
CREATE INDEX idx_user_roles_role ON user_roles(role_id);
CREATE INDEX idx_user_skills_user ON user_skills(user_id);
CREATE INDEX idx_user_skills_skill ON user_skills(skill_id);
CREATE INDEX idx_courses_category ON courses(category);
CREATE INDEX idx_courses_difficulty ON courses(difficulty_level);
CREATE INDEX idx_course_instructors_course ON course_instructors(course_id);
CREATE INDEX idx_course_instructors_instructor ON course_instructors(instructor_id);
CREATE INDEX idx_course_prerequisites_course ON course_prerequisites(course_id);
CREATE INDEX idx_training_needs_user ON training_needs(user_id);
CREATE INDEX idx_training_needs_skill ON training_needs(skill_id);
CREATE INDEX idx_training_needs_status ON training_needs(status);
CREATE INDEX idx_course_enrollments_user ON course_enrollments(user_id);
CREATE INDEX idx_course_enrollments_course ON course_enrollments(course_id);
CREATE INDEX idx_course_enrollments_status ON course_enrollments(status);

-- Insert sample data for testing
INSERT INTO users (username, email, first_name, last_name, password_hash, department, position, hire_date) VALUES
('john.doe', 'john.doe@company.com', 'John', 'Doe', 'hashed_password_1', 'Engineering', 'Software Developer', '2023-01-15'),
('jane.smith', 'jane.smith@company.com', 'Jane', 'Smith', 'hashed_password_2', 'HR', 'HR Manager', '2022-05-10'),
('mike.jones', 'mike.jones@company.com', 'Mike', 'Jones', 'hashed_password_3', 'Engineering', 'Senior Developer', '2021-03-20'),
('sarah.wilson', 'sarah.wilson@company.com', 'Sarah', 'Wilson', 'hashed_password_4', 'Marketing', 'Marketing Specialist', '2023-02-01');

INSERT INTO roles (role_name, role_description) VALUES
('Admin', 'System administrator with full access'),
('Manager', 'Department manager with team management privileges'),
('Employee', 'Regular employee user'),
('Trainer', 'Course instructor and trainer');

INSERT INTO user_roles (user_id, role_id) VALUES
(1, 1), (2, 2), (3, 3), (4, 3), (3, 4);

INSERT INTO skills (skill_name, skill_description, category) VALUES
('Python', 'Python programming language', 'Technical'),
('JavaScript', 'JavaScript programming language', 'Technical'),
('Project Management', 'Project management skills', 'Management'),
('Communication', 'Verbal and written communication', 'Soft Skills'),
('SQL', 'Structured Query Language', 'Technical'),
('React', 'React framework', 'Technical');

INSERT INTO user_skills (user_id, skill_id, proficiency_level, acquired_date) VALUES
(1, 1, 4, '2023-03-01'), (1, 5, 3, '2023-04-15'),
(2, 3, 5, '2022-06-01'), (2, 4, 4, '2022-07-15'),
(3, 1, 5, '2021-04-01'), (3, 2, 4, '2021-05-15'), (3, 6, 4, '2023-01-10'),
(4, 4, 3, '2023-02-15'), (4, 2, 2, '2023-03-20');

INSERT INTO courses (course_code, course_name, course_description, duration_hours, category, difficulty_level, max_capacity, start_date, end_date) VALUES
('PYT-101', 'Python Fundamentals', 'Introduction to Python programming', 16, 'Technical', 'Beginner', 20, '2024-01-15', '2024-02-15'),
('JS-201', 'Advanced JavaScript', 'Advanced JavaScript concepts and patterns', 24, 'Technical', 'Intermediate', 15, '2024-02-01', '2024-03-15'),
('PM-301', 'Project Management Professional', 'Comprehensive project management training', 40, 'Management', 'Advanced', 25, '2024-03-01', '2024-04-30'),
('COM-102', 'Effective Communication', 'Improving workplace communication skills', 12, 'Soft Skills', 'Beginner', 30, '2024-01-20', '2024-02-20');

INSERT INTO course_instructors (course_id, instructor_id, is_primary) VALUES
(1, 3, TRUE), (2, 3, TRUE), (3, 2, TRUE), (4, 2, TRUE);

INSERT INTO course_prerequisites (course_id, required_course_id, min_grade) VALUES
(2, 1, 70), (3, 1, 80);

INSERT INTO training_needs (user_id, skill_id, required_proficiency, priority, status, deadline) VALUES
(1, 2, 3, 'Medium', 'Pending', '2024-06-30'),
(4, 1, 2, 'High', 'Pending', '2024-05-31'),
(4, 3, 2, 'Low', 'Pending', '2024-08-31');

INSERT INTO course_enrollments (user_id, course_id, enrollment_date, completion_date, grade, status) VALUES
(1, 1, '2024-01-10', '2024-02-15', 85, 'Completed'),
(3, 2, '2024-01-25', NULL, NULL, 'In Progress'),
(4, 4, '2024-01-18', NULL, NULL, 'Enrolled');

-- Create audit trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at columns
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_courses_updated_at BEFORE UPDATE ON courses FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_training_needs_updated_at BEFORE UPDATE ON training_needs FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Create function to check course capacity
CREATE OR REPLACE FUNCTION check_course_capacity()
RETURNS TRIGGER AS $$
BEGIN
    IF (SELECT COUNT(*) FROM course_enrollments WHERE course_id = NEW.course_id AND status IN ('Enrolled', 'In Progress')) 
       >= (SELECT max_capacity FROM courses WHERE course_id = NEW.course_id) THEN
        RAISE EXCEPTION 'Course has reached maximum capacity';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_check_course_capacity BEFORE INSERT ON course_enrollments FOR EACH ROW EXECUTE FUNCTION check_course_capacity();

-- Create function to validate enrollment dates
CREATE OR REPLACE FUNCTION validate_enrollment_dates()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.completion_date IS NOT NULL AND NEW.completion_date < NEW.enrollment_date THEN
        RAISE EXCEPTION 'Completion date cannot be before enrollment date';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_validate_enrollment_dates BEFORE INSERT OR UPDATE ON course_enrollments FOR EACH ROW EXECUTE FUNCTION validate_enrollment_dates();

-- Create view for user training overview
CREATE VIEW user_training_overview AS
SELECT 
    u.user_id,
    u.username,
    u.first_name,
    u.last_name,
    u.department,
    COUNT(DISTINCT ce.course_id) AS total_courses_enrolled,
    COUNT(DISTINCT CASE WHEN ce.status = 'Completed' THEN ce.course_id END) AS courses_completed,
    COUNT(DISTINCT tn.training_need_id) AS pending_training_needs
FROM users u
LEFT JOIN course_enrollments ce ON u.user_id = ce.user_id
LEFT JOIN training_needs tn ON u.user_id = tn.user_id AND tn.status = 'Pending'
GROUP BY u.user_id, u.username, u.first_name, u.last_name, u.department;

-- Create view for course details with instructor information
CREATE VIEW course_details AS
SELECT 
    c.course_id,
    c.course_code,
    c.course_name,
    c.duration_hours,
    c.category,
    c.difficulty_level,
    c.max_capacity,
    c.start_date,
    c.end_date,
    COUNT(ce.enrollment_id) AS current_enrollments,
    STRING_AGG(DISTINCT CONCAT(u.first_name, ' ', u.last_name), ', ') AS instructors
FROM courses c
LEFT JOIN course_instructors ci ON c.course_id = ci.course_id
LEFT JOIN users u ON ci.instructor_id = u.user_id
LEFT JOIN course_enrollments ce ON c.course_id = ce.course_id AND ce.status IN ('Enrolled', 'In Progress')
GROUP BY c.course_id, c.course_code, c.course_name, c.duration_hours, c.category, c.difficulty_level, c.max_capacity, c.start_date, c.end_date;

-- Log table for tracking changes (optional for production)
CREATE TABLE schema_migration_log (
    log_id SERIAL PRIMARY KEY,
    migration_name VARCHAR(255) NOT NULL,
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) NOT NULL,
    error_message TEXT
);

-- Log the migration execution
INSERT INTO schema_migration_log (migration_name, status) VALUES ('AEP-1_schema_setup', 'Completed');