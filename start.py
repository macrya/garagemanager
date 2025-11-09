#!/usr/bin/env python3
"""
Garage Management System - Comprehensive Startup & Testing Script
Run this script to test, validate, and start the application
"""

import os
import sys
import subprocess
import time
import webbrowser
import sqlite3
import requests
import json
from pathlib import Path
from threading import Thread
from datetime import datetime

class GarageManagementStarter:
    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.backend_process = None
        self.backend_url = "http://localhost:5000"
        self.test_results = {}
        
    def print_header(self):
        print("\n" + "="*70)
        print("           GARAGE MANAGEMENT SYSTEM - STARTUP & TESTING")
        print("="*70)
        
    def check_python_version(self):
        """Check if Python version is compatible"""
        print("\n🔍 Checking Python version...")
        if sys.version_info < (3, 7):
            print(f"❌ Python 3.7+ is required. Current version: {sys.version}")
            return False
        print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} - Compatible")
        return True

    def install_dependencies(self):
        """Install required Python packages"""
        print("\n📦 Installing dependencies...")
        
        requirements = [
            "flask",
            "flask-sqlalchemy", 
            "flask-bcrypt",
            "flask-jwt-extended",
            "flask-cors",
            "requests"
        ]
        
        success_count = 0
        for package in requirements:
            try:
                print(f"   Installing {package}...", end=" ")
                subprocess.check_call([sys.executable, "-m", "pip", "install", package], 
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print("✅")
                success_count += 1
            except subprocess.CalledProcessError:
                print("❌")
                
        return success_count == len(requirements)

    def check_dependencies(self):
        """Check if all dependencies are installed"""
        print("\n🔍 Checking dependencies...")
        
        dependencies = {
            "flask": "Flask",
            "flask_sqlalchemy": "Flask-SQLAlchemy", 
            "flask_bcrypt": "Flask-Bcrypt",
            "flask_jwt_extended": "Flask-JWT-Extended",
            "flask_cors": "Flask-CORS",
            "requests": "requests"
        }
        
        missing_deps = []
        for import_name, package_name in dependencies.items():
            try:
                __import__(import_name)
                print(f"   ✅ {package_name}")
            except ImportError:
                print(f"   ❌ {package_name}")
                missing_deps.append(package_name)
        
        if missing_deps:
            print(f"\n⚠️  Missing dependencies: {', '.join(missing_deps)}")
            return False
        return True

    def create_directory_structure(self):
        """Create necessary directories"""
        print("\n📁 Creating directory structure...")
        
        directories = ["static", "logs", "backups", "tests"]
        for directory in directories:
            dir_path = self.base_dir / directory
            dir_path.mkdir(exist_ok=True)
            print(f"   ✅ ./{directory}/")

    def create_test_backend(self):
        """Create a test version of the backend with enhanced error handling"""
        backend_content = '''from flask import Flask, request, jsonify
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
'''
        
        backend_file = self.base_dir / "app.py"
        with open(backend_file, 'w', encoding='utf-8') as f:
            f.write(backend_content)
        print("   ✅ Backend application created")
        return backend_file

    def create_test_runner(self):
        """Create a comprehensive test script"""
        test_content = '''import unittest
import requests
import json
import time
import sys
from pathlib import Path

class TestGarageManagementSystem(unittest.TestCase):
    BASE_URL = "http://localhost:5000/api"
    token = None
    
    def setUp(self):
        """Wait for backend to be ready"""
        max_retries = 10
        for i in range(max_retries):
            try:
                response = requests.get("http://localhost:5000/api/system/health", timeout=5)
                if response.status_code == 200:
                    break
            except:
                if i == max_retries - 1:
                    self.skipTest("Backend not available")
                time.sleep(1)
    
    def test_1_health_check(self):
        """Test health check endpoint"""
        response = requests.get("http://localhost:5000/api/system/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'healthy')
        print("✅ Health check passed")
    
    def test_2_login(self):
        """Test authentication"""
        login_data = {
            "username": "admin",
            "password": "admin123"
        }
        response = requests.post(f"{self.BASE_URL}/auth/login", json=login_data)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('access_token', data)
        self.assertIn('user', data)
        TestGarageManagementSystem.token = data['access_token']
        print("✅ Login test passed")
    
    def test_3_token_verification(self):
        """Test token verification"""
        headers = {'Authorization': f'Bearer {self.token}'}
        response = requests.get(f"{self.BASE_URL}/auth/verify", headers=headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('user', data)
        print("✅ Token verification passed")
    
    def test_4_dashboard(self):
        """Test dashboard endpoint"""
        headers = {'Authorization': f'Bearer {self.token}'}
        response = requests.get(f"{self.BASE_URL}/dashboard", headers=headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('total_clients', data)
        self.assertIn('pending_bookings', data)
        print("✅ Dashboard test passed")
    
    def test_5_inventory(self):
        """Test inventory endpoints"""
        headers = {'Authorization': f'Bearer {self.token}'}
        response = requests.get(f"{self.BASE_URL}/inventory", headers=headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
        print("✅ Inventory test passed")
    
    def test_6_clients(self):
        """Test clients endpoints"""
        headers = {'Authorization': f'Bearer {self.token}'}
        response = requests.get(f"{self.BASE_URL}/clients", headers=headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
        print("✅ Clients test passed")
    
    def test_7_bookings(self):
        """Test bookings endpoints"""
        headers = {'Authorization': f'Bearer {self.token}'}
        response = requests.get(f"{self.BASE_URL}/bookings", headers=headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
        print("✅ Bookings test passed")

def run_tests():
    """Run all tests and return results"""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestGarageManagementSystem)
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(suite)
    return result.wasSuccessful()

if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
'''
        
        test_file = self.base_dir / "tests" / "test_system.py"
        test_file.parent.mkdir(exist_ok=True)
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write(test_content)
        print("   ✅ Test suite created")
        return test_file

    def start_backend(self):
        """Start the backend server"""
        print("\n🚀 Starting backend server...")
        
        backend_file = self.base_dir / "app.py"
        if not backend_file.exists():
            print("   ❌ Backend file not found")
            return False
            
        try:
            self.backend_process = subprocess.Popen(
                [sys.executable, str(backend_file)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait for backend to start
            print("   ⏳ Waiting for backend to start...", end=" ")
            for i in range(30):  # 30 second timeout
                try:
                    response = requests.get(f"{self.backend_url}/api/system/health", timeout=1)
                    if response.status_code == 200:
                        print("✅")
                        return True
                except:
                    pass
                time.sleep(1)
                
            print("❌ (Timeout)")
            return False
            
        except Exception as e:
            print(f"   ❌ Failed to start backend: {e}")
            return False

    def stop_backend(self):
        """Stop the backend server"""
        if self.backend_process:
            print("\n🛑 Stopping backend server...")
            self.backend_process.terminate()
            try:
                self.backend_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.backend_process.kill()
            print("✅ Backend stopped")

    def run_tests(self):
        """Run the test suite"""
        print("\n🧪 Running system tests...")
        
        test_file = self.base_dir / "tests" / "test_system.py"
        if not test_file.exists():
            print("   ❌ Test file not found")
            return False
            
        try:
            result = subprocess.run(
                [sys.executable, str(test_file)],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            print("\n" + "="*50)
            print("TEST RESULTS")
            print("="*50)
            print(result.stdout)
            if result.stderr:
                print("ERRORS:")
                print(result.stderr)
            
            return result.returncode == 0
            
        except subprocess.TimeoutExpired:
            print("   ❌ Tests timed out")
            return False
        except Exception as e:
            print(f"   ❌ Test execution failed: {e}")
            return False

    def check_system_health(self):
        """Check system health and endpoints"""
        print("\n🏥 Performing health checks...")
        
        endpoints = [
            ("/api/system/health", "GET"),
            ("/api/auth/login", "POST"),
            ("/api/dashboard", "GET"),
            ("/api/inventory", "GET"),
            ("/api/clients", "GET"),
            ("/api/bookings", "GET")
        ]
        
        all_healthy = True
        
        for endpoint, method in endpoints:
            try:
                url = f"{self.backend_url}{endpoint}"
                if method == "GET":
                    response = requests.get(url, timeout=5)
                else:
                    response = requests.post(url, json={}, timeout=5)
                
                status = "✅" if response.status_code in [200, 401] else "❌"
                print(f"   {status} {method} {endpoint} - {response.status_code}")
                
                if response.status_code >= 500:
                    all_healthy = False
                    
            except Exception as e:
                print(f"   ❌ {method} {endpoint} - Error: {e}")
                all_healthy = False
                
        return all_healthy

    def open_browser(self):
        """Open browser with the application"""
        print("\n🌐 Opening application in browser...")
        time.sleep(2)
        webbrowser.open(self.backend_url)

    def cleanup(self):
        """Clean up temporary files"""
        print("\n🧹 Cleaning up...")
        files_to_remove = ["garage.db", "garage_backend.py"]
        for file in files_to_remove:
            file_path = self.base_dir / file
            if file_path.exists():
                file_path.unlink()
                print(f"   ✅ Removed {file}")

    def run(self):
        """Main execution method"""
        self.print_header()
        
        # Initial checks
        if not self.check_python_version():
            sys.exit(1)
            
        if not self.check_dependencies():
            print("\n⚠️  Installing missing dependencies...")
            if not self.install_dependencies():
                print("❌ Failed to install dependencies")
                sys.exit(1)
        
        # Setup
        self.create_directory_structure()
        self.create_test_backend()
        self.create_test_runner()
        
        # Start backend
        if not self.start_backend():
            print("❌ Failed to start backend server")
            sys.exit(1)
        
        try:
            # Run health checks
            if not self.check_system_health():
                print("❌ Health checks failed")
                sys.exit(1)
            
            # Run tests
            test_success = self.run_tests()
            
            # Show final status
            print("\n" + "="*70)
            print("STARTUP COMPLETE")
            print("="*70)
            print(f"🔧 Backend URL: {self.backend_url}")
            print(f"📊 Health Check: {self.backend_url}/api/system/health")
            print(f"🧪 Tests: {'PASSED ✅' if test_success else 'FAILED ❌'}")
            print("🔑 Test Credentials: username='admin', password='admin123'")
            print("\nPress Ctrl+C to stop the application")
            
            # Open browser
            self.open_browser()
            
            # Keep running
            while True:
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\n\n👋 Shutting down...")
        finally:
            self.stop_backend()
            self.cleanup()

def main():
    """Main entry point"""
    starter = GarageManagementStarter()
    starter.run()

if __name__ == "__main__":
    main()