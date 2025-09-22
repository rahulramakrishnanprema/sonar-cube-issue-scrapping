-- Create table to store roles
CREATE TABLE roles (
    role_id INT PRIMARY KEY,
    role_name VARCHAR(50) NOT NULL
);

-- Insert roles into roles table
INSERT INTO roles (role_id, role_name) VALUES (1, 'employee');
INSERT INTO roles (role_id, role_name) VALUES (2, 'manager');
INSERT INTO roles (role_id, role_name) VALUES (3, 'admin');

-- Create table to store user roles
CREATE TABLE user_roles (
    user_id INT,
    role_id INT,
    PRIMARY KEY (user_id, role_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (role_id) REFERENCES roles(role_id)
);

-- Middleware for RBAC
CREATE FUNCTION check_role_permission(user_id INT, required_role VARCHAR(50)) RETURNS BOOLEAN AS $$
DECLARE
    user_role VARCHAR(50);
BEGIN
    SELECT role_name INTO user_role
    FROM roles
    JOIN user_roles ON roles.role_id = user_roles.role_id
    WHERE user_roles.user_id = user_id;
    
    IF user_role = required_role THEN
        RETURN TRUE;
    ELSE
        RETURN FALSE;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Test endpoints with different roles
CREATE FUNCTION test_endpoint(user_id INT, required_role VARCHAR(50)) RETURNS BOOLEAN AS $$
BEGIN
    IF check_role_permission(user_id, required_role) THEN
        RETURN TRUE;
    ELSE
        RAISE EXCEPTION 'Unauthorized access';
    END IF;
END;
$$ LANGUAGE plpgsql;

-- AEP-3: Role-Based Access Control (RBAC) implementation
-- Ensure proper integration and dependencies with other project files.