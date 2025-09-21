# Generated for DefaultProject-201 | 2025-09-21 06:09:33 | Developer Agent v2.0
# AutoFlow-Dashboard Enhanced Code Generation
# Thread: ce6dd025 | LangChain: Template-Enhanced Generation
# Workflow Stage: Code Generation (NO PR creation)

const crypto = require('crypto');
const jwt = require('jsonwebtoken');
const bcrypt = require('bcryptjs');
const { validationResult } = require('express-validator');
const { v4: uuidv4 } = require('uuid');

// DefaultProject-201: User Authentication System
class UserAuthenticationSystem {
    constructor() {
        this.users = new Map();
        this.refreshTokens = new Map();
        this.passwordResetTokens = new Map();
        this.jwtSecret = process.env.JWT_SECRET || crypto.randomBytes(64).toString('hex');
        this.refreshSecret = process.env.REFRESH_SECRET || crypto.randomBytes(64).toString('hex');
        this.tokenExpiry = '15m';
        this.refreshExpiry = '7d';
    }

    // Input validation middleware
    validateInput(req, res, next) {
        const errors = validationResult(req);
        if (!errors.isEmpty()) {
            return res.status(400).json({
                success: false,
                errors: errors.array()
            });
        }
        next();
    }

    // Generate JWT token
    generateToken(payload) {
        return jwt.sign(payload, this.jwtSecret, { expiresIn: this.tokenExpiry });
    }

    // Generate refresh token
    generateRefreshToken(payload) {
        return jwt.sign(payload, this.refreshSecret, { expiresIn: this.refreshExpiry });
    }

    // Verify JWT token
    verifyToken(token) {
        try {
            return jwt.verify(token, this.jwtSecret);
        } catch (error) {
            throw new Error('Invalid or expired token');
        }
    }

    // Verify refresh token
    verifyRefreshToken(token) {
        try {
            return jwt.verify(token, this.refreshSecret);
        } catch (error) {
            throw new Error('Invalid or expired refresh token');
        }
    }

