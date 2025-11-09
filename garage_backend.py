from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_cors import CORS
from datetime import datetime, timedelta
import os
import sys

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-secret-key-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///garage.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = 'jwt-dev-secret-key'
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
jwt = JWTManager(app)
CORS(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), default='staff')

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120))
    vehicle_details = db.Column(db.String(200), nullable=False)

class Inventory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    stock_quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    min_stock = db.Column(db.Integer, nullable=False)

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    service_type = db.Column(db.String(100), nullable=False)
    booking_date = db.Column(db.Date, nullable=False)
    booking_time = db.Column(db.String(10), nullable=False)
    status = db.Column(db.String(20), default='pending')
    client = db.relationship('Client', backref='bookings')

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('booking.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), default='pending')
    booking = db.relationship('Booking', backref='payments')

@app.route('/api/auth/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        if not data or not data.get('username') or not data.get('password'):
            return jsonify({'message': 'Username and password required'}), 400
        
        user = User.query.filter_by(username=data['username']).first()
        
        if user and user.check_password(data['password']):
            access_token = create_access_token(identity=user.id)
            return jsonify({
                'access_token': access_token,
                'user': {'id': user.id, 'username': user.username, 'name': user.name, 'role': user.role}
            }), 200
        
        return jsonify({'message': 'Invalid credentials'}), 401
    except Exception as e:
        return jsonify({'message': f'Login error: {str(e)}'}), 500

@app.route('/api/auth/verify', methods=['GET'])
@jwt_required()
def verify_token():
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        if user:
            return jsonify({
                'user': {'id': user.id, 'username': user.username, 'name': user.name, 'role': user.role}
            }), 200
        return jsonify({'message': 'Invalid token'}), 401
    except Exception as e:
        return jsonify({'message': f'Token verification error: {str(e)}'}), 500

@app.route('/api/dashboard', methods=['GET'])
@jwt_required()
def get_dashboard():
    try:
        total_clients = Client.query.count()
        pending_bookings = Booking.query.filter_by(status='pending').count()
        low_stock_items = Inventory.query.filter(Inventory.stock_quantity <= Inventory.min_stock).count()
        pending_payments = Payment.query.filter_by(status='pending').count()
        
        return jsonify({
            'total_clients': total_clients,
            'pending_bookings': pending_bookings,
            'low_stock_items': low_stock_items,
            'pending_payments': pending_payments,
            'recent_bookings': [],
            'low_stock_alerts': []
        })
    except Exception as e:
        return jsonify({'message': f'Dashboard error: {str(e)}'}), 500

@app.route('/api/inventory', methods=['GET'])
@jwt_required()
def get_inventory():
    try:
        items = Inventory.query.all()
        inventory_data = [{
            'id': item.id, 'name': item.name, 'category': item.category,
            'stock_quantity': item.stock_quantity, 'price': item.price, 'min_stock': item.min_stock
        } for item in items]
        return jsonify(inventory_data)
    except Exception as e:
        return jsonify({'message': f'Inventory error: {str(e)}'}), 500

@app.route('/api/clients', methods=['GET'])
@jwt_required()
def get_clients():
    try:
        clients = Client.query.all()
        clients_data = [{
            'id': client.id, 'name': client.name, 'phone': client.phone,
            'email': client.email, 'vehicle_details': client.vehicle_details
        } for client in clients]
        return jsonify(clients_data)
    except Exception as e:
        return jsonify({'message': f'Clients error: {str(e)}'}), 500

@app.route('/api/bookings', methods=['GET'])
@jwt_required()
def get_bookings():
    try:
        bookings = Booking.query.join(Client).all()
        bookings_data = [{
            'id': booking.id, 'client_name': booking.client.name,
            'service_type': booking.service_type, 'booking_date': booking.booking_date.isoformat(),
            'booking_time': booking.booking_time, 'status': booking.status
        } for booking in bookings]
        return jsonify(bookings_data)
    except Exception as e:
        return jsonify({'message': f'Bookings error: {str(e)}'}), 500

@app.route('/api/system/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        db.session.execute('SELECT 1')
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'database': 'connected',
            'version': '1.0.0'
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'timestamp': datetime.now().isoformat(),
            'database': 'disconnected',
            'error': str(e)
        }), 500

def init_db():
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', name='System Administrator', role='admin')
            admin.set_password('admin123')
            db.session.add(admin)
            
            # Add sample data
            client1 = Client(name='John Doe', phone='+254712345678', 
                           email='john@example.com', vehicle_details='Toyota Corolla 2020')
            db.session.add(client1)
            
            inventory1 = Inventory(name='Engine Oil', category='Fluids', 
                                 stock_quantity=50, price=1500.0, min_stock=10)
            db.session.add(inventory1)
            
            booking1 = Booking(client_id=1, service_type='Oil Change',
                            booking_date=datetime.now().date(), booking_time='10:00',
                            status='pending')
            db.session.add(booking1)
            
            db.session.commit()
            print("✅ Sample data created")

if __name__ == '__main__':
    with app.app_context():
        init_db()
    print("🚀 Garage Management System Backend Running on http://localhost:5000")
    print("📊 Health Check: http://localhost:5000/api/system/health")
    print("🔑 Test Login: username='admin', password='admin123'")
    app.run(debug=True, host='0.0.0.0', port=5000)
