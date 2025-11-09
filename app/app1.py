from flask import Flask, request, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_cors import CORS
from flask_mail import Mail, Message
from datetime import datetime, timedelta
import os
import re
import secrets
from functools import wraps

# Initialize Flask app
app = Flask(__name__, static_folder='.', static_url_path='')
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production-use-env-vars'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///garage_app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = 'jwt-secret-key-change-in-production-use-env-vars'
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)

# Email configuration for password reset
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', 'your-email@gmail.com')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', 'your-app-password')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_USERNAME', 'your-email@gmail.com')

# Initialize extensions
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
jwt = JWTManager(app)
mail = Mail(app)


# ==================== VALIDATION UTILITIES ====================

class ValidationError(Exception):
    """Custom validation error exception"""
    pass

def validate_email(email):
    """Validate email format"""
    if not email:
        raise ValidationError("Email is required")
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        raise ValidationError("Invalid email format")
    return email.lower().strip()

def validate_password(password):
    """Validate password strength"""
    if not password:
        raise ValidationError("Password is required")
    if len(password) < 8:
        raise ValidationError("Password must be at least 8 characters long")
    if not re.search(r'[A-Z]', password):
        raise ValidationError("Password must contain at least one uppercase letter")
    if not re.search(r'[a-z]', password):
        raise ValidationError("Password must contain at least one lowercase letter")
    if not re.search(r'\d', password):
        raise ValidationError("Password must contain at least one number")
    return password

def validate_username(username):
    """Validate username format"""
    if not username:
        raise ValidationError("Username is required")
    if len(username) < 3:
        raise ValidationError("Username must be at least 3 characters long")
    if len(username) > 50:
        raise ValidationError("Username must not exceed 50 characters")
    if not re.match(r'^[a-zA-Z0-9_.-]+$', username):
        raise ValidationError("Username can only contain letters, numbers, dots, hyphens, and underscores")
    return username.lower().strip()

def validate_phone(phone):
    """Validate phone number format"""
    if not phone:
        raise ValidationError("Phone number is required")
    # Remove spaces and special characters
    phone = re.sub(r'[^\d+]', '', phone)
    if not re.match(r'^\+?[\d]{10,15}$', phone):
        raise ValidationError("Invalid phone number format")
    return phone

def validate_required_fields(data, required_fields):
    """Check if all required fields are present"""
    missing_fields = [field for field in required_fields if not data.get(field)]
    if missing_fields:
        raise ValidationError(f"Missing required fields: {', '.join(missing_fields)}")

# ==================== DATABASE MODELS ====================

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(200), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), default='staff')
    is_active = db.Column(db.Boolean, default=True)
    reset_token = db.Column(db.String(100), unique=True)
    reset_token_expiry = db.Column(db.DateTime)
    last_login = db.Column(db.DateTime)
    failed_login_attempts = db.Column(db.Integer, default=0)
    account_locked_until = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        """Verify password"""
        return bcrypt.check_password_hash(self.password_hash, password)
    
    def generate_reset_token(self):
        """Generate password reset token"""
        self.reset_token = secrets.token_urlsafe(32)
        self.reset_token_expiry = datetime.utcnow() + timedelta(hours=1)
        return self.reset_token
    
    def verify_reset_token(self, token):
        """Verify reset token is valid and not expired"""
        return (self.reset_token == token and 
                self.reset_token_expiry and 
                self.reset_token_expiry > datetime.utcnow())
    
    def is_account_locked(self):
        """Check if account is locked due to failed login attempts"""
        if self.account_locked_until and self.account_locked_until > datetime.utcnow():
            return True
        return False
    
    def to_dict(self):
        """Convert user object to dictionary"""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'name': self.name,
            'role': self.role,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Client(db.Model):
    __tablename__ = 'clients'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120), unique=True)
    vehicle_details = db.Column(db.String(200), nullable=False)
    address = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    bookings = db.relationship('Booking', backref='client', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'phone': self.phone,
            'email': self.email,
            'vehicle_details': self.vehicle_details,
            'address': self.address,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Inventory(db.Model):
    __tablename__ = 'inventory'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    stock_quantity = db.Column(db.Integer, nullable=False, default=0)
    price = db.Column(db.Float, nullable=False)
    min_stock = db.Column(db.Integer, nullable=False, default=5)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'category': self.category,
            'stock_quantity': self.stock_quantity,
            'price': self.price,
            'min_stock': self.min_stock,
            'description': self.description,
            'is_low_stock': self.stock_quantity <= self.min_stock,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Booking(db.Model):
    __tablename__ = 'bookings'
    
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    service_type = db.Column(db.String(100), nullable=False)
    booking_date = db.Column(db.Date, nullable=False)
    booking_time = db.Column(db.String(10), nullable=False)
    status = db.Column(db.String(20), default='pending')
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    payments = db.relationship('Payment', backref='booking', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'client_id': self.client_id,
            'client_name': self.client.name if self.client else None,
            'service_type': self.service_type,
            'booking_date': self.booking_date.isoformat() if self.booking_date else None,
            'booking_time': self.booking_time,
            'status': self.status,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Payment(db.Model):
    __tablename__ = 'payments'
    
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), default='pending')
    transaction_id = db.Column(db.String(100))
    phone_number = db.Column(db.String(20))
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'booking_id': self.booking_id,
            'amount': self.amount,
            'payment_method': self.payment_method,
            'status': self.status,
            'transaction_id': self.transaction_id,
            'payment_date': self.payment_date.isoformat() if self.payment_date else None
        }

