# Issue: AEP-201
# Generated: 2025-09-20T06:31:00.963303
# Thread: 8067122d
# Enhanced: LangChain structured generation
# AI Model: deepseek/deepseek-chat-v3.1:free
# Max Length: 25000 characters

package com.aep.auth;

import io.jsonwebtoken.*;
import io.jsonwebtoken.security.Keys;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.dao.DataAccessException;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.data.redis.core.ValueOperations;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.mail.javamail.MimeMessageHelper;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.AuthenticationException;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import javax.crypto.SecretKey;
import javax.mail.MessagingException;
import javax.mail.internet.MimeMessage;
import javax.persistence.EntityManager;
import javax.persistence.PersistenceContext;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.Date;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.TimeUnit;
import java.util.regex.Pattern;

@Service
public class AuthenticationService implements UserDetailsService {

    private static final Pattern EMAIL_PATTERN = Pattern.compile("^[A-Za-z0-9+_.-]+@[A-Za-z0-9.-]+$");
    private static final Pattern PASSWORD_PATTERN = Pattern.compile("^(?=.*[0-9])(?=.*[a-z])(?=.*[A-Z])(?=.*[@#$%^&+=])(?=\\S+$).{8,}$");
    private static final long JWT_EXPIRATION_MINUTES = 60;
    private static final long PASSWORD_RESET_EXPIRATION_MINUTES = 30;
    private static final int MAX_LOGIN_ATTEMPTS = 5;
    private static final long LOGIN_ATTEMPT_LOCK_MINUTES = 15;

    @PersistenceContext
    private EntityManager entityManager;

    @Autowired
    private UserRepository userRepository;

    @Autowired
    private PasswordResetTokenRepository passwordResetTokenRepository;

    @Autowired
    private RedisTemplate<String, Integer> redisTemplate;

    @Autowired
    private JavaMailSender mailSender;

    @Autowired
    private AuthenticationManager authenticationManager;

    @Value("${jwt.secret}")
    private String jwtSecret;

    @Value("${app.base-url}")
    private String baseUrl;

    private final BCryptPasswordEncoder passwordEncoder = new BCryptPasswordEncoder();
    private final SecretKey key = Keys.hmacShaKeyFor(jwtSecret.getBytes());

    private static final Logger logger = LoggerFactory.getLogger(AuthenticationService.class);

    @Transactional
    public User registerUser(RegistrationRequest request) throws AuthenticationException {
        validateRegistrationRequest(request);

        if (userRepository.existsByEmail(request.getEmail())) {
            logger.warn("Registration attempt with existing email: {}", request.getEmail());
            throw new DuplicateEmailException("Email already registered");
        }

        try {
            User user = new User();
            user.setEmail(request.getEmail());
            user.setPasswordHash(passwordEncoder.encode(request.getPassword()));
            user.setFirstName(request.getFirstName());
            user.setLastName(request.getLastName());
            user.setEnabled(false);
            user.setAccountNonLocked(true);
            user.setVerificationToken(UUID.randomUUID().toString());

            User savedUser = userRepository.save(user);
            sendVerificationEmail(savedUser);
            
            logger.info("User registered successfully: {}", savedUser.getEmail());
            return savedUser;
        } catch (DataAccessException e) {
            logger.error("Database error during user registration", e);
            throw new AuthenticationServiceException("Registration failed due to database error", e);
        }
    }

    public AuthResponse login(LoginRequest request) throws AuthenticationException {
        validateLoginRequest(request);

        String email = request.getEmail().toLowerCase().trim();
        checkLoginAttempts(email);

        try {
            Authentication authentication = authenticationManager.authenticate(
                new UsernamePasswordAuthenticationToken(email, request.getPassword())
            );

            User user = (User) authentication.getPrincipal();
            
            if (!user.isEnabled()) {
                logger.warn("Login attempt for unverified account: {}", email);
                throw new AccountNotVerifiedException("Account not verified");
            }

            resetLoginAttempts(email);
            String token = generateToken(user);
            
            logger.info("User logged in successfully: {}", email);
            return new AuthResponse(token, user.getId(), user.getEmail());
        } catch (BadCredentialsException e) {
            handleFailedLoginAttempt(email);
            logger.warn("Failed login attempt for email: {}", email);
            throw new BadCredentialsException("Invalid credentials");
        }
    }

