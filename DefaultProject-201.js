# Generated for DefaultProject-201 | 2025-09-21 06:12:07 | Developer Agent v2.0
# AutoFlow-Dashboard Enhanced Code Generation
# Thread: d44a8b52 | LangChain: Template-Enhanced Generation
# Workflow Stage: Code Generation (NO PR creation)

const express = require('express');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const crypto = require('crypto');
const nodemailer = require('nodemailer');
const rateLimit = require('express-rate-limit');
const helmet = require('helmet');
const cors = require('cors');
const { body, validationResult } = require('express-validator');

// DefaultProject-201: User Authentication System Implementation
class DefaultProjectAuth {
    constructor() {
        this.app = express();
        this.secretKey = process.env.JWT_SECRET || crypto.randomBytes(64).toString('hex');
        this.refreshTokens = new Map();
        this.passwordResetTokens = new Map();
        this.users = new Map();
        this.initializeMiddleware();
        this.initializeRoutes();
    }

    initializeMiddleware() {
        this.app.use(helmet());
        this.app.use(cors());
        this.app.use(express.json({ limit: '10kb' }));
        
        const authLimiter = rateLimit({
            windowMs: 15 * 60 * 1000,
            max: 5,
            message: 'Too many authentication attempts, please try again later.'
        });
        
        this.app.use('/auth/login', authLimiter);
        this.app.use('/auth/register', authLimiter);
    }

    initializeRoutes() {
        // Health check endpoint
        this.app.get('/health', (req, res) => {
            res.status(200).json({ status: 'OK', timestamp: new Date().toISOString() });
        });

        // Registration endpoint
        this.app.post('/auth/register', [
            body('email').isEmail().normalizeEmail(),
            body('password').isLength({ min: 8 }).withMessage('Password must be at least 8 characters'),
            body('username').isLength({ min: 3 }).withMessage('Username must be at least 3 characters')
        ], this.handleRegistration.bind(this));

        // Login endpoint
        this.app.post('/auth/login', [
            body('email').isEmail().normalizeEmail(),
            body('password').exists().withMessage('Password is required')
        ], this.handleLogin.bind(this));

        // Refresh token endpoint
        this.app.post('/auth/refresh', this.handleRefreshToken.bind(this));

        // Password reset request
        this.app.post('/auth/password-reset-request', [
            body('email').isEmail().normalizeEmail()
        ], this.handlePasswordResetRequest.bind(this));

        // Password reset confirmation
        this.app.post('/auth/password-reset-confirm', [
            body('token').exists().withMessage('Reset token is required'),
            body('newPassword').isLength({ min: 8 }).withMessage('New password must be at least 8 characters')
        ], this.handlePasswordResetConfirm.bind(this));

        // Logout endpoint
        this.app.post('/auth/logout', this.authenticateToken.bind(this), this.handleLogout.bind(this));

        // Protected route example
        this.app.get('/auth/profile', this.authenticateToken.bind(this), this.handleProfile.bind(this));
    }

    async handleRegistration(req, res) {
        try {
            const errors = validationResult(req);
            if (!errors.isEmpty()) {
                return res.status(400).json({ 
                    error: 'Validation failed', 
                    details: errors.array() 
                });
            }

            const { email, password, username } = req.body;

            if (this.users.has(email)) {
                return res.status(409).json({ error: 'User already exists' });
            }

            const hashedPassword = await bcrypt.hash(password, 12);
            const user = {
                email,
                username,
                password: hashedPassword,
                createdAt: new Date(),
                isVerified: false
            };

            this.users.set(email, user);
            
            console.log(`User registered: ${email}`);
            res.status(201).json({ message: 'User registered successfully' });

        } catch (error) {
            console.error('Registration error:', error);
            res.status(500).json({ error: 'Internal server error' });
        }
    }

    async handleLogin(req, res) {
        try {
            const errors = validationResult(req);
            if (!errors.isEmpty()) {
                return res.status(400).json({ 
                    error: 'Validation failed', 
                    details: errors.array() 
                });
            }

            const { email, password } = req.body;
            const user = this.users.get(email);

            if (!user || !(await bcrypt.compare(password, user.password))) {
                return res.status(401).json({ error: 'Invalid credentials' });
            }

            const accessToken = this.generateAccessToken(user);
            const refreshToken = crypto.randomBytes(64).toString('hex');
            
            this.refreshTokens.set(refreshToken, {
                email: user.email,
                expiresAt: Date.now() + 7 * 24 * 60 * 60 * 1000 // 7 days
            });

            console.log(`User logged in: ${email}`);
            res.json({
                accessToken,
                refreshToken,
                expiresIn: 3600,
                user: { email: user.email, username: user.username }
            });

        } catch (error) {
            console.error('Login error:', error);
            res.status(500).json({ error: 'Internal server error' });
        }
    }