# ==================== ERROR HANDLERS ====================

@app.errorhandler(ValidationError)
def handle_validation_error(error):
    """Handle validation errors"""
    return jsonify({
        'success': False,
        'message': str(error),
        'error_type': 'validation_error'
    }), 400

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({
        'success': False,
        'message': 'Resource not found',
        'error_type': 'not_found'
    }), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    db.session.rollback()
    return jsonify({
        'success': False,
        'message': 'Internal server error. Please try again later.',
        'error_type': 'server_error'
    }), 500

@app.errorhandler(401)
def unauthorized(error):
    """Handle 401 errors"""
    return jsonify({
        'success': False,
        'message': 'Unauthorized access',
        'error_type': 'unauthorized'
    }), 401

@app.errorhandler(403)
def forbidden(error):
    """Handle 403 errors"""
    return jsonify({
        'success': False,
        'message': 'Access forbidden',
        'error_type': 'forbidden'
    }), 403

# ==================== FRONTEND ROUTE ====================

@app.route('/')
@app.route('/<path:path>')
def serve_frontend(path=None):
    """Serve the frontend single-page application"""
    return send_from_directory(app.static_folder, 'app.html')

# ==================== AUTHENTICATION ROUTES ====================

@app.route('/api/auth/register', methods=['POST'])
def register():
    """Register a new user"""
    try:
        data = request.get_json()
        
        # Validate required fields
        validate_required_fields(data, ['username', 'email', 'password', 'name'])
        
        # Validate input format
        username = validate_username(data['username'])
        email = validate_email(data['email'])
        password = validate_password(data['password'])
        name = data['name'].strip()
        
        if not name or len(name) < 2:
            raise ValidationError("Name must be at least 2 characters long")
        
        # Check if username already exists
        if User.query.filter_by(username=username).first():
            raise ValidationError("Username already exists")
        
        # Check if email already exists
        if User.query.filter_by(email=email).first():
            raise ValidationError("Email already exists")
        
        # Create new user
        new_user = User(
            username=username,
            email=email,
            name=name,
            role=data.get('role', 'staff')
        )
        new_user.set_password(password)
        
        db.session.add(new_user)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'User registered successfully',
            'user': new_user.to_dict()
        }), 201
        
    except ValidationError as e:
        raise
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Registration failed: {str(e)}'
        }), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    """User login"""
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data or not data.get('username') or not data.get('password'):
            raise ValidationError("Username and password are required")
        
        username = data['username'].strip().lower()
        password = data['password']
        
        # Find user
        user = User.query.filter_by(username=username).first()
        
        if not user:
            return jsonify({
                'success': False,
                'message': 'Invalid username or password'
            }), 401
        
        # Check if account is locked
        if user.is_account_locked():
            minutes_remaining = int((user.account_locked_until - datetime.utcnow()).total_seconds() / 60)
            return jsonify({
                'success': False,
                'message': f'Account is locked due to too many failed login attempts. Please try again in {minutes_remaining} minutes.'
            }), 403
        
        # Check if account is active
        if not user.is_active:
            return jsonify({
                'success': False,
                'message': 'Account is deactivated. Please contact administrator.'
            }), 403
        
        # Verify password
        if user.check_password(password):
            # Reset failed login attempts
            user.failed_login_attempts = 0
            user.account_locked_until = None
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            # Create access token
            access_token = create_access_token(identity=user.id)
            
            return jsonify({
                'success': True,
                'message': 'Login successful',
                'access_token': access_token,
                'user': user.to_dict()
            }), 200
        else:
            # Increment failed login attempts
            user.failed_login_attempts += 1
            
            # Lock account after 5 failed attempts
            if user.failed_login_attempts >= 5:
                user.account_locked_until = datetime.utcnow() + timedelta(minutes=30)
                db.session.commit()
                return jsonify({
                    'success': False,
                    'message': 'Account locked due to too many failed login attempts. Please try again in 30 minutes.'
                }), 403
            
            db.session.commit()
            
            remaining_attempts = 5 - user.failed_login_attempts
            return jsonify({
                'success': False,
                'message': f'Invalid username or password. {remaining_attempts} attempts remaining.'
            }), 401
            
    except ValidationError as e:
        raise
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Login failed: {str(e)}'
        }), 500