    @Transactional
    public void initiatePasswordReset(String email) throws AuthenticationException {
        if (!EMAIL_PATTERN.matcher(email).matches()) {
            throw new InvalidEmailException("Invalid email format");
        }

        Optional<User> userOpt = userRepository.findByEmail(email);
        if (userOpt.isEmpty()) {
            logger.warn("Password reset attempt for non-existent email: {}", email);
            return; // Security: don't reveal if email exists
        }

        User user = userOpt.get();
        String token = UUID.randomUUID().toString();
        
        PasswordResetToken resetToken = new PasswordResetToken();
        resetToken.setToken(token);
        resetToken.setUser(user);
        resetToken.setExpiryDate(Date.from(Instant.now().plus(PASSWORD_RESET_EXPIRATION_MINUTES, ChronoUnit.MINUTES)));
        
        passwordResetTokenRepository.save(resetToken);
        sendPasswordResetEmail(user, token);
        
        logger.info("Password reset initiated for user: {}", email);
    }

    @Transactional
    public void completePasswordReset(PasswordResetRequest request) throws AuthenticationException {
        validatePasswordResetRequest(request);

        Optional<PasswordResetToken> tokenOpt = passwordResetTokenRepository.findByToken(request.getToken());
        if (tokenOpt.isEmpty() || tokenOpt.get().isExpired()) {
            logger.warn("Invalid or expired password reset token attempted");
            throw new InvalidTokenException("Invalid or expired reset token");
        }

        PasswordResetToken resetToken = tokenOpt.get();
        User user = resetToken.getUser();
        
        user.setPasswordHash(passwordEncoder.encode(request.getNewPassword()));
        userRepository.save(user);
        passwordResetTokenRepository.delete(resetToken);
        
        logger.info("Password reset completed successfully for user: {}", user.getEmail());
    }

    @Transactional
    public void verifyEmail(String token) throws AuthenticationException {
        Optional<User> userOpt = userRepository.findByVerificationToken(token);
        if (userOpt.isEmpty()) {
            logger.warn("Invalid email verification token attempted");
            throw new InvalidTokenException("Invalid verification token");
        }

        User user = userOpt.get();
        user.setEnabled(true);
        user.setVerificationToken(null);
        userRepository.save(user);
        
        logger.info("Email verified successfully for user: {}", user.getEmail());
    }

    public boolean validateToken(String token) {
        try {
            Jwts.parserBuilder()
                .setSigningKey(key)
                .build()
                .parseClaimsJws(token);
            return true;
        } catch (JwtException | IllegalArgumentException e) {
            logger.warn("Invalid JWT token attempted: {}", e.getMessage());
            return false;
        }
    }

    public AuthResponse refreshToken(String oldToken) throws AuthenticationException {
        if (!validateToken(oldToken)) {
            throw new InvalidTokenException("Invalid token");
        }

        Claims claims = Jwts.parserBuilder()
            .setSigningKey(key)
            .build()
            .parseClaimsJws(oldToken)
            .getBody();

        String email = claims.getSubject();
        Optional<User> userOpt = userRepository.findByEmail(email);
        
        if (userOpt.isEmpty()) {
            throw new UserNotFoundException("User not found");
        }

        User user = userOpt.get();
        String newToken = generateToken(user);
        
        logger.info("Token refreshed for user: {}", email);
        return new AuthResponse(newToken, user.getId(), user.getEmail());
    }

    @Override
    public UserDetails loadUserByUsername(String email) throws UsernameNotFoundException {
        Optional<User> userOpt = userRepository.findByEmail(email);
        if (userOpt.isEmpty()) {
            logger.warn("User not found: {}", email);
            throw new UsernameNotFoundException("User not found");
        }
        return userOpt.get();
    }

