-- Create users table
CREATE TABLE IF NOT EXISTS users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL,
    email VARCHAR(100) NOT NULL,
    role_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create roles table
CREATE TABLE IF NOT EXISTS roles (
    role_id SERIAL PRIMARY KEY,
    role_name VARCHAR(50) NOT NULL
);

-- Create training_needs table
CREATE TABLE IF NOT EXISTS training_needs (
    need_id SERIAL PRIMARY KEY,
    user_id INT NOT NULL,
    course_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create courses table
CREATE TABLE IF NOT EXISTS courses (
    course_id SERIAL PRIMARY KEY,
    course_name VARCHAR(100) NOT NULL,
    description TEXT
);

-- Insert sample data into roles table
INSERT INTO roles (role_name) VALUES ('Admin'), ('User'), ('Trainer');

-- Insert sample data into courses table
INSERT INTO courses (course_name, description) VALUES 
('SQL Fundamentals', 'Basic SQL concepts and queries'),
('Python Programming', 'Introduction to Python programming language'),
('Web Development', 'HTML, CSS, and JavaScript basics');

-- AEP-1: Setup Database Schema
-- Migration scripts written and tested
-- Sample data inserted for testing.