    handleRefreshToken(req, res) {
        try {
            const { refreshToken } = req.body;
            
            if (!refreshToken || !this.refreshTokens.has(refreshToken)) {
                return res.status(401).json({ error: 'Invalid refresh token' });
            }

            const tokenData = this.refreshTokens.get(refreshToken);
            if (tokenData.expiresAt < Date.now()) {
                this.refreshTokens.delete(refreshToken);
                return res.status(401).json({ error: 'Refresh token expired' });
            }

            const user = this.users.get(tokenData.email);
            if (!user) {
                return res.status(401).json({ error: 'User not found' });
            }

            const newAccessToken = this.generateAccessToken(user);
            
            console.log(`Token refreshed for: ${user.email}`);
            res.json({ accessToken: newAccessToken, expiresIn: 3600 });

        } catch (error) {
            console.error('Refresh token error:', error);
            res.status(500).json({ error: 'Internal server error' });
        }
    }

    async handlePasswordResetRequest(req, res) {
        try {
            const errors = validationResult(req);
            if (!errors.isEmpty()) {
                return res.status(400).json({ 
                    error: 'Validation failed', 
                    details: errors.array() 
                });
            }

            const { email } = req.body;
            const user = this.users.get(email);

            if (!user) {
                // Don't reveal whether email exists
                return res.json({ message: 'If the email exists, a reset link has been sent' });
            }

            const resetToken = crypto.randomBytes(32).toString('hex');
            const expiresAt = Date.now() + 3600000; // 1 hour

            this.passwordResetTokens.set(resetToken, {
                email: user.email,
                expiresAt
            });

            // In production, implement actual email sending
            console.log(`Password reset token for ${email}: ${resetToken}`);
            
            res.json({ message: 'If the email exists, a reset link has been sent' });

        } catch (error) {
            console.error('Password reset request error:', error);
            res.status(500).json({ error: 'Internal server error' });
        }
    }

    async handlePasswordResetConfirm(req, res) {
        try {
            const errors = validationResult(req);
            if (!errors.isEmpty()) {
                return res.status(400).json({ 
                    error: 'Validation failed', 
                    details: errors.array() 
                });
            }

            const { token, newPassword } = req.body;
            
            if (!this.passwordResetTokens.has(token)) {
                return res.status(400).json({ error: 'Invalid or expired reset token' });
            }

            const tokenData = this.passwordResetTokens.get(token);
            if (tokenData.expiresAt < Date.now()) {
                this.passwordResetTokens.delete(token);
                return res.status(400).json({ error: 'Reset token expired' });
            }

            const user = this.users.get(tokenData.email);
            if (!user) {
                return res.status(400).json({ error: 'User not found' });
            }

            user.password = await bcrypt.hash(newPassword, 12);
            this.passwordResetTokens.delete(token);
            
            console.log(`Password reset for: ${user.email}`);
            res.json({ message: 'Password reset successfully' });

        } catch (error) {
            console.error('Password reset confirm error:', error);
            res.status(500).json({ error: 'Internal server error' });
        }
    }

    handleLogout(req, res) {
        try {
            const refreshToken = req.body.refreshToken;
            if (refreshToken) {
                this.refreshTokens.delete(refreshToken);
            }
            
            console.log(`User logged out: ${req.user.email}`);
            res.json({ message: 'Logged out successfully' });

        } catch (error) {
            console.error('Logout error:', error);
            res.status(500).json({ error: 'Internal server error' });
        }
    }

    handleProfile(req, res) {
        try {
            const user = this.users.get(req.user.email);
            if (!user) {
                return res.status(404).json({ error: 'User not found' });
            }

            res.json({
                email: user.email,
                username: user.username,
                createdAt: user.createdAt
            });

        } catch (error) {
            console.error('Profile error:', error);
            res.status(500).json({ error: 'Internal server error' });
        }
    }

    authenticateToken(req, res, next) {
        try {
            const authHeader = req.headers['authorization'];
            const token = authHeader && authHeader.split(' ')[1];

            if (!token) {
                return res.status(401).json({ error: 'Access token required' });
            }

            jwt.verify(token, this.secretKey, (err, user) => {
                if (err) {
                    return res.status(403).json({ error: 'Invalid or expired token' });
                }
                req.user = user;
                next();
            });

        } catch (error) {
            console.error('Authentication error:', error);
            res.status(500).json({ error: 'Internal server error' });
        }
    }

    generateAccessToken(user) {
        return jwt.sign(
            { email: user.email, username: user.username },
            this.secretKey,
            { expiresIn: '1h' }
        );
    }

    start(port = 3000) {
        this.app.listen(port, () => {
            console.log(`DefaultProject-201 Authentication server running on port ${port}`);
        });
    }
}

// Export for use in other modules
module.exports = DefaultProjectAuth;

// If running directly
if (require.main === module) {
    const authServer = new DefaultProjectAuth();
    authServer.start(process.env.PORT || 3000);
}