@app.route('/api/auth/forgot-password', methods=['POST'])
def forgot_password():
    """Request password reset"""
    try:
        data = request.get_json()
        
        if not data or not data.get('email'):
            raise ValidationError("Email is required")
        
        email = validate_email(data['email'])
        
        # Find user by email
        user = User.query.filter_by(email=email).first()
        
        # Always return success message for security (don't reveal if email exists)
        if not user:
            return jsonify({
                'success': True,
                'message': 'If an account with that email exists, a password reset link has been sent.'
            }), 200
        
        # Generate reset token
        reset_token = user.generate_reset_token()
        db.session.commit()
        
        # Create reset link
        reset_link = f"http://localhost:5000/reset-password?token={reset_token}"
        
        # Send email (in production, use actual email service)
        try:
            msg = Message(
                'Password Reset Request',
                recipients=[user.email]
            )
            msg.body = f"""Hello {user.name},

You have requested to reset your password. Click the link below to reset your password:

{reset_link}

This link will expire in 1 hour.

If you did not request this, please ignore this email.

Best regards,
AutoCare Garage Team
"""
            msg.html = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #2c3e50;">Password Reset Request</h2>
                    <p>Hello {user.name},</p>
                    <p>You have requested to reset your password. Click the button below to reset your password:</p>
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{reset_link}" style="background-color: #3498db; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block;">Reset Password</a>
                    </div>
                    <p>Or copy and paste this link into your browser:</p>
                    <p style="word-break: break-all; background-color: #f4f4f4; padding: 10px; border-radius: 3px;">{reset_link}</p>
                    <p style="color: #e74c3c; font-weight: bold;">This link will expire in 1 hour.</p>
                    <p>If you did not request this, please ignore this email.</p>
                    <p>Best regards,<br>AutoCare Garage Team</p>
                </div>
            </body>
            </html>
            """
            # mail.send(msg)  # Uncomment when email is configured
            print(f"Password reset link: {reset_link}")  # For development
        except Exception as e:
            print(f"Error sending email: {e}")
        
        return jsonify({
            'success': True,
            'message': 'If an account with that email exists, a password reset link has been sent.',
            'reset_link': reset_link  # Remove this in production!
        }), 200
        
    except ValidationError as e:
        raise
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Password reset request failed: {str(e)}'
        }), 500

@app.route('/api/auth/reset-password', methods=['POST'])
def reset_password():
    """Reset password with token"""
    try:
        data = request.get_json()
        
        # Validate required fields
        validate_required_fields(data, ['token', 'password'])
        
        token = data['token']
        new_password = validate_password(data['password'])
        
        # Find user by reset token
        user = User.query.filter_by(reset_token=token).first()
        
        if not user:
            return jsonify({
                'success': False,
                'message': 'Invalid or expired reset token'
            }), 400
        
        # Verify token is not expired
        if not user.verify_reset_token(token):
            return jsonify({
                'success': False,
                'message': 'Reset token has expired. Please request a new one.'
            }), 400
        
        # Reset password
        user.set_password(new_password)
        user.reset_token = None
        user.reset_token_expiry = None
        user.failed_login_attempts = 0
        user.account_locked_until = None
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Password has been reset successfully. You can now login with your new password.'
        }), 200
        
    except ValidationError as e:
        raise
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Password reset failed: {str(e)}'
        }), 500

@app.route('/api/auth/change-password', methods=['POST'])
@jwt_required()
def change_password():
    """Change password for logged-in user"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        # Validate required fields
        validate_required_fields(data, ['current_password', 'new_password'])
        
        user = User.query.get_or_404(user_id)
        
        # Verify current password
        if not user.check_password(data['current_password']):
            return jsonify({
                'success': False,
                'message': 'Current password is incorrect'
            }), 401
        
        # Validate new password
        new_password = validate_password(data['new_password'])
        
        # Check if new password is different from current
        if user.check_password(new_password):
            raise ValidationError("New password must be different from current password")
        
        # Update password
        user.set_password(new_password)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Password changed successfully'
        }), 200
        
    except ValidationError as e:
        raise
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Password change failed: {str(e)}'
        }), 500

