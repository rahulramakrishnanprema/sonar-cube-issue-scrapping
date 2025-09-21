const express = require('express');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const { body, validationResult } = require('express-validator');
const rateLimit = require('express-rate-limit');

const router = express.Router();

// In-memory user store (replace with database in production)
const users = new Map();
const JWT_SECRET = process.env.JWT_SECRET || 'your-secret-key-change-in-production';
const JWT_EXPIRY = process.env.JWT_EXPIRY || '1h';

// Rate limiting for authentication endpoints
const authLimiter = rateLimit({
    windowMs: 15 * 60 * 1000, // 15 minutes
    max: 5, // limit each IP to 5 requests per windowMs
    message: 'Too many authentication attempts, please try again later.',
    standardHeaders: true,
    legacyHeaders: false,
});

// Input validation middleware
const validateRegistration = [
    body('email').isEmail().normalizeEmail().withMessage('Valid email is required'),
    body('password').isLength({ min: 6 }).withMessage('Password must be at least 6 characters'),
    body('name').trim().notEmpty().withMessage('Name is required')
];

const validateLogin = [
    body('email').isEmail().normalizeEmail().withMessage('Valid email is required'),
    body('password').notEmpty().withMessage('Password is required')
];

// Error handling middleware
const handleValidationErrors = (req, res, next) => {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
        return res.status(400).json({
            success: false,
            message: 'Validation failed',
            errors: errors.array()
        });
    }
    next();
};

// AEP-2: Registration API
router.post('/register', authLimiter, validateRegistration, handleValidationErrors, async (req, res) => {
    try {
        const { email, password, name } = req.body;

        // Check if user already exists
        if (users.has(email)) {
            return res.status(409).json({
                success: false,
                message: 'User already exists'
            });
        }

        // Hash password
        const saltRounds = 10;
        const hashedPassword = await bcrypt.hash(password, saltRounds);

        // Store user
        users.set(email, {
            email,
            password: hashedPassword,
            name,
            createdAt: new Date()
        });

        // Generate JWT token
        const token = jwt.sign(
            { email, name },
            JWT_SECRET,
            { expiresIn: JWT_EXPIRY }
        );

        console.log(`User registered successfully: ${email}`);
        
        res.status(201).json({
            success: true,
            message: 'User registered successfully',
            token,
            user: { email, name }
        });

    } catch (error) {
        console.error('Registration error:', error);
        res.status(500).json({
            success: false,
            message: 'Internal server error during registration'
        });
    }
});

// AEP-2: Login API
router.post('/login', authLimiter, validateLogin, handleValidationErrors, async (req, res) => {
    try {
        const { email, password } = req.body;

        // Find user
        const user = users.get(email);
        if (!user) {
            console.warn(`Login attempt failed: User not found - ${email}`);
            return res.status(401).json({
                success: false,
                message: 'Invalid email or password'
            });
        }

        // Verify password
        const isPasswordValid = await bcrypt.compare(password, user.password);
        if (!isPasswordValid) {
            console.warn(`Login attempt failed: Invalid password - ${email}`);
            return res.status(401).json({
                success: false,
                message: 'Invalid email or password'
            });
        }

        // Generate JWT token
        const token = jwt.sign(
            { email: user.email, name: user.name },
            JWT_SECRET,
            { expiresIn: JWT_EXPIRY }
        );

        console.log(`User logged in successfully: ${email}`);
        
        res.json({
            success: true,
            message: 'Login successful',
            token,
            user: {
                email: user.email,
                name: user.name
            }
        });

    } catch (error) {
        console.error('Login error:', error);
        res.status(500).json({
            success: false,
            message: 'Internal server error during login'
        });
    }
});

// Token verification middleware (for protected routes)
const verifyToken = (req, res, next) => {
    const token = req.header('Authorization')?.replace('Bearer ', '');
    
    if (!token) {
        return res.status(401).json({
            success: false,
            message: 'Access denied. No token provided.'
        });
    }

    try {
        const verified = jwt.verify(token, JWT_SECRET);
        req.user = verified;
        next();
    } catch (error) {
        console.error('Token verification failed:', error);
        res.status(400).json({
            success: false,
            message: 'Invalid token'
        });
    }
};

// Protected route example
router.get('/profile', verifyToken, (req, res) => {
    const user = users.get(req.user.email);
    if (!user) {
        return res.status(404).json({
            success: false,
            message: 'User not found'
        });
    }

    res.json({
        success: true,
        user: {
            email: user.email,
            name: user.name,
            createdAt: user.createdAt
        }
    });
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