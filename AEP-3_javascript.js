const express = require('express');
const jwt = require('jsonwebtoken');
const { Pool } = require('pg');
const winston = require('winston');

// Logger configuration
const logger = winston.createLogger({
    level: 'info',
    format: winston.format.combine(
        winston.format.timestamp(),
        winston.format.json()
    ),
    transports: [
        new winston.transports.File({ filename: 'error.log', level: 'error' }),
        new winston.transports.File({ filename: 'combined.log' })
    ]
});

if (process.env.NODE_ENV !== 'production') {
    logger.add(new winston.transports.Console({
        format: winston.format.simple()
    }));
}

// Database connection pool
const pool = new Pool({
    user: process.env.DB_USER || 'admin',
    host: process.env.DB_HOST || 'localhost',
    database: process.env.DB_NAME || 'rbac_db',
    password: process.env.DB_PASSWORD || 'password',
    port: process.env.DB_PORT || 5432,
    max: 20,
    idleTimeoutMillis: 30000,
    connectionTimeoutMillis: 2000,
});

// Role definitions
const ROLES = {
    EMPLOYEE: 'employee',
    MANAGER: 'manager',
    ADMIN: 'admin'
};

// Route permissions mapping
const ROUTE_PERMISSIONS = {
    '/api/users': [ROLES.ADMIN, ROLES.MANAGER],
    '/api/users/:id': [ROLES.ADMIN, ROLES.MANAGER],
    '/api/reports': [ROLES.ADMIN, ROLES.MANAGER],
    '/api/admin': [ROLES.ADMIN],
    '/api/settings': [ROLES.ADMIN, ROLES.MANAGER],
    '/api/tasks': [ROLES.EMPLOYEE, ROLES.MANAGER, ROLES.ADMIN],
    '/api/tasks/:id': [ROLES.EMPLOYEE, ROLES.MANAGER, ROLES.ADMIN]
};

// AEP-3: RBAC Middleware
const rbacMiddleware = async (req, res, next) => {
    try {
        const token = req.header('Authorization')?.replace('Bearer ', '');
        
        if (!token) {
            logger.warn('Access attempt without token', { path: req.path });
            return res.status(401).json({ 
                error: 'Access denied. No token provided.',
                code: 'AUTH_NO_TOKEN'
            });
        }

        const decoded = jwt.verify(token, process.env.JWT_SECRET || 'fallback_secret');
        req.user = decoded;

        // Get user role from database
        const userQuery = 'SELECT role FROM users WHERE id = $1';
        const userResult = await pool.query(userQuery, [decoded.userId]);
        
        if (userResult.rows.length === 0) {
            logger.warn('User not found in database', { userId: decoded.userId });
            return res.status(401).json({ 
                error: 'User not found.',
                code: 'USER_NOT_FOUND'
            });
        }

        const userRole = userResult.rows[0].role;
        
        // Check if user role is valid
        if (!Object.values(ROLES).includes(userRole)) {
            logger.error('Invalid user role', { userId: decoded.userId, role: userRole });
            return res.status(403).json({ 
                error: 'Invalid user role.',
                code: 'INVALID_ROLE'
            });
        }

        // Check route permissions
        const routePath = req.baseUrl + req.path;
        const hasPermission = checkRoutePermission(routePath, req.method, userRole);
        
        if (!hasPermission) {
            logger.warn('Unauthorized access attempt', { 
                userId: decoded.userId, 
                role: userRole, 
                path: routePath,
                method: req.method 
            });
            return res.status(403).json({ 
                error: 'Access denied. Insufficient permissions.',
                code: 'INSUFFICIENT_PERMISSIONS'
            });
        }

        logger.info('Access granted', { 
            userId: decoded.userId, 
            role: userRole, 
            path: routePath 
        });
        
        next();
    } catch (error) {
        if (error.name === 'JsonWebTokenError') {
            logger.warn('Invalid token', { error: error.message });
            return res.status(401).json({ 
                error: 'Invalid token.',
                code: 'INVALID_TOKEN'
            });
        }
        
        if (error.name === 'TokenExpiredError') {
            logger.warn('Token expired', { error: error.message });
            return res.status(401).json({ 
                error: 'Token expired.',
                code: 'TOKEN_EXPIRED'
            });
        }

        logger.error('RBAC middleware error', { error: error.message });
        res.status(500).json({ 
            error: 'Internal server error.',
            code: 'SERVER_ERROR'
        });
    }
};