    private String generateToken(User user) {
        Instant now = Instant.now();
        Instant expiry = now.plus(JWT_EXPIRATION_MINUTES, ChronoUnit.MINUTES);

        return Jwts.builder()
            .setSubject(user.getEmail())
            .claim("userId", user.getId())
            .setIssuedAt(Date.from(now))
            .setExpiration(Date.from(expiry))
            .signWith(key)
            .compact();
    }

    private void sendVerificationEmail(User user) throws AuthenticationException {
        try {
            MimeMessage message = mailSender.createMimeMessage();
            MimeMessageHelper helper = new MimeMessageHelper(message, true);
            
            helper.setTo(user.getEmail());
            helper.setSubject("Verify your AEP account");
            helper.setText(buildVerificationEmailContent(user), true);
            
            mailSender.send(message);
        } catch (MessagingException e) {
            logger.error("Failed to send verification email to: {}", user.getEmail(), e);
            throw new EmailServiceException("Failed to send verification email");
        }
    }

    private void sendPasswordResetEmail(User user, String token) throws AuthenticationException {
        try {
            MimeMessage message = mailSender.createMimeMessage();
            MimeMessageHelper helper = new MimeMessageHelper(message, true);
            
            helper.setTo(user.getEmail());
            helper.setSubject("Reset your AEP password");
            helper.setText(buildPasswordResetEmailContent(user, token), true);
            
            mailSender.send(message);
        } catch (MessagingException e) {
            logger.error("Failed to send password reset email to: {}", user.getEmail(), e);
            throw new EmailServiceException("Failed to send password reset email");
        }
    }

    private String buildVerificationEmailContent(User user) {
        String verificationUrl = baseUrl + "/auth/verify?token=" + user.getVerificationToken();
        return "<html><body>" +
               "<h2>Welcome to AEP!</h2>" +
               "<p>Please click the link below to verify your email address:</p>" +
               "<a href=\"" + verificationUrl + "\">Verify Email</a>" +
               "</body></html>";
    }

    private String buildPasswordResetEmailContent(User user, String token) {
        String resetUrl = baseUrl + "/auth/reset-password?token=" + token;
        return "<html><body>" +
               "<h2>Password Reset Request</h2>" +
               "<p>Click the link below to reset your password:</p>" +
               "<a href=\"" + resetUrl + "\">Reset Password</a>" +
               "<p>This link will expire in " + PASSWORD_RESET_EXPIRATION_MINUTES + " minutes.</p>" +
               "</body></html>";
    }

    private void checkLoginAttempts(String email) throws AuthenticationException {
        ValueOperations<String, Integer> ops = redisTemplate.opsForValue();
        String key = "login_attempts:" + email;
        Integer attempts = ops.get(key);

        if (attempts != null && attempts >= MAX_LOGIN_ATTEMPTS) {
            logger.warn("Account locked due to too many failed attempts: {}", email);
            throw new AccountLockedException("Account temporarily locked");
        }
    }

    private void handleFailedLoginAttempt(String email) {
        ValueOperations<String, Integer> ops = redisTemplate.opsForValue();
        String key = "login_attempts:" + email;
        
        Integer attempts = ops.get(key);
        if (attempts == null) {
            attempts = 0;
        }
        
        attempts++;
        ops.set(key, attempts, LOGIN_ATTEMPT_LOCK_MINUTES, TimeUnit.MINUTES);
    }

    private void resetLoginAttempts(String email) {
        redisTemplate.delete("login_attempts:" + email);
    }

    private void validateRegistrationRequest(RegistrationRequest request) {
        if (request.getEmail() == null || !EMAIL_PATTERN.matcher(request.getEmail()).matches()) {
            throw new InvalidEmailException("Invalid email format");
        }
        
        if (request.getPassword() == null || !PASSWORD_PATTERN.matcher(request.getPassword()).matches()) {
            throw new InvalidPasswordException("Password must be at least 8 characters with uppercase, lowercase, number and special character");
        }
        
        if (request.getFirstName() == null || request.getFirstName().trim().isEmpty()) {
            throw new InvalidInputException("First name is required");
        }
        
        if (request.getLastName() == null || request.getLastName().trim().isEmpty()) {
            throw new InvalidInputException("Last name is required");
        }
    }

