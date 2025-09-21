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
CREATE FUNCTION check_role_access(user_id INT, required_role VARCHAR(50)) RETURNS BOOLEAN AS $$
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
-- Example usage:
-- SELECT check_role_access(1, 'admin'); -- Returns TRUE if user has admin role

-- AEP-3: Role-Based Access Control (RBAC) system
-- Ensure proper integration and dependencies

-- End of AEP-3_sql.sql file.