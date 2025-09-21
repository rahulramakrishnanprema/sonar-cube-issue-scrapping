-- Issue Reference: AEP-1
-- Database Schema Setup for Training Management System

-- Drop existing tables if they exist (for clean migration)
DROP TABLE IF EXISTS user_courses CASCADE;
DROP TABLE IF EXISTS training_needs CASCADE;
DROP TABLE IF EXISTS courses CASCADE;
DROP TABLE IF EXISTS user_skills CASCADE;
DROP TABLE IF EXISTS skills CASCADE;
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
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL UNIQUE,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    role_id INTEGER NOT NULL REFERENCES roles(role_id),
    department VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_email_format CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
);

-- Create skills table
CREATE TABLE skills (
    skill_id SERIAL PRIMARY KEY,
    skill_name VARCHAR(100) NOT NULL UNIQUE,
    skill_description TEXT,
    category VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create user_skills table (junction table for users and skills)
CREATE TABLE user_skills (
    user_skill_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    skill_id INTEGER NOT NULL REFERENCES skills(skill_id) ON DELETE CASCADE,
    proficiency_level INTEGER CHECK (proficiency_level BETWEEN 1 AND 5),
    years_of_experience INTEGER CHECK (years_of_experience >= 0),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, skill_id)
);

-- Create courses table
CREATE TABLE courses (
    course_id SERIAL PRIMARY KEY,
    course_code VARCHAR(20) NOT NULL UNIQUE,
    course_name VARCHAR(200) NOT NULL,
    description TEXT,
    duration_hours INTEGER CHECK (duration_hours > 0),
    skill_id INTEGER REFERENCES skills(skill_id),
    instructor VARCHAR(100),
    is_available BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create training_needs table
CREATE TABLE training_needs (
    training_need_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    skill_id INTEGER NOT NULL REFERENCES skills(skill_id) ON DELETE CASCADE,
    required_proficiency INTEGER CHECK (required_proficiency BETWEEN 1 AND 5),
    priority_level INTEGER CHECK (priority_level BETWEEN 1 AND 3),
    status VARCHAR(20) DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'APPROVED', 'COMPLETED', 'REJECTED')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, skill_id)
);

-- Create user_courses table (junction table for users and courses)
CREATE TABLE user_courses (
    user_course_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    course_id INTEGER NOT NULL REFERENCES courses(course_id) ON DELETE CASCADE,
    enrollment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completion_date TIMESTAMP,
    status VARCHAR(20) DEFAULT 'ENROLLED' CHECK (status IN ('ENROLLED', 'IN_PROGRESS', 'COMPLETED', 'DROPPED')),
    grade NUMERIC(5,2) CHECK (grade >= 0 AND grade <= 100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, course_id)
);

-- Create indexes for better performance
CREATE INDEX idx_users_role ON users(role_id);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_user_skills_user ON user_skills(user_id);
CREATE INDEX idx_user_skills_skill ON user_skills(skill_id);
CREATE INDEX idx_courses_skill ON courses(skill_id);
CREATE INDEX idx_training_needs_user ON training_needs(user_id);
CREATE INDEX idx_training_needs_skill ON training_needs(skill_id);
CREATE INDEX idx_user_courses_user ON user_courses(user_id);
CREATE INDEX idx_user_courses_course ON user_courses(course_id);

-- Insert sample roles
INSERT INTO roles (role_name, role_description) VALUES
('Administrator', 'System administrator with full access'),
('Manager', 'Department manager who can approve training requests'),
('Employee', 'Regular employee who can request training'),
('Trainer', 'Training instructor role');

-- Insert sample skills
INSERT INTO skills (skill_name, skill_description, category) VALUES
('SQL Programming', 'Structured Query Language programming', 'Technical'),
('Python Development', 'Python programming and development', 'Technical'),
('Project Management', 'Managing projects and teams', 'Management'),
('Data Analysis', 'Data analysis and visualization', 'Analytical'),
('Communication Skills', 'Verbal and written communication', 'Soft Skills'),
('Leadership', 'Team leadership and management', 'Management');

