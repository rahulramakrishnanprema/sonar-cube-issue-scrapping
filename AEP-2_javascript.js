const express = require('express');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const { body, validationResult } = require('express-validator');
const rateLimit = require('express-rate-limit');
const { v4: uuidv4 } = require('uuid');

const router = express.Router();

// In-memory storage for demo purposes (replace with database in production)
const users = new Map();
const refreshTokens = new Map();

// JWT configuration
const JWT_SECRET = process.env.JWT_SECRET || 'your-secret-key-change-in-production';
const JWT_REFRESH_SECRET = process.env.JWT_REFRESH_SECRET || 'your-refresh-secret-key-change-in-production';
const JWT_EXPIRES_IN = '15m';
const JWT_REFRESH_EXPIRES_IN = '7d';

// Rate limiting for authentication endpoints
const authLimiter = rateLimit({
    windowMs: 15 * 60 * 1000, // 15 minutes
    max: 5, // limit each IP to 5 requests per windowMs
    message: 'Too many authentication attempts, please try again later',
    standardHeaders: true,
    legacyHeaders: false,
});

// Input validation middleware
const validateRegistration = [
    body('email').isEmail().normalizeEmail().withMessage('Valid email is required'),
    body('password').isLength({ min: 8 }).withMessage('Password must be at least 8 characters'),
    body('firstName').trim().isLength({ min: 1 }).withMessage('First name is required'),
    body('lastName').trim().isLength({ min: 1 }).withMessage('Last name is required')
];

const validateLogin = [
    body('email').isEmail().normalizeEmail().withMessage('Valid email is required'),
    body('password').notEmpty().withMessage('Password is required')
];

// Utility functions
const generateTokens = (userId, email) => {
    const accessToken = jwt.sign(
        { userId, email },
        JWT_SECRET,
        { expiresIn: JWT_EXPIRES_IN }
    );
    
    const refreshToken = jwt.sign(
        { userId, email },
        JWT_REFRESH_SECRET,
        { expiresIn: JWT_REFRESH_EXPIRES_IN }
    );
    
    return { accessToken, refreshToken };
};

const logAuthAttempt = (email, success, ip, userAgent) => {
    console.log(`AEP-2 Auth Attempt: ${email} - ${success ? 'SUCCESS' : 'FAILED'} - IP: ${ip} - User-Agent: ${userAgent}`);
};

// Registration API - AEP-2 Subtask #2
router.post('/register', authLimiter, validateRegistration, async (req, res) => {
    try {
        const errors = validationResult(req);
        if (!errors.isEmpty()) {
            return res.status(400).json({
                success: false,
                message: 'Validation failed',
                errors: errors.array()
            });
        }

        const { email, password, firstName, lastName } = req.body;

        // Check if user already exists
        if (users.has(email)) {
            logAuthAttempt(email, false, req.ip, req.get('User-Agent'));
            return res.status(409).json({
                success: false,
                message: 'User already exists'
            });
        }

        // Hash password
        const saltRounds = 12;
        const hashedPassword = await bcrypt.hash(password, saltRounds);

        // Create user
        const userId = uuidv4();
        const user = {
            id: userId,
            email,
            password: hashedPassword,
            firstName: firstName.trim(),
            lastName: lastName.trim(),
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString()
        };

        users.set(email, user);

        // Generate tokens
        const tokens = generateTokens(userId, email);
        refreshTokens.set(userId, tokens.refreshToken);

        logAuthAttempt(email, true, req.ip, req.get('User-Agent'));

        res.status(201).json({
            success: true,
            message: 'User registered successfully',
            data: {
                user: {
                    id: user.id,
                    email: user.email,
                    firstName: user.firstName,
                    lastName: user.lastName
                },
                tokens: {
                    accessToken: tokens.accessToken,
                    refreshToken: tokens.refreshToken,
                    expiresIn: JWT_EXPIRES_IN
                }
            }
        });

    } catch (error) {
        console.error('AEP-2 Registration Error:', error);
        res.status(500).json({
            success: false,
            message: 'Internal server error during registration'
        });
    }
});

