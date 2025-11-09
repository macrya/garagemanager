from flask import Flask, request, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_cors import CORS
from datetime import datetime, timedelta
import os
import sys

app = Flask(__name__, static_folder='app')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///garage.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'jwt-dev-secret-key')
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
    email = db.Column(db.String(120), unique=True, nullable=False)
    reset_token = db.Column(db.String(100), unique=True)
    reset_token_expiration = db.Column(db.DateTime)

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

@app.route('/api/auth/forgot-password', methods=['POST'])
def forgot_password():
    try:
        data = request.get_json()
        if not data or not data.get('email'):
            return jsonify({'success': False, 'message': 'Email required'}), 400

        user = User.query.filter_by(email=data['email']).first()
        if not user:
            return jsonify({'success': True, 'message': 'If an account with that email exists, a password reset link has been sent.'}), 200

        # Generate a random token
        token = os.urandom(24).hex()
        user.reset_token = token
        user.reset_token_expiration = datetime.utcnow() + timedelta(hours=1)
        db.session.commit()

        # In a real application, you would email the user the reset link
        reset_link = f'http://localhost:5000/reset-password?token={token}'
        print(f'Password reset link: {reset_link}')

        return jsonify({'success': True, 'message': 'If an account with that email exists, a password reset link has been sent.', 'reset_link': reset_link}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': f'Forgot password error: {str(e)}'}), 500

@app.route('/api/auth/change-password', methods=['POST'])
@jwt_required()
def change_password():
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404

        data = request.get_json()
        if not data or not data.get('current_password') or not data.get('new_password'):
            return jsonify({'success': False, 'message': 'Current and new password required'}), 400

        if not user.check_password(data['current_password']):
            return jsonify({'success': False, 'message': 'Incorrect current password'}), 401

        user.set_password(data['new_password'])
        db.session.commit()

        return jsonify({'success': True, 'message': 'Password changed successfully'}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': f'Change password error: {str(e)}'}), 500

@app.route('/api/auth/verify', methods=['GET'])
@jwt_required()
def verify_token():
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        if user:
            return jsonify({
                'success': True,
                'user': {'id': user.id, 'username': user.username, 'name': user.name, 'role': user.role}
            }), 200
        return jsonify({'success': False, 'message': 'Invalid token'}), 401
    except Exception as e:
        return jsonify({'success': False, 'message': f'Token verification error: {str(e)}'}), 500

@app.route('/api/dashboard', methods=['GET'])
@jwt_required()
def get_dashboard():
    try:
        total_clients = Client.query.count()
        pending_bookings = Booking.query.filter_by(status='pending').count()
        low_stock_items = Inventory.query.filter(Inventory.stock_quantity <= Inventory.min_stock).count()
        pending_payments = Payment.query.filter_by(status='pending').count()

        recent_bookings_data = db.session.query(Booking, Client).join(Client).order_by(Booking.booking_date.desc()).limit(5).all()
        recent_bookings = [{
            'client_name': client.name,
            'service_type': booking.service_type,
            'booking_date': booking.booking_date.isoformat(),
            'status': booking.status
        } for booking, client in recent_bookings_data]

        low_stock_alerts_data = Inventory.query.filter(Inventory.stock_quantity <= Inventory.min_stock).order_by(Inventory.stock_quantity).limit(5).all()
        low_stock_alerts = [{
            'name': item.name,
            'stock_quantity': item.stock_quantity,
            'min_stock': item.min_stock
        } for item in low_stock_alerts_data]
        
        return jsonify({
            'success': True,
            'data': {
                'total_clients': total_clients,
                'pending_bookings': pending_bookings,
                'low_stock_items': low_stock_items,
                'pending_payments': pending_payments,
                'recent_bookings': recent_bookings,
                'low_stock_alerts': low_stock_alerts
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Dashboard error: {str(e)}'}), 500

@app.route('/api/inventory', methods=['POST'])
@jwt_required()
def create_inventory_item():
    try:
        data = request.get_json()
        if not data or not data.get('name') or not data.get('category') or not data.get('stock_quantity') or not data.get('price') or not data.get('min_stock'):
            return jsonify({'success': False, 'message': 'Name, category, stock quantity, price, and min stock required'}), 400

        new_item = Inventory(
            name=data['name'],
            category=data['category'],
            stock_quantity=data['stock_quantity'],
            price=data['price'],
            min_stock=data['min_stock']
        )
        db.session.add(new_item)
        db.session.commit()

        return jsonify({'success': True, 'message': 'Inventory item created successfully', 'data': {'id': new_item.id}}), 201
    except Exception as e:
        return jsonify({'success': False, 'message': f'Inventory item creation error: {str(e)}'}), 500

@app.route('/api/inventory/<int:item_id>', methods=['PUT'])
@jwt_required()
def update_inventory_item(item_id):
    try:
        item = Inventory.query.get(item_id)
        if not item:
            return jsonify({'success': False, 'message': 'Inventory item not found'}), 404

        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400

        item.name = data.get('name', item.name)
        item.category = data.get('category', item.category)
        item.stock_quantity = data.get('stock_quantity', item.stock_quantity)
        item.price = data.get('price', item.price)
        item.min_stock = data.get('min_stock', item.min_stock)

        db.session.commit()

        return jsonify({'success': True, 'message': 'Inventory item updated successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Inventory item update error: {str(e)}'}), 500

@app.route('/api/inventory', methods=['GET'])
@jwt_required()
def get_inventory():
    try:
        items = Inventory.query.all()
        inventory_data = [{
            'id': item.id, 'name': item.name, 'category': item.category,
            'stock_quantity': item.stock_quantity, 'price': item.price, 'min_stock': item.min_stock,
            'is_low_stock': item.stock_quantity <= item.min_stock
        } for item in items]
        return jsonify({'success': True, 'data': inventory_data})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Inventory error: {str(e)}'}), 500

@app.route('/api/clients', methods=['GET'])
@jwt_required()
def get_clients():
    try:
        clients = Client.query.all()
        clients_data = [{
            'id': client.id, 'name': client.name, 'phone': client.phone,
            'email': client.email, 'vehicle_details': client.vehicle_details
        } for client in clients]
        return jsonify({'success': True, 'data': clients_data})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Clients error: {str(e)}'}), 500

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
        return jsonify({'success': True, 'data': bookings_data})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Bookings error: {str(e)}'}), 500

@app.route('/api/clients', methods=['POST'])
@jwt_required()
def create_client():
    try:
        data = request.get_json()
        if not data or not data.get('name') or not data.get('phone') or not data.get('vehicle_details'):
            return jsonify({'success': False, 'message': 'Name, phone, and vehicle details required'}), 400

        new_client = Client(
            name=data['name'],
            phone=data['phone'],
            email=data.get('email'),
            vehicle_details=data['vehicle_details']
        )
        db.session.add(new_client)
        db.session.commit()

        return jsonify({'success': True, 'message': 'Client created successfully', 'data': {'id': new_client.id}}), 201
    except Exception as e:
        return jsonify({'success': False, 'message': f'Client creation error: {str(e)}'}), 500

@app.route('/api/clients/<int:client_id>', methods=['PUT'])
@jwt_required()
def update_client(client_id):
    try:
        client = Client.query.get(client_id)
        if not client:
            return jsonify({'success': False, 'message': 'Client not found'}), 404

        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400

        client.name = data.get('name', client.name)
        client.phone = data.get('phone', client.phone)
        client.email = data.get('email', client.email)
        client.vehicle_details = data.get('vehicle_details', client.vehicle_details)

        db.session.commit()

        return jsonify({'success': True, 'message': 'Client updated successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Client update error: {str(e)}'}), 500

@app.route('/api/clients/<int:client_id>', methods=['DELETE'])
@jwt_required()
def delete_client(client_id):
    try:
        client = Client.query.get(client_id)
        if not client:
            return jsonify({'success': False, 'message': 'Client not found'}), 404

        db.session.delete(client)
        db.session.commit()

        return jsonify({'success': True, 'message': 'Client deleted successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Client deletion error: {str(e)}'}), 500

@app.route('/api/bookings', methods=['POST'])
@jwt_required()
def create_booking():
    try:
        data = request.get_json()
        if not data or not data.get('client_id') or not data.get('service_type') or not data.get('booking_date') or not data.get('booking_time'):
            return jsonify({'success': False, 'message': 'Client ID, service type, booking date, and booking time required'}), 400

        new_booking = Booking(
            client_id=data['client_id'],
            service_type=data['service_type'],
            booking_date=datetime.strptime(data['booking_date'], '%Y-%m-%d').date(),
            booking_time=data['booking_time'],
            status=data.get('status', 'pending')
        )
        db.session.add(new_booking)
        db.session.commit()

        return jsonify({'success': True, 'message': 'Booking created successfully', 'data': {'id': new_booking.id}}), 201
    except Exception as e:
        return jsonify({'success': False, 'message': f'Booking creation error: {str(e)}'}), 500

@app.route('/api/bookings/<int:booking_id>', methods=['PUT'])
@jwt_required()
def update_booking(booking_id):
    try:
        booking = Booking.query.get(booking_id)
        if not booking:
            return jsonify({'success': False, 'message': 'Booking not found'}), 404

        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400

        booking.client_id = data.get('client_id', booking.client_id)
        booking.service_type = data.get('service_type', booking.service_type)
        if data.get('booking_date'):
            booking.booking_date = datetime.strptime(data['booking_date'], '%Y-%m-%d').date()
        booking.booking_time = data.get('booking_time', booking.booking_time)
        booking.status = data.get('status', booking.status)

        db.session.commit()

        return jsonify({'success': True, 'message': 'Booking updated successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Booking update error: {str(e)}'}), 500

@app.route('/api/bookings/<int:booking_id>', methods=['DELETE'])
@jwt_required()
def delete_booking(booking_id):
    try:
        booking = Booking.query.get(booking_id)
        if not booking:
            return jsonify({'success': False, 'message': 'Booking not found'}), 404

        db.session.delete(booking)
        db.session.commit()

        return jsonify({'success': True, 'message': 'Booking deleted successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Booking deletion error: {str(e)}'}), 500

@app.route('/api/payments', methods=['GET'])
@jwt_required()
def get_payments():
    try:
        payments = Payment.query.join(Booking).all()
        payments_data = [{
            'id': payment.id,
            'booking_id': payment.booking_id,
            'amount': payment.amount,
            'payment_method': payment.payment_method,
            'status': payment.status,
            'payment_date': payment.booking.booking_date.isoformat()
        } for payment in payments]
        return jsonify({'success': True, 'data': payments_data})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Payments error: {str(e)}'}), 500

@app.route('/api/payments/<int:payment_id>', methods=['PUT'])
@jwt_required()
def update_payment(payment_id):
    try:
        payment = Payment.query.get(payment_id)
        if not payment:
            return jsonify({'success': False, 'message': 'Payment not found'}), 404

        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400

        payment.booking_id = data.get('booking_id', payment.booking_id)
        payment.amount = data.get('amount', payment.amount)
        payment.payment_method = data.get('payment_method', payment.payment_method)
        payment.status = data.get('status', payment.status)

        db.session.commit()

        return jsonify({'success': True, 'message': 'Payment updated successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Payment update error: {str(e)}'}), 500

@app.route('/api/payments/<int:payment_id>', methods=['DELETE'])
@jwt_required()
def delete_payment(payment_id):
    try:
        payment = Payment.query.get(payment_id)
        if not payment:
            return jsonify({'success': False, 'message': 'Payment not found'}), 404

        db.session.delete(payment)
        db.session.commit()

        return jsonify({'success': True, 'message': 'Payment deleted successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Payment deletion error: {str(e)}'}), 500

@app.route('/api/system/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
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

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    else:
        return send_from_directory(app.static_folder, 'app.html')

def init_db():
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', name='System Administrator', role='admin')
            admin.set_password('admin123')
            db.session.add(admin)
            
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

            payment1 = Payment(booking_id=1, amount=1500.0, payment_method='cash', status='pending')
            db.session.add(payment1)
            
            db.session.commit()
            print("✅ Sample data created")

@app.route('/api/payments', methods=['POST'])
@jwt_required()
def create_payment():
    try:
        data = request.get_json()
        if not data or not data.get('booking_id') or not data.get('amount') or not data.get('payment_method'):
            return jsonify({'success': False, 'message': 'Booking ID, amount, and payment method required'}), 400

        new_payment = Payment(
            booking_id=data['booking_id'],
            amount=data['amount'],
            payment_method=data['payment_method'],
            status='completed'
        )
        db.session.add(new_payment)
        db.session.commit()

        return jsonify({'success': True, 'message': 'Payment created successfully', 'data': {'id': new_payment.id}}), 201
    except Exception as e:
        return jsonify({'success': False, 'message': f'Payment creation error: {str(e)}'}), 500

if __name__ == '__main__':
    with app.app_context():
        init_db()
    is_prod = os.environ.get('FLASK_ENV') == 'production'
    print("🚀 Garage Management System Backend Running on http://localhost:5000")
    print("📊 Health Check: http://localhost:5000/api/system/health")
    print("🔑 Test Login: username='admin', password='admin123'")
    app.run(debug=not is_prod, host='0.0.0.0', port=5000)