    // User registration
    async register(req, res) {
        try {
            const { email, password, firstName, lastName } = req.body;
            
            // Check if user already exists
            if (this.users.has(email)) {
                return res.status(409).json({
                    success: false,
                    message: 'User already exists'
                });
            }

            // Hash password
            const saltRounds = 12;
            const hashedPassword = await bcrypt.hash(password, saltRounds);

            // Create user object
            const user = {
                id: uuidv4(),
                email,
                password: hashedPassword,
                firstName,
                lastName,
                createdAt: new Date(),
                updatedAt: new Date(),
                isVerified: false,
                lastLogin: null
            };

            // Store user
            this.users.set(email, user);

            // Generate tokens
            const tokenPayload = { userId: user.id, email: user.email };
            const token = this.generateToken(tokenPayload);
            const refreshToken = this.generateRefreshToken(tokenPayload);
            
            // Store refresh token
            this.refreshTokens.set(refreshToken, {
                userId: user.id,
                expiresAt: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000)
            });

            console.log(`User registered successfully: ${email}`);

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
                    token,
                    refreshToken
                }
            });

        } catch (error) {
            console.error('Registration error:', error);
            res.status(500).json({
                success: false,
                message: 'Internal server error during registration'
            });
        }
    }

    // User login
    async login(req, res) {
        try {
            const { email, password } = req.body;

            // Check if user exists
            const user = this.users.get(email);
            if (!user) {
                return res.status(401).json({
                    success: false,
                    message: 'Invalid credentials'
                });
            }

            // Verify password
            const isValidPassword = await bcrypt.compare(password, user.password);
            if (!isValidPassword) {
                return res.status(401).json({
                    success: false,
                    message: 'Invalid credentials'
                });
            }

            // Update last login
            user.lastLogin = new Date();
            user.updatedAt = new Date();
            this.users.set(email, user);

            // Generate tokens
            const tokenPayload = { userId: user.id, email: user.email };
            const token = this.generateToken(tokenPayload);
            const refreshToken = this.generateRefreshToken(tokenPayload);

            // Store refresh token
            this.refreshTokens.set(refreshToken, {
                userId: user.id,
                expiresAt: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000)
            });

            console.log(`User logged in successfully: ${email}`);

            res.status(200).json({
                success: true,
                message: 'Login successful',
                data: {
                    user: {
                        id: user.id,
                        email: user.email,
                        firstName: user.firstName,
                        lastName: user.lastName
                    },
                    token,
                    refreshToken
                }
            });

        } catch (error) {
            console.error('Login error:', error);
            res.status(500).json({
                success: false,
                message: 'Internal server error during login'
            });
        }
    }

    // Token refresh
    async refreshToken(req, res) {
        try {
            const { refreshToken } = req.body;

            if (!refreshToken) {
                return res.status(400).json({
                    success: false,
                    message: 'Refresh token is required'
                });
            }

            // Verify refresh token
            const decoded = this.verifyRefreshToken(refreshToken);
            
            // Check if refresh token exists in storage
            const storedToken = this.refreshTokens.get(refreshToken);
            if (!storedToken || storedToken.userId !== decoded.userId) {
                return res.status(401).json({
                    success: false,
                    message: 'Invalid refresh token'
                });
            }

            // Get user
            let user = null;
            for (const [email, userData] of this.users.entries()) {
                if (userData.id === decoded.userId) {
                    user = userData;
                    break;
                }
            }

            if (!user) {
                return res.status(401).json({
                    success: false,
                    message: 'User not found'
                });
            }

            // Generate new tokens
            const tokenPayload = { userId: user.id, email: user.email };
            const newToken = this.generateToken(tokenPayload);
            const newRefreshToken = this.generateRefreshToken(tokenPayload);

            // Remove old refresh token and store new one
            this.refreshTokens.delete(refreshToken);
            this.refreshTokens.set(newRefreshToken, {
                userId: user.id,
                expiresAt: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000)
            });

            console.log(`Token refreshed for user: ${user.email}`);

            res.status(200).json({
                success: true,
                message: 'Token refreshed successfully',
                data: {
                    token: newToken,
                    refreshToken: newRefreshToken
                }
            });

        } catch (error) {
            console.error('Token refresh error:', error);
            res.status(401).json({
                success: false,
                message: 'Invalid refresh token'
            });
        }
    }

    // Password reset request
    async requestPasswordReset(req, res) {
        try {
            const { email } = req.body;

            // Check if user exists
            const user = this.users.get(email);
            if (!user) {
                // Return success even if user doesn't exist for security
                return res.status(200).json({
                    success: true,
                    message: 'If the email exists, a reset link has been sent'
                });
            }

            // Generate reset token
            const resetToken = crypto.randomBytes(32).toString('hex');
            const resetTokenExpiry = new Date(Date.now() + 60 * 60 * 1000); // 1 hour

            // Store reset token
            this.passwordResetTokens.set(resetToken, {
                userId: user.id,
                email: user.email,
                expiresAt: resetTokenExpiry
            });

            // In production, you would send an email here
            console.log(`Password reset token generated for ${email}: ${resetToken}`);

            res.status(200).json({
                success: true,
                message: 'If the email exists, a reset link has been sent',
                data: {
                    resetToken: resetToken // In production, this would be sent via email
                }
            });

        } catch (error) {
            console.error('Password reset request error:', error);
            res.status(500).json({
                success: false,
                message: 'Internal server error during password reset request'
            });
        }
    }

    // Password reset confirmation
    async resetPassword(req, res) {
        try {
            const { resetToken, newPassword } = req.body;

            if (!resetToken || !newPassword) {
                return res.status(400).json({
                    success: false,
                    message: 'Reset token and new password are required'
                });
            }

            // Check if reset token exists and is valid
            const resetData = this.passwordResetTokens.get(resetToken);
            if (!resetData || resetData.expiresAt < new Date()) {
                return res.status(400).json({
                    success: false,
                    message: 'Invalid or expired reset token'
                });
            }

            // Find user
            let user = null;
            for (const [email, userData] of this.users.entries()) {
                if (userData.id === resetData.userId) {
                    user = userData;
                    break;
                }
            }

            if (!user) {
                return res.status(400).json({
                    success: false,
                    message: 'User not found'
                });
            }

            // Hash new password
            const saltRounds = 12;
            const hashedPassword = await bcrypt.hash(newPassword, saltRounds);

            // Update user password
            user.password = hashedPassword;
            user.updatedAt = new Date();
            this.users.set(user.email, user);

            // Remove used reset token
            this.passwordResetTokens.delete(resetToken);

            // Invalidate all refresh tokens for this user
            for (const [token, tokenData] of this.refreshTokens.entries()) {
                if (tokenData.userId === user.id) {
                    this.refreshTokens.delete(token);
                }
            }

            console.log(`Password reset successfully for user: ${user.email}`);

            res.status(200).json({
                success: true,
                message: 'Password reset successfully'
            });

        } catch (error) {
            console.error('Password reset error:', error);
            res.status(500).json({
                success: false,
                message: 'Internal server error during password reset'
            });
        }
    }

    // Logout
    async logout(req, res) {
        try {
            const { refreshToken } = req.body;

            if (refreshToken) {
                this.refreshTokens.delete(refreshToken);
            }

            console.log('User logged out successfully');

            res.status(200).json({
                success: true,
                message: 'Logged out successfully'
            });

        } catch (error) {
            console.error('Logout error:', error);
            res.status(500).json({
                success: false,
                message: 'Internal server error during logout'
            });
        }
    }

    // Get current user profile
    async getProfile(req, res) {
        try {
            const authHeader = req.headers.authorization;
            
            if (!authHeader || !authHeader.startsWith('Bearer ')) {
                return res.status(401).json({
                    success: false,
                    message: 'Authorization token required'
                });
            }

            const token = authHeader.substring(7);
            const decoded = this.verifyToken(token);

            // Find user
            let user = null;
            for (const [email, userData] of this.users.entries()) {
                if (userData.id === decoded.userId) {
                    user = userData;
                    break;
                }
            }

            if (!user) {
                return res.status(404).json({
                    success: false,
                    message: 'User not found'
                });
            }

            res.status(200).json({
                success: true,
                data: {
                    user: {
                        id: user.id,
                        email: user.email,
                        firstName: user.firstName,
                        lastName: user.lastName,
                        createdAt: user.createdAt,
                        lastLogin: user.lastLogin
                    }
                }
            });

        } catch (error) {
            console.error('Get profile error:', error);
            res.status(401).json({
                success: false,
                message: 'Invalid or expired token'
            });
        }
    }

    // Middleware for protected routes
    authenticateToken(req, res, next) {
        try {
            const authHeader = req.headers.authorization;
            
            if (!authHeader || !authHeader.startsWith('Bearer ')) {
                return res.status(401).json({
                    success: false,
                    message: 'Authorization token required'
                });
            }

            const token = authHeader.substring(7);
            const decoded = this.verifyToken(token);
            
            req.user = decoded;
            next();

        } catch (error) {
            console.error('Authentication error:', error);
            res.status(401).json({
                success: false,
                message: 'Invalid or expired token'
            });
        }
    }

    // Cleanup expired tokens (should be called periodically)
    cleanupExpiredTokens() {
        const now = new Date();
        
        // Clean expired refresh tokens
        for (const [token, tokenData] of this.refreshTokens.entries()) {
            if (tokenData.expiresAt < now) {
                this.refreshTokens.delete(token);
            }
        }

        // Clean expired password reset tokens
        for (const [token, tokenData] of this.passwordResetTokens.entries()) {
            if (tokenData.expiresAt < now) {
                this.passwordResetTokens.delete(token);
            }
        }

        console.log('Expired tokens cleaned up');
    }
}

// Export middleware functions and class
module.exports = {
    UserAuthenticationSystem,
    validationRules: {
        register: [
            // Add your validation rules using express-validator
        ],
        login: [
            // Add your validation rules using express-validator
        ],
        passwordReset: [
            // Add your validation rules using express-validator
        ]
    }
};