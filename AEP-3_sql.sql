-- AEP-3: Role-Based Access Control (RBAC) SQL Implementation
-- This script creates the necessary database schema for RBAC functionality

-- Create roles table to store system roles
CREATE TABLE IF NOT EXISTS roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- Create users_roles table for role assignments
CREATE TABLE IF NOT EXISTS users_roles (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    role_id INTEGER NOT NULL,
    assigned_by INTEGER,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    CONSTRAINT fk_role FOREIGN KEY(role_id) REFERENCES roles(id) ON DELETE CASCADE,
    CONSTRAINT unique_user_role UNIQUE(user_id, role_id)
);

-- Create permissions table for granular access control
CREATE TABLE IF NOT EXISTS permissions (
    id SERIAL PRIMARY KEY,
    code VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    category VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- Create role_permissions table to assign permissions to roles
CREATE TABLE IF NOT EXISTS role_permissions (
    id SERIAL PRIMARY KEY,
    role_id INTEGER NOT NULL,
    permission_id INTEGER NOT NULL,
    granted_by INTEGER,
    granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_role_permission_role FOREIGN KEY(role_id) REFERENCES roles(id) ON DELETE CASCADE,
    CONSTRAINT fk_role_permission_permission FOREIGN KEY(permission_id) REFERENCES permissions(id) ON DELETE CASCADE,
    CONSTRAINT unique_role_permission UNIQUE(role_id, permission_id)
);

-- Create audit log table for RBAC changes
CREATE TABLE IF NOT EXISTS rbac_audit_log (
    id SERIAL PRIMARY KEY,
    action_type VARCHAR(50) NOT NULL,
    target_type VARCHAR(50) NOT NULL,
    target_id INTEGER,
    performed_by INTEGER NOT NULL,
    performed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    old_values JSONB,
    new_values JSONB,
    ip_address VARCHAR(45),
    user_agent TEXT
);

-- Insert default system roles
INSERT INTO roles (name, description) VALUES
('admin', 'System administrator with full access to all features and settings'),
('manager', 'Manager role with elevated permissions for team management'),
('employee', 'Standard employee role with basic access permissions')
ON CONFLICT (name) DO NOTHING;

-- Insert common permissions
INSERT INTO permissions (code, name, description, category) VALUES
-- User management permissions
('users:read', 'View Users', 'Permission to view user profiles and lists', 'user_management'),
('users:create', 'Create Users', 'Permission to create new user accounts', 'user_management'),
('users:update', 'Update Users', 'Permission to modify user information', 'user_management'),
('users:delete', 'Delete Users', 'Permission to deactivate or delete users', 'user_management'),

-- Role management permissions
('roles:read', 'View Roles', 'Permission to view role definitions', 'role_management'),
('roles:create', 'Create Roles', 'Permission to create new roles', 'role_management'),
('roles:update', 'Update Roles', 'Permission to modify role properties', 'role_management'),
('roles:delete', 'Delete Roles', 'Permission to delete roles', 'role_management'),
('roles:assign', 'Assign Roles', 'Permission to assign roles to users', 'role_management'),

-- Permission management
('permissions:read', 'View Permissions', 'Permission to view system permissions', 'permission_management'),
('permissions:assign', 'Assign Permissions', 'Permission to assign permissions to roles', 'permission_management'),

-- Content permissions
('content:read', 'View Content', 'Permission to view general content', 'content'),
('content:create', 'Create Content', 'Permission to create new content', 'content'),
('content:update', 'Update Content', 'Permission to modify existing content', 'content'),
('content:delete', 'Delete Content', 'Permission to remove content', 'content'),

-- System permissions
('system:settings', 'System Settings', 'Access to system configuration', 'system'),
('system:reports', 'View Reports', 'Access to system reports and analytics', 'system'),
('system:audit', 'View Audit Logs', 'Access to system audit logs', 'system')
ON CONFLICT (code) DO NOTHING;

-- Assign permissions to admin role (all permissions)
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.name = 'admin'
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- Assign basic permissions to manager role
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.name = 'manager'
AND p.code IN (
    'users:read',
    'users:create',
    'users:update',
    'roles:read',
    'permissions:read',
    'content:read',
    'content:create',
    'content:update',
    'content:delete',
    'system:reports'
)
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- Assign basic permissions to employee role
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.name = 'employee'
AND p.code IN (
    'users:read',
    'content:read',
    'content:create',
    'content:update'
)
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_users_roles_user_id ON users_roles(user_id);
CREATE INDEX IF NOT EXISTS idx_users_roles_role_id ON users_roles(role_id);
CREATE INDEX IF NOT EXISTS idx_users_roles_active ON users_roles(is_active);
CREATE INDEX IF NOT EXISTS idx_role_permissions_role_id ON role_permissions(role_id);
CREATE INDEX IF NOT EXISTS idx_role_permissions_permission_id ON role_permissions(permission_id);
CREATE INDEX IF NOT EXISTS idx_rbac_audit_performed_by ON rbac_audit_log(performed_by);
CREATE INDEX IF NOT EXISTS idx_rbac_audit_action_type ON rbac_audit_log(action_type);
CREATE INDEX IF NOT EXISTS idx_roles_active ON roles(is_active);
CREATE INDEX IF NOT EXISTS idx_permissions_active ON permissions(is_active);

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger for roles table
CREATE TRIGGER update_roles_updated_at 
    BEFORE UPDATE ON roles 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Create view for user roles with permissions
CREATE OR REPLACE VIEW user_roles_with_permissions AS
SELECT 
    ur.user_id,
    r.id as role_id,
    r.name as role_name,
    p.code as permission_code,
    p.name as permission_name,
    p.category as permission_category
FROM users_roles ur
JOIN roles r ON ur.role_id = r.id AND r.is_active = TRUE
JOIN role_permissions rp ON r.id = rp.role_id
JOIN permissions p ON rp.permission_id = p.id AND p.is_active = TRUE
WHERE ur.is_active = TRUE AND ur.expires_at IS NULL OR ur.expires_at > CURRENT_TIMESTAMP;

-- Create function to check user permission
CREATE OR REPLACE FUNCTION check_user_permission(
    p_user_id INTEGER,
    p_permission_code VARCHAR
) RETURNS BOOLEAN AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 
        FROM user_roles_with_permissions 
        WHERE user_id = p_user_id 
        AND permission_code = p_permission_code
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Create function to get user permissions
CREATE OR REPLACE FUNCTION get_user_permissions(
    p_user_id INTEGER
) RETURNS TABLE(permission_code VARCHAR, permission_name VARCHAR, category VARCHAR) AS $$
BEGIN
    RETURN QUERY
    SELECT DISTINCT 
        urwp.permission_code,
        urwp.permission_name,
        urwp.permission_category
    FROM user_roles_with_permissions urwp
    WHERE urwp.user_id = p_user_id
    ORDER BY urwp.permission_category, urwp.permission_code;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Create function to log RBAC actions
CREATE OR REPLACE FUNCTION log_rbac_action(
    p_action_type VARCHAR,
    p_target_type VARCHAR,
    p_target_id INTEGER,
    p_performed_by INTEGER,
    p_old_values JSONB,
    p_new_values JSONB,
    p_ip_address VARCHAR DEFAULT NULL,
    p_user_agent TEXT DEFAULT NULL
) RETURNS VOID AS $$
BEGIN
    INSERT INTO rbac_audit_log (
        action_type,
        target_type,
        target_id,
        performed_by,
        old_values,
        new_values,
        ip_address,
        user_agent
    ) VALUES (
        p_action_type,
        p_target_type,
        p_target_id,
        p_performed_by,
        p_old_values,
        p_new_values,
        p_ip_address,
        p_user_agent
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Create function to assign role to user
CREATE OR REPLACE FUNCTION assign_role_to_user(
    p_user_id INTEGER,
    p_role_id INTEGER,
    p_assigned_by INTEGER,
    p_expires_at TIMESTAMP DEFAULT NULL
) RETURNS VOID AS $$
BEGIN
    -- Check if role exists and is active
    IF NOT EXISTS (SELECT 1 FROM roles WHERE id = p_role_id AND is_active = TRUE) THEN
        RAISE EXCEPTION 'Role not found or inactive';
    END IF;

    -- Insert or update role assignment
    INSERT INTO users_roles (user_id, role_id, assigned_by, expires_at, is_active)
    VALUES (p_user_id, p_role_id, p_assigned_by, p_expires_at, TRUE)
    ON CONFLICT (user_id, role_id) 
    DO UPDATE SET 
        assigned_by = p_assigned_by,
        expires_at = p_expires_at,
        is_active = TRUE,
        assigned_at = CURRENT_TIMESTAMP;

    -- Log the action
    PERFORM log_rbac_action(
        'ASSIGN_ROLE',
        'USER_ROLE',
        NULL,
        p_assigned_by,
        NULL,
        jsonb_build_object('user_id', p_user_id, 'role_id', p_role_id)
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Create function to revoke role from user
CREATE OR REPLACE FUNCTION revoke_role_from_user(
    p_user_id INTEGER,
    p_role_id INTEGER,
    p_revoked_by INTEGER
) RETURNS VOID AS $$
BEGIN
    -- Update the role assignment to inactive
    UPDATE users_roles 
    SET is_active = FALSE,
        assigned_by = p_revoked_by,
        assigned_at = CURRENT_TIMESTAMP
    WHERE user_id = p_user_id 
    AND role_id = p_role_id 
    AND is_active = TRUE;

    -- Log the action
    PERFORM log_rbac_action(
        'REVOKE_ROLE',
        'USER_ROLE',
        NULL,
        p_revoked_by,
        jsonb_build_object('user_id', p_user_id, 'role_id', p_role_id),
        NULL
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Add comments to tables and columns
COMMENT ON TABLE roles IS 'Stores system roles for RBAC implementation (AEP-3)';
COMMENT ON TABLE users_roles IS 'Maps users to their assigned roles (AEP-3)';
COMMENT ON TABLE permissions IS 'Stores granular permissions for RBAC system (AEP-3)';
COMMENT ON TABLE role_permissions IS 'Maps permissions to roles (AEP-3)';
COMMENT ON TABLE rbac_audit_log IS 'Audit log for RBAC-related actions (AEP-3)';

COMMENT ON COLUMN roles.name IS 'Unique role identifier name';
COMMENT ON COLUMN users_roles.expires_at IS 'Optional expiration date for role assignment';
COMMENT ON COLUMN permissions.code IS 'Unique permission code used in application logic';

-- Grant necessary permissions (adjust based on your database user)
GRANT SELECT ON roles TO application_user;
GRANT SELECT ON users_roles TO application_user;
GRANT SELECT ON permissions TO application_user;
GRANT SELECT ON role_permissions TO application_user;
GRANT SELECT ON rbac_audit_log TO application_user;
GRANT EXECUTE ON FUNCTION check_user_permission TO application_user;
GRANT EXECUTE ON FUNCTION get_user_permissions TO application_user;
GRANT EXECUTE ON FUNCTION assign_role_to_user TO application_user;
GRANT EXECUTE ON FUNCTION revoke_role_from_user TO application_user;
GRANT SELECT ON user_roles_with_permissions TO application_user;