-- Insert sample users
INSERT INTO users (username, email, first_name, last_name, role_id, department) VALUES
('admin_user', 'admin@company.com', 'Admin', 'User', 1, 'IT'),
('manager_john', 'john.manager@company.com', 'John', 'Manager', 2, 'Operations'),
('employee_sarah', 'sarah.employee@company.com', 'Sarah', 'Employee', 3, 'Marketing'),
('trainer_mike', 'mike.trainer@company.com', 'Mike', 'Trainer', 4, 'Training');

-- Insert sample user skills
INSERT INTO user_skills (user_id, skill_id, proficiency_level, years_of_experience) VALUES
(1, 1, 4, 5),  -- Admin has SQL skills
(2, 3, 5, 8),  -- Manager has Project Management skills
(3, 5, 3, 2),  -- Employee has Communication skills
(4, 1, 5, 10), -- Trainer has SQL skills
(4, 2, 4, 7);  -- Trainer has Python skills

-- Insert sample courses
INSERT INTO courses (course_code, course_name, description, duration_hours, skill_id, instructor) VALUES
('SQL101', 'Introduction to SQL', 'Basic SQL programming course', 16, 1, 'Mike Trainer'),
('PYTHON201', 'Python for Data Analysis', 'Intermediate Python course focusing on data analysis', 24, 2, 'Mike Trainer'),
('PM301', 'Advanced Project Management', 'Advanced project management techniques', 20, 3, 'External Instructor'),
('COMM101', 'Effective Communication', 'Improving workplace communication skills', 12, 5, 'Sarah Coach');

-- Insert sample training needs
INSERT INTO training_needs (user_id, skill_id, required_proficiency, priority_level, status) VALUES
(3, 1, 3, 2, 'PENDING'),    -- Employee needs SQL training
(3, 2, 2, 1, 'APPROVED'),   -- Employee needs Python training (approved)
(2, 4, 4, 3, 'COMPLETED');  -- Manager completed Data Analysis training

-- Insert sample user course enrollments
INSERT INTO user_courses (user_id, course_id, enrollment_date, completion_date, status, grade) VALUES
(3, 2, '2024-01-15', NULL, 'ENROLLED', NULL),           -- Employee enrolled in Python course
(2, 3, '2024-01-10', '2024-02-01', 'COMPLETED', 92.5), -- Manager completed Project Management course
(4, 1, '2024-01-20', NULL, 'IN_PROGRESS', NULL);        -- Trainer teaching SQL course

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
CREATE TRIGGER update_skills_updated_at BEFORE UPDATE ON skills FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_user_skills_updated_at BEFORE UPDATE ON user_skills FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_courses_updated_at BEFORE UPDATE ON courses FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_training_needs_updated_at BEFORE UPDATE ON training_needs FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_user_courses_updated_at BEFORE UPDATE ON user_courses FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Create view for user training overview
CREATE VIEW user_training_overview AS
SELECT 
    u.user_id,
    u.username,
    u.first_name,
    u.last_name,
    r.role_name,
    u.department,
    COUNT(DISTINCT us.skill_id) as total_skills,
    COUNT(DISTINCT tn.training_need_id) as pending_training_needs,
    COUNT(DISTINCT uc.course_id) as enrolled_courses,
    COUNT(DISTINCT CASE WHEN uc.status = 'COMPLETED' THEN uc.course_id END) as completed_courses
FROM users u
JOIN roles r ON u.role_id = r.role_id
LEFT JOIN user_skills us ON u.user_id = us.user_id
LEFT JOIN training_needs tn ON u.user_id = tn.user_id AND tn.status = 'PENDING'
LEFT JOIN user_courses uc ON u.user_id = uc.user_id
GROUP BY u.user_id, u.username, u.first_name, u.last_name, r.role_name, u.department;

-- Log table for tracking schema changes
CREATE TABLE schema_migration_log (
    log_id SERIAL PRIMARY KEY,
    migration_name VARCHAR(200) NOT NULL,
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) CHECK (status IN ('SUCCESS', 'FAILED')),
    error_message TEXT
);

-- Log the successful migration
INSERT INTO schema_migration_log (migration_name, status) VALUES ('AEP-1_schema_setup', 'SUCCESS');