    private void validateLoginRequest(LoginRequest request) {
        if (request.getEmail() == null || request.getEmail().trim().isEmpty()) {
            throw new InvalidEmailException("Email is required");
        }
        
        if (request.getPassword() == null || request.getPassword().isEmpty()) {
            throw new InvalidPasswordException("Password is required");
        }
    }

    private void validatePasswordResetRequest(PasswordResetRequest request) {
        if (request.getToken() == null || request.getToken().isEmpty()) {
            throw new InvalidTokenException("Reset token is required");
        }
        
        if (request.getNewPassword() == null || !PASSWORD_PATTERN.matcher(request.getNewPassword()).matches()) {
            throw new InvalidPasswordException("Password must be at least 8 characters with uppercase, lowercase, number and special character");
        }
    }
}

@Entity
@Table(name = "users")
class User implements UserDetails {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    @Column(unique = true, nullable = false)
    private String email;
    
    @Column(nullable = false)
    private String passwordHash;
    
    @Column(nullable = false)
    private String firstName;
    
    @Column(nullable = false)
    private String lastName;
    
    private boolean enabled;
    private boolean accountNonLocked;
    private String verificationToken;
    
    // Getters and setters
    // UserDetails interface methods implementation
}

@Entity
@Table(name = "password_reset_tokens")
class PasswordResetToken {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    @Column(unique = true, nullable = false)
    private String token;
    
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id", nullable = false)
    private User user;
    
    @Column(nullable = false)
    private Date expiryDate;
    
    public boolean isExpired() {
        return expiryDate.before(new Date());
    }
    
    // Getters and setters
}

class RegistrationRequest {
    private String email;
    private String password;
    private String firstName;
    private String lastName;
    
    // Getters and setters
}

class LoginRequest {
    private String email;
    private String password;
    
    // Getters and setters
}

class PasswordResetRequest {
    private String token;
    private String newPassword;
    
    // Getters and setters
}

class AuthResponse {
    private String token;
    private Long userId;
    private String email;
    
    public AuthResponse(String token, Long userId, String email) {
        this.token = token;
        this.userId = userId;
        this.email = email;
    }
    
    // Getters
}

// Exception classes
class AuthenticationServiceException extends AuthenticationException {
    public AuthenticationServiceException(String msg, Throwable cause) {
        super(msg, cause);
    }
    public AuthenticationServiceException(String msg) {
        super(msg);
    }
}

class DuplicateEmailException extends AuthenticationException {
    public DuplicateEmailException(String msg) {
        super(msg);
    }
}

class InvalidEmailException extends AuthenticationException {
    public InvalidEmailException(String msg) {
        super(msg);
    }
}

class InvalidPasswordException extends AuthenticationException {
    public InvalidPasswordException(String msg) {
        super(msg);
    }
}

class InvalidTokenException extends AuthenticationException {
    public InvalidTokenException(String msg) {
        super(msg);
    }
}

class AccountNotVerifiedException extends AuthenticationException {
    public AccountNotVerifiedException(String msg) {
        super(msg);
    }
}

class AccountLockedException extends AuthenticationException {
    public AccountLockedException(String msg) {
        super(msg);
    }
}

class UserNotFoundException extends AuthenticationException {
    public UserNotFoundException(String msg) {
        super(msg);
    }
}

class EmailServiceException extends AuthenticationException {
    public EmailServiceException(String msg) {
        super(msg);
    }
}

class InvalidInputException extends AuthenticationException {
    public InvalidInputException(String msg) {
        super(msg);
    }
}

interface UserRepository extends JpaRepository<User, Long> {
    Optional<User> findByEmail(String email);
    boolean existsByEmail(String email);
    Optional<User> findByVerificationToken(String token);
}

interface PasswordResetTokenRepository extends JpaRepository<PasswordResetToken, Long> {
    Optional<PasswordResetToken> findByToken(String token);
}