// Helper function to check route permissions
function checkRoutePermission(routePath, method, userRole) {
    // Find matching route pattern
    const matchingRoute = Object.keys(ROUTE_PERMISSIONS).find(routePattern => {
        const pattern = new RegExp('^' + routePattern.replace(/:\w+/g, '\\w+') + '$');
        return pattern.test(routePath);
    });

    if (!matchingRoute) {
        // Route not defined in permissions - default deny
        return false;
    }

    const allowedRoles = ROUTE_PERMISSIONS[matchingRoute];
    return allowedRoles.includes(userRole);
}

// Database initialization function for roles
async function initializeRoles() {
    try {
        // Check if roles table exists
        const checkTableQuery = `
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'roles'
            );
        `;
        
        const tableExists = await pool.query(checkTableQuery);
        
        if (!tableExists.rows[0].exists) {
            // Create roles table
            const createTableQuery = `
                CREATE TABLE roles (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(50) UNIQUE NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            `;
            
            await pool.query(createTableQuery);
            logger.info('Roles table created');
            
            // Insert default roles
            const insertRolesQuery = `
                INSERT INTO roles (name, description) VALUES
                ('employee', 'Regular employee with basic access'),
                ('manager', 'Manager with elevated permissions'),
                ('admin', 'System administrator with full access')
                ON CONFLICT (name) DO NOTHING;
            `;
            
            await pool.query(insertRolesQuery);
            logger.info('Default roles inserted');
        }
        
        // Add role column to users table if it doesn't exist
        const checkColumnQuery = `
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'users' AND column_name = 'role';
        `;
        
        const columnExists = await pool.query(checkColumnQuery);
        
        if (columnExists.rows.length === 0) {
            const alterTableQuery = `
                ALTER TABLE users 
                ADD COLUMN role VARCHAR(50) NOT NULL DEFAULT 'employee',
                ADD CONSTRAINT fk_user_role 
                FOREIGN KEY (role) REFERENCES roles(name);
            `;
            
            await pool.query(alterTableQuery);
            logger.info('Role column added to users table');
        }
        
    } catch (error) {
        logger.error('Failed to initialize roles', { error: error.message });
        throw error;
    }
}

// Utility function to get user role
async function getUserRole(userId) {
    try {
        const query = 'SELECT role FROM users WHERE id = $1';
        const result = await pool.query(query, [userId]);
        
        if (result.rows.length === 0) {
            throw new Error('User not found');
        }
        
        return result.rows[0].role;
    } catch (error) {
        logger.error('Error getting user role', { userId, error: error.message });
        throw error;
    }
}

// Utility function to update user role (admin only)
async function updateUserRole(userId, newRole) {
    try {
        // Validate role exists
        const roleCheckQuery = 'SELECT name FROM roles WHERE name = $1';
        const roleCheck = await pool.query(roleCheckQuery, [newRole]);
        
        if (roleCheck.rows.length === 0) {
            throw new Error('Invalid role');
        }
        
        const updateQuery = 'UPDATE users SET role = $1, updated_at = CURRENT_TIMESTAMP WHERE id = $2 RETURNING *';
        const result = await pool.query(updateQuery, [newRole, userId]);
        
        if (result.rows.length === 0) {
            throw new Error('User not found');
        }
        
        logger.info('User role updated', { userId, newRole });
        return result.rows[0];
    } catch (error) {
        logger.error('Error updating user role', { userId, newRole, error: error.message });
        throw error;
    }
}

// Health check endpoint for RBAC system
function createRbacHealthCheck() {
    return async (req, res) => {
        try {
            // Check database connection
            await pool.query('SELECT 1');
            
            // Check roles table exists and has data
            const rolesCheck = await pool.query('SELECT COUNT(*) FROM roles');
            
            res.json({
                status: 'healthy',
                database: 'connected',
                rolesCount: parseInt(rolesCheck.rows[0].count),
                timestamp: new Date().toISOString()
            });
        } catch (error) {
            logger.error('RBAC health check failed', { error: error.message });
            res.status(500).json({
                status: 'unhealthy',
                error: error.message,
                timestamp: new Date().toISOString()
            });
        }
    };
}

// Export middleware and utilities
module.exports = {
    rbacMiddleware,
    initializeRoles,
    getUserRole,
    updateUserRole,
    createRbacHealthCheck,
    ROLES
};