-- AEP-1: Setup Database Schema

-- Drop existing tables if they exist (for clean migration)
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
    role_id INTEGER NOT NULL REFERENCES roles(role_id),
    department VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_email_format CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
);

-- Create courses table
CREATE TABLE courses (
    course_id SERIAL PRIMARY KEY,
    course_code VARCHAR(20) NOT NULL UNIQUE,
    course_name VARCHAR(200) NOT NULL,
    course_description TEXT,
    category VARCHAR(100),
    duration_hours INTEGER NOT NULL CHECK (duration_hours > 0),
    difficulty_level VARCHAR(20) CHECK (difficulty_level IN ('Beginner', 'Intermediate', 'Advanced')),
    is_available BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create training_needs table
CREATE TABLE training_needs (
    need_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(user_id),
    required_skill VARCHAR(200) NOT NULL,
    priority_level VARCHAR(20) DEFAULT 'Medium' CHECK (priority_level IN ('Low', 'Medium', 'High')),
    status VARCHAR(20) DEFAULT 'Pending' CHECK (status IN ('Pending', 'Approved', 'Rejected', 'Completed')),
    deadline_date DATE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create user_courses junction table
CREATE TABLE user_courses (
    user_course_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(user_id),
    course_id INTEGER NOT NULL REFERENCES courses(course_id),
    enrollment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completion_date TIMESTAMP,
    status VARCHAR(20) DEFAULT 'Enrolled' CHECK (status IN ('Enrolled', 'In Progress', 'Completed', 'Dropped')),
    progress_percentage INTEGER DEFAULT 0 CHECK (progress_percentage BETWEEN 0 AND 100),
    UNIQUE(user_id, course_id)
);

-- Create indexes for better performance
CREATE INDEX idx_users_role_id ON users(role_id);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_training_needs_user_id ON training_needs(user_id);
CREATE INDEX idx_training_needs_status ON training_needs(status);
CREATE INDEX idx_user_courses_user_id ON user_courses(user_id);
CREATE INDEX idx_user_courses_course_id ON user_courses(course_id);
CREATE INDEX idx_user_courses_status ON user_courses(status);
CREATE INDEX idx_courses_category ON courses(category);

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updating updated_at
CREATE TRIGGER update_roles_updated_at BEFORE UPDATE ON roles FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_courses_updated_at BEFORE UPDATE ON courses FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_training_needs_updated_at BEFORE UPDATE ON training_needs FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Insert sample roles
INSERT INTO roles (role_name, role_description) VALUES
('Administrator', 'System administrator with full access'),
('Manager', 'Department manager with team management privileges'),
('Employee', 'Regular employee user'),
('Trainer', 'Training instructor and content manager');

-- Insert sample users
INSERT INTO users (username, email, first_name, last_name, role_id, department) VALUES
('admin.user', 'admin@company.com', 'Admin', 'User', 1, 'IT'),
('john.manager', 'john.manager@company.com', 'John', 'Smith', 2, 'Sales'),
('sarah.employee', 'sarah.employee@company.com', 'Sarah', 'Johnson', 3, 'Marketing'),
('mike.trainer', 'mike.trainer@company.com', 'Mike', 'Brown', 4, 'HR'),
('jane.doe', 'jane.doe@company.com', 'Jane', 'Doe', 3, 'Finance');

-- Insert sample courses
INSERT INTO courses (course_code, course_name, course_description, category, duration_hours, difficulty_level) VALUES
('DEV-101', 'Introduction to Programming', 'Basic programming concepts and fundamentals', 'Development', 40, 'Beginner'),
('MGMT-201', 'Leadership Skills', 'Developing effective leadership and management skills', 'Management', 24, 'Intermediate'),
('DATA-301', 'Advanced Data Analysis', 'Advanced techniques for data analysis and visualization', 'Data Science', 60, 'Advanced'),
('COMM-102', 'Effective Communication', 'Improving workplace communication skills', 'Soft Skills', 16, 'Beginner'),
('PROJ-202', 'Project Management', 'Fundamentals of project management methodologies', 'Management', 32, 'Intermediate');

-- Insert sample training needs
INSERT INTO training_needs (user_id, required_skill, priority_level, status, deadline_date, notes) VALUES
(3, 'Data Analysis Skills', 'High', 'Approved', '2024-03-31', 'Required for upcoming project'),
(2, 'Advanced Excel', 'Medium', 'Pending', '2024-04-15', 'For financial reporting'),
(5, 'Presentation Skills', 'Low', 'Approved', '2024-05-01', 'Team presentation training'),
(3, 'Python Programming', 'High', 'Completed', '2024-02-15', 'Completed basic course'),
(4, 'Conflict Resolution', 'Medium', 'Approved', '2024-04-30', 'Team management training');

-- Insert sample user course enrollments
INSERT INTO user_courses (user_id, course_id, enrollment_date, completion_date, status, progress_percentage) VALUES
(3, 3, '2024-01-15', '2024-02-15', 'Completed', 100),
(2, 2, '2024-02-01', NULL, 'In Progress', 75),
(5, 4, '2024-02-10', NULL, 'Enrolled', 0),
(4, 5, '2024-01-20', NULL, 'In Progress', 60),
(3, 1, '2024-03-01', NULL, 'Enrolled', 25);

-- Create view for user training progress
CREATE VIEW user_training_progress AS
SELECT 
    u.user_id,
    u.username,
    u.first_name,
    u.last_name,
    r.role_name,
    u.department,
    COUNT(uc.user_course_id) AS total_courses,
    COUNT(CASE WHEN uc.status = 'Completed' THEN 1 END) AS completed_courses,
    COUNT(CASE WHEN uc.status IN ('Enrolled', 'In Progress') THEN 1 END) AS active_courses,
    COALESCE(AVG(uc.progress_percentage), 0) AS avg_progress
FROM users u
LEFT JOIN roles r ON u.role_id = r.role_id
LEFT JOIN user_courses uc ON u.user_id = uc.user_id
GROUP BY u.user_id, u.username, u.first_name, u.last_name, r.role_name, u.department;

-- Create view for course statistics
CREATE VIEW course_statistics AS
SELECT 
    c.course_id,
    c.course_code,
    c.course_name,
    c.category,
    c.difficulty_level,
    COUNT(uc.user_course_id) AS total_enrollments,
    COUNT(CASE WHEN uc.status = 'Completed' THEN 1 END) AS completions,
    COUNT(CASE WHEN uc.status IN ('Enrolled', 'In Progress') THEN 1 END) AS active_enrollments,
    COALESCE(AVG(uc.progress_percentage), 0) AS avg_progress
FROM courses c
LEFT JOIN user_courses uc ON c.course_id = uc.course_id
GROUP BY c.course_id, c.course_code, c.course_name, c.category, c.difficulty_level;

-- Create function to validate user enrollment
CREATE OR REPLACE FUNCTION validate_user_enrollment()
RETURNS TRIGGER AS $$
BEGIN
    -- Check if user exists and is active
    IF NOT EXISTS (SELECT 1 FROM users WHERE user_id = NEW.user_id AND is_active = TRUE) THEN
        RAISE EXCEPTION 'User is not active or does not exist';
    END IF;
    
    -- Check if course is available
    IF NOT EXISTS (SELECT 1 FROM courses WHERE course_id = NEW.course_id AND is_available = TRUE) THEN
        RAISE EXCEPTION 'Course is not available';
    END IF;
    
    -- Check for duplicate enrollment
    IF EXISTS (SELECT 1 FROM user_courses WHERE user_id = NEW.user_id AND course_id = NEW.course_id) THEN
        RAISE EXCEPTION 'User is already enrolled in this course';
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for enrollment validation
CREATE TRIGGER validate_enrollment BEFORE INSERT ON user_courses FOR EACH ROW EXECUTE FUNCTION validate_user_enrollment();

-- Create function to update completion date
CREATE OR REPLACE FUNCTION update_completion_date()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status = 'Completed' AND OLD.status != 'Completed' THEN
        NEW.completion_date = CURRENT_TIMESTAMP;
        NEW.progress_percentage = 100;
    ENDIF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for completion date update
CREATE TRIGGER update_completion_date BEFORE UPDATE ON user_courses FOR EACH ROW EXECUTE FUNCTION update_completion_date();

-- Create audit table for tracking changes
CREATE TABLE schema_audit (
    audit_id SERIAL PRIMARY KEY,
    table_name VARCHAR(100) NOT NULL,
    operation VARCHAR(10) NOT NULL,
    record_id INTEGER,
    old_values JSONB,
    new_values JSONB,
    changed_by VARCHAR(100),
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create function for auditing
CREATE OR REPLACE FUNCTION audit_changes()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO schema_audit (table_name, operation, record_id, new_values, changed_by)
        VALUES (TG_TABLE_NAME, 'INSERT', NEW.user_id, to_jsonb(NEW), current_user);
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO schema_audit (table_name, operation, record_id, old_values, new_values, changed_by)
        VALUES (TG_TABLE_NAME, 'UPDATE', NEW.user_id, to_jsonb(OLD), to_jsonb(NEW), current_user);
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO schema_audit (table_name, operation, record_id, old_values, changed_by)
        VALUES (TG_TABLE_NAME, 'DELETE', OLD.user_id, to_jsonb(OLD), current_user);
        RETURN OLD;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Create audit triggers for critical tables
CREATE TRIGGER audit_users AFTER INSERT OR UPDATE OR DELETE ON users FOR EACH ROW EXECUTE FUNCTION audit_changes();
CREATE TRIGGER audit_courses AFTER INSERT OR UPDATE OR DELETE ON courses FOR EACH ROW EXECUTE FUNCTION audit_changes();

-- Insert additional validation data
INSERT INTO roles (role_name, role_description) VALUES 
('HR Manager', 'Human Resources management role'),
('Quality Assurance', 'Quality control and testing specialist');

-- Verify data insertion
DO $$
BEGIN
    IF (SELECT COUNT(*) FROM roles) < 4 THEN
        RAISE EXCEPTION 'Roles data not properly inserted';
    END IF;
    
    IF (SELECT COUNT(*) FROM users) < 5 THEN
        RAISE EXCEPTION 'Users data not properly inserted';
    END IF;
    
    IF (SELECT COUNT(*) FROM courses) < 5 THEN
        RAISE EXCEPTION 'Courses data not properly inserted';
    END IF;
    
    RAISE NOTICE 'Database schema setup completed successfully for AEP-1';
END $$;