@app.route('/api/auth/verify', methods=['GET'])
@jwt_required()
def verify_token():
    """Verify JWT token"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user or not user.is_active:
            return jsonify({
                'success': False,
                'message': 'Invalid or inactive user'
            }), 401
        
        return jsonify({
            'success': True,
            'user': user.to_dict()
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': 'Token verification failed'
        }), 401

@app.route('/api/auth/logout', methods=['POST'])
@jwt_required()
def logout():
    """Logout user (client-side token removal)"""
    return jsonify({
        'success': True,
        'message': 'Logged out successfully'
    }), 200

# ==================== DASHBOARD ROUTES ====================

@app.route('/api/dashboard', methods=['GET'])
@jwt_required()
def get_dashboard():
    """Get dashboard statistics"""
    try:
        total_clients = Client.query.count()
        pending_bookings = Booking.query.filter_by(status='pending').count()
        low_stock_items = Inventory.query.filter(
            Inventory.stock_quantity <= Inventory.min_stock
        ).count()
        pending_payments = Payment.query.filter_by(status='pending').count()
        
        # Recent bookings
        recent_bookings = Booking.query.join(Client).order_by(
            Booking.created_at.desc()
        ).limit(5).all()
        
        # Low stock alerts
        low_stock_alerts = Inventory.query.filter(
            Inventory.stock_quantity <= Inventory.min_stock
        ).order_by(Inventory.stock_quantity.asc()).limit(5).all()
        
        return jsonify({
            'success': True,
            'data': {
                'total_clients': total_clients,
                'pending_bookings': pending_bookings,
                'low_stock_items': low_stock_items,
                'pending_payments': pending_payments,
                'recent_bookings': [booking.to_dict() for booking in recent_bookings],
                'low_stock_alerts': [item.to_dict() for item in low_stock_alerts]
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Failed to fetch dashboard data: {str(e)}'
        }), 500

# ==================== CLIENT ROUTES ====================

@app.route('/api/clients', methods=['GET'])
@jwt_required()
def get_clients():
    """Get all clients"""
    try:
        clients = Client.query.order_by(Client.created_at.desc()).all()
        return jsonify({
            'success': True,
            'data': [client.to_dict() for client in clients]
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Failed to fetch clients: {str(e)}'
        }), 500

@app.route('/api/clients', methods=['POST'])
@jwt_required()
def create_client():
    """Create new client"""
    try:
        data = request.get_json()
        
        # Validate required fields
        validate_required_fields(data, ['name', 'phone', 'vehicle_details'])
        
        name = data['name'].strip()
        phone = validate_phone(data['phone'])
        vehicle_details = data['vehicle_details'].strip()
        
        if not name or len(name) < 2:
            raise ValidationError("Name must be at least 2 characters long")
        
        if not vehicle_details:
            raise ValidationError("Vehicle details are required")
        
        # Validate email if provided
        email = None
        if data.get('email'):
            email = validate_email(data['email'])
            
            # Check if email already exists
            existing_client = Client.query.filter_by(email=email).first()
            if existing_client:
                raise ValidationError("A client with this email already exists")
        
        # Create new client
        new_client = Client(
            name=name,
            phone=phone,
            email=email,
            vehicle_details=vehicle_details,
            address=data.get('address', '').strip()
        )
        
        db.session.add(new_client)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Client created successfully',
            'data': new_client.to_dict()
        }), 201
        
    except ValidationError as e:
        raise
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Failed to create client: {str(e)}'
        }), 500

@app.route('/api/clients/<int:client_id>', methods=['PUT'])
@jwt_required()
def update_client(client_id):
    """Update client"""
    try:
        client = Client.query.get_or_404(client_id)
        data = request.get_json()
        
        # Validate and update fields
        if 'name' in data:
            name = data['name'].strip()
            if not name or len(name) < 2:
                raise ValidationError("Name must be at least 2 characters long")
            client.name = name
        
        if 'phone' in data:
            client.phone = validate_phone(data['phone'])
        
        if 'email' in data:
            if data['email']:
                email = validate_email(data['email'])
                # Check if email is used by another client
                existing = Client.query.filter_by(email=email).filter(Client.id != client_id).first()
                if existing:
                    raise ValidationError("A client with this email already exists")
                client.email = email
            else:
                client.email = None
        
        if 'vehicle_details' in data:
            vehicle_details = data['vehicle_details'].strip()
            if not vehicle_details:
                raise ValidationError("Vehicle details cannot be empty")
            client.vehicle_details = vehicle_details
        
        if 'address' in data:
            client.address = data['address'].strip()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Client updated successfully',
            'data': client.to_dict()
        }), 200
        
    except ValidationError as e:
        raise
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Failed to update client: {str(e)}'
        }), 500

@app.route('/api/clients/<int:client_id>', methods=['DELETE'])
@jwt_required()
def delete_client(client_id):
    """Delete client"""
    try:
        client = Client.query.get_or_404(client_id)
        
        # Check if client has bookings
        if client.bookings:
            return jsonify({
                'success': False,
                'message': 'Cannot delete client with existing bookings'
            }), 400
        
        db.session.delete(client)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Client deleted successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Failed to delete client: {str(e)}'
        }), 500

# ==================== INVENTORY ROUTES ====================

@app.route('/api/inventory', methods=['GET'])
@jwt_required()
def get_inventory():
    """Get all inventory items"""
    try:
        items = Inventory.query.order_by(Inventory.name).all()
        return jsonify({
            'success': True,
            'data': [item.to_dict() for item in items]
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Failed to fetch inventory: {str(e)}'
        }), 500

@app.route('/api/inventory', methods=['POST'])
@jwt_required()
def create_inventory_item():
    """Create new inventory item"""
    try:
        data = request.get_json()
        
        # Validate required fields
        validate_required_fields(data, ['name', 'category', 'stock_quantity', 'price', 'min_stock'])
        
        name = data['name'].strip()
        if not name:
            raise ValidationError("Item name cannot be empty")
        
        # Validate numeric fields
        try:
            stock_quantity = int(data['stock_quantity'])
            if stock_quantity < 0:
                raise ValidationError("Stock quantity cannot be negative")
        except (ValueError, TypeError):
            raise ValidationError("Stock quantity must be a valid number")
        
        try:
            price = float(data['price'])
            if price < 0:
                raise ValidationError("Price cannot be negative")
        except (ValueError, TypeError):
            raise ValidationError("Price must be a valid number")
        
        try:
            min_stock = int(data['min_stock'])
            if min_stock < 0:
                raise ValidationError("Minimum stock cannot be negative")
        except (ValueError, TypeError):
            raise ValidationError("Minimum stock must be a valid number")
        
        # Create new inventory item
        new_item = Inventory(
            name=name,
            category=data['category'],
            stock_quantity=stock_quantity,
            price=price,
            min_stock=min_stock,
            description=data.get('description', '').strip()
        )
        
        db.session.add(new_item)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Inventory item created successfully',
            'data': new_item.to_dict()
        }), 201
        
    except ValidationError as e:
        raise
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Failed to create inventory item: {str(e)}'
        }), 500

@app.route('/api/inventory/<int:item_id>', methods=['PUT'])
@jwt_required()
def update_inventory_item(item_id):
    """Update inventory item"""
    try:
        item = Inventory.query.get_or_404(item_id)
        data = request.get_json()
        
        # Validate and update fields
        if 'name' in data:
            name = data['name'].strip()
            if not name:
                raise ValidationError("Item name cannot be empty")
            item.name = name
        
        if 'category' in data:
            item.category = data['category']
        
        if 'stock_quantity' in data:
            try:
                stock_quantity = int(data['stock_quantity'])
                if stock_quantity < 0:
                    raise ValidationError("Stock quantity cannot be negative")
                item.stock_quantity = stock_quantity
            except (ValueError, TypeError):
                raise ValidationError("Stock quantity must be a valid number")
        
        if 'price' in data:
            try:
                price = float(data['price'])
                if price < 0:
                    raise ValidationError("Price cannot be negative")
                item.price = price
            except (ValueError, TypeError):
                raise ValidationError("Price must be a valid number")
        
        if 'min_stock' in data:
            try:
                min_stock = int(data['min_stock'])
                if min_stock < 0:
                    raise ValidationError("Minimum stock cannot be negative")
                item.min_stock = min_stock
            except (ValueError, TypeError):
                raise ValidationError("Minimum stock must be a valid number")
        
        if 'description' in data:
            item.description = data['description'].strip()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Inventory item updated successfully',
            'data': item.to_dict()
        }), 200
        
    except ValidationError as e:
        raise
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Failed to update inventory item: {str(e)}'
        }), 500

@app.route('/api/inventory/<int:item_id>', methods=['DELETE'])
@jwt_required()
def delete_inventory_item(item_id):
    """Delete inventory item"""
    try:
        item = Inventory.query.get_or_404(item_id)
        db.session.delete(item)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Inventory item deleted successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Failed to delete inventory item: {str(e)}'
        }), 500

# ==================== BOOKING ROUTES ====================

@app.route('/api/bookings', methods=['GET'])
@jwt_required()
def get_bookings():
    """Get all bookings"""
    try:
        bookings = Booking.query.join(Client).order_by(Booking.booking_date.desc()).all()
        return jsonify({
            'success': True,
            'data': [booking.to_dict() for booking in bookings]
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Failed to fetch bookings: {str(e)}'
        }), 500

@app.route('/api/bookings', methods=['POST'])
@jwt_required()
def create_booking():
    """Create new booking"""
    try:
        data = request.get_json()
        
        # Validate required fields
        validate_required_fields(data, ['client_id', 'service_type', 'booking_date', 'booking_time'])
        
        # Verify client exists
        client = Client.query.get(data['client_id'])
        if not client:
            raise ValidationError("Invalid client ID")
        
        # Validate date
        try:
            booking_date = datetime.strptime(data['booking_date'], '%Y-%m-%d').date()
            if booking_date < datetime.now().date():
                raise ValidationError("Booking date cannot be in the past")
        except ValueError:
            raise ValidationError("Invalid date format. Use YYYY-MM-DD")
        
        # Create new booking
        new_booking = Booking(
            client_id=data['client_id'],
            service_type=data['service_type'],
            booking_date=booking_date,
            booking_time=data['booking_time'],
            status=data.get('status', 'pending'),
            notes=data.get('notes', '').strip()
        )
        
        db.session.add(new_booking)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Booking created successfully',
            'data': new_booking.to_dict()
        }), 201
        
    except ValidationError as e:
        raise
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Failed to create booking: {str(e)}'
        }), 500

@app.route('/api/bookings/<int:booking_id>', methods=['PUT'])
@jwt_required()
def update_booking(booking_id):
    """Update booking"""
    try:
        booking = Booking.query.get_or_404(booking_id)
        data = request.get_json()
        
        if 'status' in data:
            valid_statuses = ['pending', 'confirmed', 'completed', 'cancelled']
            if data['status'] not in valid_statuses:
                raise ValidationError(f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
            booking.status = data['status']
        
        if 'booking_date' in data:
            try:
                booking_date = datetime.strptime(data['booking_date'], '%Y-%m-%d').date()
                if booking_date < datetime.now().date():
                    raise ValidationError("Booking date cannot be in the past")
                booking.booking_date = booking_date
            except ValueError:
                raise ValidationError("Invalid date format. Use YYYY-MM-DD")
        
        if 'booking_time' in data:
            booking.booking_time = data['booking_time']
        
        if 'service_type' in data:
            booking.service_type = data['service_type']
        
        if 'notes' in data:
            booking.notes = data['notes'].strip()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Booking updated successfully',
            'data': booking.to_dict()
        }), 200
        
    except ValidationError as e:
        raise
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Failed to update booking: {str(e)}'
        }), 500

@app.route('/api/bookings/<int:booking_id>', methods=['DELETE'])
@jwt_required()
def delete_booking(booking_id):
    """Delete booking"""
    try:
        booking = Booking.query.get_or_404(booking_id)
        
        # Check if booking has payments
        if booking.payments:
            return jsonify({
                'success': False,
                'message': 'Cannot delete booking with existing payments'
            }), 400
        
        db.session.delete(booking)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Booking deleted successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Failed to delete booking: {str(e)}'
        }), 500

# ==================== PAYMENT ROUTES ====================

@app.route('/api/payments', methods=['GET'])
@jwt_required()
def get_payments():
    """Get all payments"""
    try:
        payments = Payment.query.join(Booking).join(Client).order_by(Payment.payment_date.desc()).all()
        return jsonify({
            'success': True,
            'data': [payment.to_dict() for payment in payments]
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Failed to fetch payments: {str(e)}'
        }), 500

@app.route('/api/payments', methods=['POST'])
@jwt_required()
def create_payment():
    """Create new payment"""
    try:
        data = request.get_json()
        
        # Validate required fields
        validate_required_fields(data, ['booking_id', 'amount', 'payment_method'])
        
        # Verify booking exists
        booking = Booking.query.get(data['booking_id'])
        if not booking:
            raise ValidationError("Invalid booking ID")
        
        # Validate amount
        try:
            amount = float(data['amount'])
            if amount <= 0:
                raise ValidationError("Amount must be greater than zero")
        except (ValueError, TypeError):
            raise ValidationError("Amount must be a valid number")
        
        # Validate payment method
        valid_methods = ['Cash', 'Card', 'M-Pesa', 'Bank Transfer']
        if data['payment_method'] not in valid_methods:
            raise ValidationError(f"Invalid payment method. Must be one of: {', '.join(valid_methods)}")
        
        # Create new payment
        new_payment = Payment(
            booking_id=data['booking_id'],
            amount=amount,
            payment_method=data['payment_method'],
            status='completed',
            phone_number=data.get('phone_number', '').strip(),
            transaction_id=data.get('transaction_id', '').strip()
        )
        
        db.session.add(new_payment)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Payment recorded successfully',
            'data': new_payment.to_dict()
        }), 201
        
    except ValidationError as e:
        raise
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Failed to create payment: {str(e)}'
        }), 500

# ==================== DATABASE INITIALIZATION ====================

def init_db():
    """Initialize database and create default data"""
    with app.app_context():
        db.create_all()
        
        # Create admin user if not exists
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                email='admin@autocare.com',
                name='System Administrator',
                role='admin'
            )
            admin.set_password('Admin@123')
            db.session.add(admin)
            db.session.commit()
            print("✓ Admin user created: admin@autocare.com / Admin@123")
        
        # Create sample staff user
        if not User.query.filter_by(username='staff').first():
            staff = User(
                username='staff',
                email='staff@autocare.com',
                name='Staff Member',
                role='staff'
            )
            staff.set_password('Staff@123')
            db.session.add(staff)
            db.session.commit()
            print("✓ Staff user created: staff@autocare.com / Staff@123")
        
        print("\n=== Database initialized successfully! ===\n")

# ==================== MAIN ====================

if __name__ == '__main__':
    init_db()
    print("\n=== AutoCare Garage Management System ===")
    print("Backend server starting...")
    print("API running on: http://localhost:5000")
    print("=" * 40 + "\n")
    app.run(debug=True, port=5000, host='0.0.0.0')