// Login API - AEP-2 Subtask #1
router.post('/login', authLimiter, validateLogin, async (req, res) => {
    try {
        const errors = validationResult(req);
        if (!errors.isEmpty()) {
            return res.status(400).json({
                success: false,
                message: 'Validation failed',
                errors: errors.array()
            });
        }

        const { email, password } = req.body;

        // Find user
        const user = users.get(email);
        if (!user) {
            logAuthAttempt(email, false, req.ip, req.get('User-Agent'));
            return res.status(401).json({
                success: false,
                message: 'Invalid email or password'
            });
        }

        // Verify password
        const isPasswordValid = await bcrypt.compare(password, user.password);
        if (!isPasswordValid) {
            logAuthAttempt(email, false, req.ip, req.get('User-Agent'));
            return res.status(401).json({
                success: false,
                message: 'Invalid email or password'
            });
        }

        // Generate tokens - AEP-2 Subtask #3
        const tokens = generateTokens(user.id, user.email);
        refreshTokens.set(user.id, tokens.refreshToken);

        // Update last login
        user.updatedAt = new Date().toISOString();

        logAuthAttempt(email, true, req.ip, req.get('User-Agent'));

        res.json({
            success: true,
            message: 'Login successful',
            data: {
                user: {
                    id: user.id,
                    email: user.email,
                    firstName: user.firstName,
                    lastName: user.lastName
                },
                tokens: {
                    accessToken: tokens.accessToken,
                    refreshToken: tokens.refreshToken,
                    expiresIn: JWT_EXPIRES_IN
                }
            }
        });

    } catch (error) {
        console.error('AEP-2 Login Error:', error);
        res.status(500).json({
            success: false,
            message: 'Internal server error during login'
        });
    }
});

// Refresh token endpoint
router.post('/refresh', async (req, res) => {
    try {
        const { refreshToken } = req.body;

        if (!refreshToken) {
            return res.status(400).json({
                success: false,
                message: 'Refresh token is required'
            });
        }

        // Verify refresh token
        let decoded;
        try {
            decoded = jwt.verify(refreshToken, JWT_REFRESH_SECRET);
        } catch (error) {
            return res.status(401).json({
                success: false,
                message: 'Invalid refresh token'
            });
        }

        // Check if refresh token exists in storage
        const storedRefreshToken = refreshTokens.get(decoded.userId);
        if (!storedRefreshToken || storedRefreshToken !== refreshToken) {
            return res.status(401).json({
                success: false,
                message: 'Refresh token not found'
            });
        }

        // Generate new tokens
        const tokens = generateTokens(decoded.userId, decoded.email);
        refreshTokens.set(decoded.userId, tokens.refreshToken);

        res.json({
            success: true,
            message: 'Token refreshed successfully',
            data: {
                accessToken: tokens.accessToken,
                refreshToken: tokens.refreshToken,
                expiresIn: JWT_EXPIRES_IN
            }
        });

    } catch (error) {
        console.error('AEP-2 Refresh Token Error:', error);
        res.status(500).json({
            success: false,
            message: 'Internal server error during token refresh'
        });
    }
});

// Logout endpoint
router.post('/logout', async (req, res) => {
    try {
        const authHeader = req.headers.authorization;
        if (!authHeader || !authHeader.startsWith('Bearer ')) {
            return res.status(401).json({
                success: false,
                message: 'Authorization header required'
            });
        }

        const token = authHeader.substring(7);
        
        try {
            const decoded = jwt.verify(token, JWT_SECRET);
            refreshTokens.delete(decoded.userId);
            
            res.json({
                success: true,
                message: 'Logout successful'
            });
        } catch (error) {
            return res.status(401).json({
                success: false,
                message: 'Invalid token'
            });
        }

    } catch (error) {
        console.error('AEP-2 Logout Error:', error);
        res.status(500).json({
            success: false,
            message: 'Internal server error during logout'
        });
    }
});

// Health check endpoint
router.get('/health', (req, res) => {
    res.json({
        success: true,
        message: 'Authentication API is running',
        timestamp: new Date().toISOString()
    });
});

module.exports = router;