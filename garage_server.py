#!/usr/bin/env python3
"""
Garage Management System - Standalone Web Server
No external dependencies required - uses only Python standard library
"""

import http.server
import socketserver
import json
import sqlite3
import urllib.parse
import hashlib
import secrets
from datetime import datetime, timedelta
import os
import mimetypes

PORT = int(os.environ.get('PORT', 5000))
DB_FILE = 'garage_management.db'

# Initialize database
def init_database():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Create tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT NOT NULL,
            address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            make TEXT NOT NULL,
            model TEXT NOT NULL,
            year INTEGER NOT NULL,
            license_plate TEXT UNIQUE NOT NULL,
            vin TEXT,
            color TEXT,
            engine_type TEXT,
            transmission TEXT,
            fuel_type TEXT,
            current_odometer INTEGER DEFAULT 0,
            oil_change_interval INTEGER DEFAULT 5000,
            last_service_date TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id INTEGER NOT NULL,
            service_type TEXT NOT NULL,
            description TEXT,
            labor_cost REAL DEFAULT 0,
            parts_cost REAL DEFAULT 0,
            total_cost REAL NOT NULL,
            status TEXT DEFAULT 'scheduled',
            service_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_date TIMESTAMP,
            technician TEXT,
            notes TEXT,
            labor_hours REAL DEFAULT 0,
            payment_status TEXT DEFAULT 'unpaid',
            FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE CASCADE
        )
    ''')

    # Parts and inventory table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS parts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            part_number TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            quantity INTEGER DEFAULT 0,
            unit_cost REAL NOT NULL,
            reorder_level INTEGER DEFAULT 10,
            supplier TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Service parts junction table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS service_parts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_id INTEGER NOT NULL,
            part_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            FOREIGN KEY (service_id) REFERENCES services(id) ON DELETE CASCADE,
            FOREIGN KEY (part_id) REFERENCES parts(id)
        )
    ''')

    # Time tracking for services
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS time_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_id INTEGER NOT NULL,
            technician TEXT NOT NULL,
            start_time TIMESTAMP NOT NULL,
            end_time TIMESTAMP,
            duration_hours REAL,
            notes TEXT,
            FOREIGN KEY (service_id) REFERENCES services(id) ON DELETE CASCADE
        )
    ''')

    # Expenses table for financial tracking
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            description TEXT NOT NULL,
            amount REAL NOT NULL,
            expense_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notes TEXT
        )
    ''')

    # Odometer readings
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS odometer_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id INTEGER NOT NULL,
            service_id INTEGER,
            reading INTEGER NOT NULL,
            reading_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE CASCADE,
            FOREIGN KEY (service_id) REFERENCES services(id) ON DELETE SET NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'staff',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')

    # Add sample data if database is empty
    cursor.execute('SELECT COUNT(*) FROM customers')
    if cursor.fetchone()[0] == 0:
        # Add admin user
        password_hash = hashlib.sha256('admin123'.encode()).hexdigest()
        cursor.execute('INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)',
                      ('admin', password_hash, 'admin'))

        # Add sample customers
        cursor.execute('''INSERT INTO customers (name, email, phone, address) VALUES
            ('John Smith', 'john.smith@email.com', '555-0101', '123 Main St'),
            ('Sarah Johnson', 'sarah.j@email.com', '555-0102', '456 Oak Ave'),
            ('Mike Williams', 'mike.w@email.com', '555-0103', '789 Pine Rd')
        ''')

        # Add sample vehicles
        cursor.execute('''INSERT INTO vehicles (customer_id, make, model, year, license_plate, color) VALUES
            (1, 'Toyota', 'Camry', 2020, 'ABC-123', 'Silver'),
            (1, 'Honda', 'Civic', 2019, 'XYZ-789', 'Blue'),
            (2, 'Ford', 'F-150', 2021, 'DEF-456', 'Black'),
            (3, 'Chevrolet', 'Malibu', 2018, 'GHI-789', 'White')
        ''')

        # Add sample parts
        cursor.execute('''INSERT INTO parts (part_number, name, description, quantity, unit_cost, reorder_level, supplier) VALUES
            ('OIL-001', 'Engine Oil 5W-30', 'Synthetic motor oil 5W-30', 50, 8.99, 15, 'AutoParts Inc'),
            ('FILTER-001', 'Oil Filter', 'Standard oil filter', 30, 4.50, 10, 'AutoParts Inc'),
            ('BRAKE-PAD-001', 'Brake Pads Front', 'Ceramic brake pads', 20, 45.00, 8, 'BrakeSupply Co'),
            ('TIRE-001', 'All-Season Tire', '225/65R17 all-season', 25, 89.99, 12, 'TireWarehouse'),
            ('COOLANT-001', 'Engine Coolant', 'Universal antifreeze coolant', 40, 12.99, 10, 'AutoParts Inc')
        ''')

        # Add sample services with new schema
        cursor.execute('''INSERT INTO services
            (vehicle_id, service_type, description, labor_cost, parts_cost, total_cost, status, technician, labor_hours, payment_status) VALUES
            (1, 'Oil Change', 'Regular maintenance oil change', 25.00, 20.00, 45.00, 'completed_paid', 'Mike', 0.5, 'paid'),
            (2, 'Brake Inspection', 'Annual brake system inspection', 60.00, 20.00, 80.00, 'in_progress', 'Sarah', 1.5, 'unpaid'),
            (3, 'Tire Rotation', 'Rotate all four tires', 35.00, 0.00, 35.00, 'scheduled', NULL, 0, 'unpaid'),
            (4, 'Engine Diagnostic', 'Check engine light diagnosis', 120.00, 0.00, 120.00, 'awaiting_parts', 'Mike', 2.0, 'unpaid')
        ''')

        # Add sample expenses
        cursor.execute('''INSERT INTO expenses (category, description, amount) VALUES
            ('Rent', 'Monthly garage rent', 2000.00),
            ('Utilities', 'Electricity and water', 350.00),
            ('Salaries', 'Staff salaries', 5000.00),
            ('Equipment', 'New diagnostic tool', 450.00)
        ''')

    conn.commit()
    conn.close()
    print(f"✅ Database initialized: {DB_FILE}")

# Authentication helpers
def create_session(user_id):
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now() + timedelta(hours=24)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO sessions (user_id, token, expires_at) VALUES (?, ?, ?)',
                  (user_id, token, expires_at.isoformat()))
    conn.commit()
    conn.close()
    return token

def verify_session(token):
    if not token:
        return None
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT u.id, u.username, u.role
        FROM sessions s
        JOIN users u ON s.user_id = u.id
        WHERE s.token = ? AND s.expires_at > ?
    ''', (token, datetime.now().isoformat()))
    user = cursor.fetchone()
    conn.close()
    return {'id': user[0], 'username': user[1], 'role': user[2]} if user else None

# Request handler
class GarageRequestHandler(http.server.SimpleHTTPRequestHandler):

    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.serve_frontend()
        elif self.path.startswith('/api/dashboard'):
            self.handle_dashboard()
        elif self.path.startswith('/api/customers/') and '/history' in self.path:
            customer_id = self.path.split('/')[-2]
            self.handle_customer_history(customer_id)
        elif self.path.startswith('/api/customers'):
            self.handle_get_customers()
        elif self.path.startswith('/api/vehicles/') and '/history' in self.path:
            vehicle_id = self.path.split('/')[-2]
            self.handle_vehicle_history(vehicle_id)
        elif self.path.startswith('/api/vehicles'):
            self.handle_get_vehicles()
        elif self.path.startswith('/api/services/') and '/invoice' in self.path:
            service_id = self.path.split('/')[-2]
            self.handle_generate_invoice(service_id)
        elif self.path.startswith('/api/services'):
            self.handle_get_services()
        elif self.path.startswith('/api/parts'):
            self.handle_get_parts()
        elif self.path.startswith('/api/expenses'):
            self.handle_get_expenses()
        elif self.path.startswith('/api/time-entries'):
            self.handle_get_time_entries()
        elif self.path.startswith('/api/stats'):
            self.handle_stats()
        elif self.path.startswith('/api/financial-summary'):
            self.handle_financial_summary()
        else:
            self.send_error(404, 'Not Found')

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else '{}'

        try:
            data = json.loads(body) if body else {}
        except:
            data = {}

        if self.path == '/api/login':
            self.handle_login(data)
        elif self.path == '/api/customers':
            self.handle_add_customer(data)
        elif self.path == '/api/vehicles':
            self.handle_add_vehicle(data)
        elif self.path == '/api/services':
            self.handle_add_service(data)
        elif self.path == '/api/parts':
            self.handle_add_part(data)
        elif self.path == '/api/expenses':
            self.handle_add_expense(data)
        elif self.path == '/api/time-entries':
            self.handle_add_time_entry(data)
        elif self.path.startswith('/api/time-entries/') and '/stop' in self.path:
            entry_id = self.path.split('/')[-2]
            self.handle_stop_time_entry(entry_id, data)
        else:
            self.send_error(404, 'Not Found')

    def do_PUT(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else '{}'

        try:
            data = json.loads(body) if body else {}
        except:
            data = {}

        if self.path.startswith('/api/customers/'):
            customer_id = self.path.split('/')[-1]
            self.handle_update_customer(customer_id, data)
        elif self.path.startswith('/api/vehicles/'):
            vehicle_id = self.path.split('/')[-1]
            self.handle_update_vehicle(vehicle_id, data)
        elif self.path.startswith('/api/services/'):
            service_id = self.path.split('/')[-1]
            self.handle_update_service(service_id, data)
        elif self.path.startswith('/api/parts/'):
            part_id = self.path.split('/')[-1]
            self.handle_update_part(part_id, data)
        elif self.path.startswith('/api/expenses/'):
            expense_id = self.path.split('/')[-1]
            self.handle_update_expense(expense_id, data)
        else:
            self.send_error(404, 'Not Found')

    def do_DELETE(self):
        if self.path.startswith('/api/customers/'):
            customer_id = self.path.split('/')[-1]
            self.handle_delete_customer(customer_id)
        elif self.path.startswith('/api/vehicles/'):
            vehicle_id = self.path.split('/')[-1]
            self.handle_delete_vehicle(vehicle_id)
        elif self.path.startswith('/api/services/'):
            service_id = self.path.split('/')[-1]
            self.handle_delete_service(service_id)
        elif self.path.startswith('/api/parts/'):
            part_id = self.path.split('/')[-1]
            self.handle_delete_part(part_id)
        elif self.path.startswith('/api/expenses/'):
            expense_id = self.path.split('/')[-1]
            self.handle_delete_expense(expense_id)
        elif self.path.startswith('/api/time-entries/'):
            entry_id = self.path.split('/')[-1]
            self.handle_delete_time_entry(entry_id)
        else:
            self.send_error(404, 'Not Found')

    def serve_frontend(self):
        html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Garage Management System</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        .header {
            background: white;
            padding: 20px 30px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            margin-bottom: 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .header h1 { color: #667eea; font-size: 28px; }
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: white;
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            transition: all 0.3s;
        }
        .stat-card.clickable {
            cursor: pointer;
        }
        .stat-card.clickable:hover {
            transform: translateY(-5px);
            box-shadow: 0 6px 12px rgba(0,0,0,0.15);
        }
        .stat-card h3 { color: #666; font-size: 14px; margin-bottom: 10px; }
        .stat-card .value { font-size: 36px; font-weight: bold; color: #667eea; }
        .stat-card small { display: block; margin-top: 5px; font-size: 11px; }
        .content {
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 30px;
            border-bottom: 2px solid #eee;
        }
        .tab {
            padding: 12px 24px;
            background: none;
            border: none;
            cursor: pointer;
            font-size: 16px;
            color: #666;
            border-bottom: 3px solid transparent;
            transition: all 0.3s;
        }
        .tab.active {
            color: #667eea;
            border-bottom-color: #667eea;
        }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #eee;
        }
        th {
            background: #f8f9fa;
            font-weight: 600;
            color: #333;
        }
        tr:hover { background: #f8f9fa; }
        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.3s;
        }
        .btn-primary {
            background: #667eea;
            color: white;
        }
        .btn-primary:hover { background: #5568d3; }
        .btn-success {
            background: #27ae60;
            color: white;
        }
        .btn-danger {
            background: #e74c3c;
            color: white;
        }
        .btn-sm { padding: 6px 12px; font-size: 12px; margin: 0 2px; }
        .status-badge {
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
        }
        .status-scheduled { background: #e7f3ff; color: #004085; }
        .status-in_progress { background: #cfe2ff; color: #084298; }
        .status-awaiting_parts { background: #fff3cd; color: #856404; }
        .status-quality_check { background: #d1ecf1; color: #0c5460; }
        .status-ready_for_pickup { background: #d4edda; color: #155724; }
        .status-completed_paid { background: #d1e7dd; color: #0f5132; }
        .payment-paid { background: #d1e7dd; color: #0f5132; }
        .payment-unpaid { background: #f8d7da; color: #721c24; }
        .payment-partial { background: #fff3cd; color: #856404; }
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.5);
            justify-content: center;
            align-items: center;
            z-index: 1000;
        }
        .modal.active { display: flex; }
        .modal-content {
            background: white;
            padding: 30px;
            border-radius: 10px;
            max-width: 500px;
            width: 90%;
            max-height: 90vh;
            overflow-y: auto;
        }
        .modal-content h2 { margin-bottom: 20px; color: #667eea; }
        .form-group {
            margin-bottom: 15px;
        }
        .form-group label {
            display: block;
            margin-bottom: 5px;
            font-weight: 600;
            color: #333;
        }
        .form-group input,
        .form-group select,
        .form-group textarea {
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-size: 14px;
        }
        .form-group textarea { min-height: 100px; }
        .form-actions {
            display: flex;
            gap: 10px;
            justify-content: flex-end;
            margin-top: 20px;
        }
        .login-container {
            max-width: 400px;
            margin: 100px auto;
            background: white;
            padding: 40px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .login-container h2 {
            color: #667eea;
            margin-bottom: 30px;
            text-align: center;
        }
        .hidden { display: none !important; }
    </style>
</head>
<body>
    <div id="loginView" class="login-container">
        <h2>🔧 Garage Management System</h2>
        <form id="loginForm">
            <div class="form-group">
                <label>Username</label>
                <input type="text" id="username" value="admin" required>
            </div>
            <div class="form-group">
                <label>Password</label>
                <input type="password" id="password" value="admin123" required>
            </div>
            <button type="submit" class="btn btn-primary" style="width: 100%">Login</button>
        </form>
    </div>

    <div id="mainView" class="container hidden">
        <div class="header">
            <h1>🔧 Garage Management System</h1>
            <button class="btn btn-danger" onclick="logout()">Logout</button>
        </div>

        <div class="stats" id="stats"></div>

        <div class="content">
            <div class="tabs">
                <button class="tab active" onclick="showTab('customers')">Customers</button>
                <button class="tab" onclick="showTab('vehicles')">Vehicles</button>
                <button class="tab" onclick="showTab('services')">Services</button>
                <button class="tab" onclick="showTab('parts')">Parts Inventory</button>
                <button class="tab" onclick="showTab('expenses')">Expenses</button>
                <button class="tab" onclick="showTab('financial')">Financial Summary</button>
            </div>

            <div id="customersTab" class="tab-content active">
                <button class="btn btn-primary" onclick="showAddCustomer()">+ Add Customer</button>
                <table>
                    <thead>
                        <tr>
                            <th>Name</th>
                            <th>Email</th>
                            <th>Phone</th>
                            <th>Address</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody id="customersTable"></tbody>
                </table>
            </div>

            <div id="vehiclesTab" class="tab-content">
                <button class="btn btn-primary" onclick="showAddVehicle()">+ Add Vehicle</button>
                <table>
                    <thead>
                        <tr>
                            <th>Owner</th>
                            <th>Make/Model</th>
                            <th>Year</th>
                            <th>License Plate</th>
                            <th>Color</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody id="vehiclesTable"></tbody>
                </table>
            </div>

            <div id="servicesTab" class="tab-content">
                <button class="btn btn-primary" onclick="showAddService()">+ Add Service</button>
                <button class="btn" onclick="clearServiceFilter()" style="margin-left: 10px;">Clear Filter</button>
                <table>
                    <thead>
                        <tr>
                            <th>Vehicle</th>
                            <th>Service Type</th>
                            <th>Labor Cost</th>
                            <th>Parts Cost</th>
                            <th>Total</th>
                            <th>Status</th>
                            <th>Payment</th>
                            <th>Technician</th>
                            <th>Date</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody id="servicesTable"></tbody>
                </table>
            </div>

            <div id="partsTab" class="tab-content">
                <button class="btn btn-primary" onclick="showAddPart()">+ Add Part</button>
                <table>
                    <thead>
                        <tr>
                            <th>Part Number</th>
                            <th>Name</th>
                            <th>Quantity</th>
                            <th>Unit Cost</th>
                            <th>Reorder Level</th>
                            <th>Supplier</th>
                            <th>Status</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody id="partsTable"></tbody>
                </table>
            </div>

            <div id="expensesTab" class="tab-content">
                <button class="btn btn-primary" onclick="showAddExpense()">+ Add Expense</button>
                <table>
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>Category</th>
                            <th>Description</th>
                            <th>Amount</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody id="expensesTable"></tbody>
                </table>
            </div>

            <div id="financialTab" class="tab-content">
                <h2 style="margin-bottom: 20px;">Financial Summary</h2>
                <div id="financialSummary" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px;"></div>
                <div id="financialCharts"></div>
            </div>
        </div>
    </div>

    <div id="modal" class="modal">
        <div class="modal-content" id="modalContent"></div>
    </div>

    <script>
        let token = localStorage.getItem('token');
        let customers = [];
        let vehicles = [];
        let services = [];
        let parts = [];
        let expenses = [];
        let financialData = null;

        function showTab(tab) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            event.target.classList.add('active');
            document.getElementById(tab + 'Tab').classList.add('active');
        }

        async function api(url, options = {}) {
            const headers = { 'Content-Type': 'application/json' };
            if (token) headers['Authorization'] = token;
            const response = await fetch(url, { ...options, headers });
            if (response.status === 401) {
                logout();
                return null;
            }
            return response.json();
        }

        document.getElementById('loginForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;
            const result = await api('/api/login', {
                method: 'POST',
                body: JSON.stringify({ username, password })
            });
            if (result && result.success) {
                token = result.token;
                localStorage.setItem('token', token);
                document.getElementById('loginView').classList.add('hidden');
                document.getElementById('mainView').classList.remove('hidden');
                loadData();
            } else {
                alert('Login failed');
            }
        });

        function logout() {
            localStorage.removeItem('token');
            location.reload();
        }

        async function loadData() {
            const [statsData, customersData, vehiclesData, servicesData, partsData, expensesData, financialSummary] = await Promise.all([
                api('/api/stats'),
                api('/api/customers'),
                api('/api/vehicles'),
                api('/api/services'),
                api('/api/parts'),
                api('/api/expenses'),
                api('/api/financial-summary')
            ]);

            if (statsData) renderStats(statsData);
            if (customersData) {
                customers = customersData;
                renderCustomers();
            }
            if (vehiclesData) {
                vehicles = vehiclesData;
                renderVehicles();
            }
            if (servicesData) {
                services = servicesData;
                renderServices();
            }
            if (partsData) {
                parts = partsData;
                renderParts();
            }
            if (expensesData) {
                expenses = expensesData;
                renderExpenses();
            }
            if (financialSummary) {
                financialData = financialSummary;
                renderFinancialSummary();
            }
        }

        function renderStats(stats) {
            document.getElementById('stats').innerHTML = `
                <div class="stat-card clickable" onclick="showTab('customers')" title="Click to view customers">
                    <h3>Total Customers</h3>
                    <div class="value">${stats.total_customers}</div>
                </div>
                <div class="stat-card clickable" onclick="showTab('vehicles')" title="Click to view vehicles">
                    <h3>Total Vehicles</h3>
                    <div class="value">${stats.total_vehicles}</div>
                </div>
                <div class="stat-card clickable" onclick="filterServices('pending')" title="Click to view pending services">
                    <h3>Pending Services</h3>
                    <div class="value">${stats.pending_services}</div>
                </div>
                <div class="stat-card clickable" onclick="filterServices('ready_for_pickup')" title="Click to view ready for pickup">
                    <h3>Ready for Pickup</h3>
                    <div class="value">${stats.ready_for_pickup || 0}</div>
                </div>
                <div class="stat-card clickable" onclick="showTab('financial')" title="Click to view financial details">
                    <h3>Total Revenue</h3>
                    <div class="value">$${stats.total_revenue.toFixed(2)}</div>
                    <small style="color: #666;">Labor: $${(stats.labor_revenue || 0).toFixed(2)} | Parts: $${(stats.parts_revenue || 0).toFixed(2)}</small>
                </div>
                <div class="stat-card" style="background: ${(stats.outstanding_amount || 0) > 0 ? '#fff3cd' : 'white'}">
                    <h3>Outstanding Payments</h3>
                    <div class="value" style="color: ${(stats.outstanding_amount || 0) > 0 ? '#856404' : '#27ae60'}">$${(stats.outstanding_amount || 0).toFixed(2)}</div>
                </div>
                <div class="stat-card clickable" onclick="showTab('parts')" style="background: ${(stats.low_stock_parts || 0) > 0 ? '#f8d7da' : 'white'}" title="Click to view parts inventory">
                    <h3>Low Stock Parts</h3>
                    <div class="value" style="color: ${(stats.low_stock_parts || 0) > 0 ? '#842029' : '#27ae60'}">${stats.low_stock_parts || 0}</div>
                </div>
            `;
        }

        function filterServices(status) {
            showTab('services');
            currentFilter = status;
            renderServices();
        }

        let currentFilter = null;

        function renderCustomers() {
            document.getElementById('customersTable').innerHTML = customers.map(c => `
                <tr>
                    <td>${c.name}</td>
                    <td>${c.email}</td>
                    <td>${c.phone}</td>
                    <td>${c.address || 'N/A'}</td>
                    <td>
                        <button class="btn btn-sm btn-primary" onclick="editCustomer(${c.id})">Edit</button>
                        <button class="btn btn-sm btn-danger" onclick="deleteCustomer(${c.id})">Delete</button>
                    </td>
                </tr>
            `).join('');
        }

        function renderVehicles() {
            document.getElementById('vehiclesTable').innerHTML = vehicles.map(v => `
                <tr>
                    <td>${v.owner_name}</td>
                    <td>${v.make} ${v.model}</td>
                    <td>${v.year}</td>
                    <td>${v.license_plate}</td>
                    <td>${v.color || 'N/A'}</td>
                    <td>
                        <button class="btn btn-sm btn-primary" onclick="editVehicle(${v.id})">Edit</button>
                        <button class="btn btn-sm btn-danger" onclick="deleteVehicle(${v.id})">Delete</button>
                    </td>
                </tr>
            `).join('');
        }

        function renderServices() {
            let filteredServices = services;
            if (currentFilter) {
                if (currentFilter === 'pending') {
                    filteredServices = services.filter(s => ['scheduled', 'in_progress', 'awaiting_parts', 'quality_check'].includes(s.status));
                } else {
                    filteredServices = services.filter(s => s.status === currentFilter);
                }
            }

            document.getElementById('servicesTable').innerHTML = filteredServices.map(s => `
                <tr>
                    <td>${s.vehicle_info}</td>
                    <td>${s.service_type}</td>
                    <td>$${(s.labor_cost || 0).toFixed(2)}</td>
                    <td>$${(s.parts_cost || 0).toFixed(2)}</td>
                    <td><strong>$${(s.total_cost || 0).toFixed(2)}</strong></td>
                    <td><span class="status-badge status-${s.status}">${s.status.replace(/_/g, ' ')}</span></td>
                    <td><span class="status-badge payment-${s.payment_status}">${s.payment_status}</span></td>
                    <td>${s.technician || 'Unassigned'}</td>
                    <td>${new Date(s.service_date).toLocaleDateString()}</td>
                    <td>
                        <button class="btn btn-sm btn-primary" onclick="editService(${s.id})">Edit</button>
                        <button class="btn btn-sm btn-success" onclick="viewInvoice(${s.id})">Invoice</button>
                        <button class="btn btn-sm btn-danger" onclick="deleteService(${s.id})">Delete</button>
                    </td>
                </tr>
            `).join('');
        }

        function clearServiceFilter() {
            currentFilter = null;
            renderServices();
        }

        function showAddCustomer() {
            document.getElementById('modalContent').innerHTML = `
                <h2>Add Customer</h2>
                <form id="customerForm">
                    <div class="form-group">
                        <label>Name *</label>
                        <input type="text" name="name" required>
                    </div>
                    <div class="form-group">
                        <label>Email *</label>
                        <input type="email" name="email" required>
                    </div>
                    <div class="form-group">
                        <label>Phone *</label>
                        <input type="tel" name="phone" required>
                    </div>
                    <div class="form-group">
                        <label>Address</label>
                        <input type="text" name="address">
                    </div>
                    <div class="form-actions">
                        <button type="button" class="btn" onclick="closeModal()">Cancel</button>
                        <button type="submit" class="btn btn-primary">Add Customer</button>
                    </div>
                </form>
            `;
            document.getElementById('customerForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const formData = new FormData(e.target);
                const data = Object.fromEntries(formData);
                const result = await api('/api/customers', {
                    method: 'POST',
                    body: JSON.stringify(data)
                });
                if (result && result.success) {
                    closeModal();
                    loadData();
                }
            });
            document.getElementById('modal').classList.add('active');
        }

        function showAddVehicle() {
            document.getElementById('modalContent').innerHTML = `
                <h2>Add Vehicle</h2>
                <form id="vehicleForm">
                    <div class="form-group">
                        <label>Customer *</label>
                        <select name="customer_id" required>
                            <option value="">Select Customer</option>
                            ${customers.map(c => `<option value="${c.id}">${c.name}</option>`).join('')}
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Make *</label>
                        <input type="text" name="make" required>
                    </div>
                    <div class="form-group">
                        <label>Model *</label>
                        <input type="text" name="model" required>
                    </div>
                    <div class="form-group">
                        <label>Year *</label>
                        <input type="number" name="year" required min="1900" max="2100">
                    </div>
                    <div class="form-group">
                        <label>License Plate *</label>
                        <input type="text" name="license_plate" required>
                    </div>
                    <div class="form-group">
                        <label>VIN</label>
                        <input type="text" name="vin">
                    </div>
                    <div class="form-group">
                        <label>Color</label>
                        <input type="text" name="color">
                    </div>
                    <div class="form-actions">
                        <button type="button" class="btn" onclick="closeModal()">Cancel</button>
                        <button type="submit" class="btn btn-primary">Add Vehicle</button>
                    </div>
                </form>
            `;
            document.getElementById('vehicleForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const formData = new FormData(e.target);
                const data = Object.fromEntries(formData);
                const result = await api('/api/vehicles', {
                    method: 'POST',
                    body: JSON.stringify(data)
                });
                if (result && result.success) {
                    closeModal();
                    loadData();
                }
            });
            document.getElementById('modal').classList.add('active');
        }

        function showAddService() {
            document.getElementById('modalContent').innerHTML = `
                <h2>Add Service</h2>
                <form id="serviceForm">
                    <div class="form-group">
                        <label>Vehicle *</label>
                        <select name="vehicle_id" required>
                            <option value="">Select Vehicle</option>
                            ${vehicles.map(v => `<option value="${v.id}">${v.owner_name} - ${v.make} ${v.model} (${v.license_plate})</option>`).join('')}
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Service Type *</label>
                        <input type="text" name="service_type" required>
                    </div>
                    <div class="form-group">
                        <label>Description</label>
                        <textarea name="description"></textarea>
                    </div>
                    <div class="form-group">
                        <label>Labor Cost *</label>
                        <input type="number" name="labor_cost" step="0.01" value="0" required>
                    </div>
                    <div class="form-group">
                        <label>Parts Cost *</label>
                        <input type="number" name="parts_cost" step="0.01" value="0" required>
                    </div>
                    <div class="form-group">
                        <label>Labor Hours</label>
                        <input type="number" name="labor_hours" step="0.1" value="0">
                    </div>
                    <div class="form-group">
                        <label>Status *</label>
                        <select name="status" required>
                            <option value="scheduled">Scheduled</option>
                            <option value="in_progress">In Progress</option>
                            <option value="awaiting_parts">Awaiting Parts</option>
                            <option value="quality_check">Quality Check</option>
                            <option value="ready_for_pickup">Ready for Pickup</option>
                            <option value="completed_paid">Completed & Paid</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Payment Status *</label>
                        <select name="payment_status" required>
                            <option value="unpaid">Unpaid</option>
                            <option value="partial">Partial</option>
                            <option value="paid">Paid</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Technician</label>
                        <input type="text" name="technician">
                    </div>
                    <div class="form-group">
                        <label>Notes</label>
                        <textarea name="notes"></textarea>
                    </div>
                    <div class="form-actions">
                        <button type="button" class="btn" onclick="closeModal()">Cancel</button>
                        <button type="submit" class="btn btn-primary">Add Service</button>
                    </div>
                </form>
            `;
            document.getElementById('serviceForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const formData = new FormData(e.target);
                const data = Object.fromEntries(formData);
                const result = await api('/api/services', {
                    method: 'POST',
                    body: JSON.stringify(data)
                });
                if (result && result.success) {
                    closeModal();
                    loadData();
                }
            });
            document.getElementById('modal').classList.add('active');
        }

        async function deleteCustomer(id) {
            if (confirm('Delete this customer and all associated vehicles/services?')) {
                await api(`/api/customers/${id}`, { method: 'DELETE' });
                loadData();
            }
        }

        async function deleteVehicle(id) {
            if (confirm('Delete this vehicle and all associated services?')) {
                await api(`/api/vehicles/${id}`, { method: 'DELETE' });
                loadData();
            }
        }

        async function deleteService(id) {
            if (confirm('Delete this service?')) {
                await api(`/api/services/${id}`, { method: 'DELETE' });
                loadData();
            }
        }

        // Edit functions
        function editCustomer(id) {
            const customer = customers.find(c => c.id === id);
            if (!customer) return;

            document.getElementById('modalContent').innerHTML = `
                <h2>Edit Customer</h2>
                <form id="customerForm">
                    <div class="form-group">
                        <label>Name *</label>
                        <input type="text" name="name" value="${customer.name}" required>
                    </div>
                    <div class="form-group">
                        <label>Email *</label>
                        <input type="email" name="email" value="${customer.email}" required>
                    </div>
                    <div class="form-group">
                        <label>Phone *</label>
                        <input type="tel" name="phone" value="${customer.phone}" required>
                    </div>
                    <div class="form-group">
                        <label>Address</label>
                        <input type="text" name="address" value="${customer.address || ''}">
                    </div>
                    <div class="form-actions">
                        <button type="button" class="btn" onclick="closeModal()">Cancel</button>
                        <button type="submit" class="btn btn-primary">Update Customer</button>
                    </div>
                </form>
            `;
            document.getElementById('customerForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const formData = new FormData(e.target);
                const data = Object.fromEntries(formData);
                const result = await api(`/api/customers/${id}`, {
                    method: 'PUT',
                    body: JSON.stringify(data)
                });
                if (result && result.success) {
                    closeModal();
                    loadData();
                }
            });
            document.getElementById('modal').classList.add('active');
        }

        function editVehicle(id) {
            const vehicle = vehicles.find(v => v.id === id);
            if (!vehicle) return;

            document.getElementById('modalContent').innerHTML = `
                <h2>Edit Vehicle</h2>
                <form id="vehicleForm">
                    <div class="form-group">
                        <label>Customer *</label>
                        <select name="customer_id" required>
                            ${customers.map(c => `<option value="${c.id}" ${c.id === vehicle.customer_id ? 'selected' : ''}>${c.name}</option>`).join('')}
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Make *</label>
                        <input type="text" name="make" value="${vehicle.make}" required>
                    </div>
                    <div class="form-group">
                        <label>Model *</label>
                        <input type="text" name="model" value="${vehicle.model}" required>
                    </div>
                    <div class="form-group">
                        <label>Year *</label>
                        <input type="number" name="year" value="${vehicle.year}" required>
                    </div>
                    <div class="form-group">
                        <label>License Plate *</label>
                        <input type="text" name="license_plate" value="${vehicle.license_plate}" required>
                    </div>
                    <div class="form-group">
                        <label>VIN</label>
                        <input type="text" name="vin" value="${vehicle.vin || ''}">
                    </div>
                    <div class="form-group">
                        <label>Color</label>
                        <input type="text" name="color" value="${vehicle.color || ''}">
                    </div>
                    <div class="form-actions">
                        <button type="button" class="btn" onclick="closeModal()">Cancel</button>
                        <button type="submit" class="btn btn-primary">Update Vehicle</button>
                    </div>
                </form>
            `;
            document.getElementById('vehicleForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const formData = new FormData(e.target);
                const data = Object.fromEntries(formData);
                const result = await api(`/api/vehicles/${id}`, {
                    method: 'PUT',
                    body: JSON.stringify(data)
                });
                if (result && result.success) {
                    closeModal();
                    loadData();
                }
            });
            document.getElementById('modal').classList.add('active');
        }

        function editService(id) {
            const service = services.find(s => s.id === id);
            if (!service) return;

            document.getElementById('modalContent').innerHTML = `
                <h2>Edit Service</h2>
                <form id="serviceForm">
                    <div class="form-group">
                        <label>Vehicle *</label>
                        <select name="vehicle_id" required>
                            ${vehicles.map(v => `<option value="${v.id}" ${v.id === service.vehicle_id ? 'selected' : ''}>${v.owner_name} - ${v.make} ${v.model}</option>`).join('')}
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Service Type *</label>
                        <input type="text" name="service_type" value="${service.service_type}" required>
                    </div>
                    <div class="form-group">
                        <label>Description</label>
                        <textarea name="description">${service.description || ''}</textarea>
                    </div>
                    <div class="form-group">
                        <label>Labor Cost *</label>
                        <input type="number" name="labor_cost" step="0.01" value="${service.labor_cost || 0}" required>
                    </div>
                    <div class="form-group">
                        <label>Parts Cost *</label>
                        <input type="number" name="parts_cost" step="0.01" value="${service.parts_cost || 0}" required>
                    </div>
                    <div class="form-group">
                        <label>Labor Hours</label>
                        <input type="number" name="labor_hours" step="0.1" value="${service.labor_hours || 0}">
                    </div>
                    <div class="form-group">
                        <label>Status *</label>
                        <select name="status" required>
                            <option value="scheduled" ${service.status === 'scheduled' ? 'selected' : ''}>Scheduled</option>
                            <option value="in_progress" ${service.status === 'in_progress' ? 'selected' : ''}>In Progress</option>
                            <option value="awaiting_parts" ${service.status === 'awaiting_parts' ? 'selected' : ''}>Awaiting Parts</option>
                            <option value="quality_check" ${service.status === 'quality_check' ? 'selected' : ''}>Quality Check</option>
                            <option value="ready_for_pickup" ${service.status === 'ready_for_pickup' ? 'selected' : ''}>Ready for Pickup</option>
                            <option value="completed_paid" ${service.status === 'completed_paid' ? 'selected' : ''}>Completed & Paid</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Payment Status *</label>
                        <select name="payment_status" required>
                            <option value="unpaid" ${service.payment_status === 'unpaid' ? 'selected' : ''}>Unpaid</option>
                            <option value="partial" ${service.payment_status === 'partial' ? 'selected' : ''}>Partial</option>
                            <option value="paid" ${service.payment_status === 'paid' ? 'selected' : ''}>Paid</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Technician</label>
                        <input type="text" name="technician" value="${service.technician || ''}">
                    </div>
                    <div class="form-group">
                        <label>Notes</label>
                        <textarea name="notes">${service.notes || ''}</textarea>
                    </div>
                    <div class="form-actions">
                        <button type="button" class="btn" onclick="closeModal()">Cancel</button>
                        <button type="submit" class="btn btn-primary">Update Service</button>
                    </div>
                </form>
            `;
            document.getElementById('serviceForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const formData = new FormData(e.target);
                const data = Object.fromEntries(formData);
                const result = await api(`/api/services/${id}`, {
                    method: 'PUT',
                    body: JSON.stringify(data)
                });
                if (result && result.success) {
                    closeModal();
                    loadData();
                }
            });
            document.getElementById('modal').classList.add('active');
        }

        // Parts management functions
        function renderParts() {
            document.getElementById('partsTable').innerHTML = parts.map(p => `
                <tr style="${p.low_stock ? 'background: #fff3cd;' : ''}">
                    <td>${p.part_number}</td>
                    <td>${p.name}</td>
                    <td>${p.quantity}</td>
                    <td>$${p.unit_cost.toFixed(2)}</td>
                    <td>${p.reorder_level}</td>
                    <td>${p.supplier || 'N/A'}</td>
                    <td>${p.low_stock ? '<span class="status-badge" style="background: #f8d7da; color: #721c24;">Low Stock</span>' : '<span class="status-badge" style="background: #d1e7dd; color: #0f5132;">In Stock</span>'}</td>
                    <td>
                        <button class="btn btn-sm btn-primary" onclick="editPart(${p.id})">Edit</button>
                        <button class="btn btn-sm btn-danger" onclick="deletePart(${p.id})">Delete</button>
                    </td>
                </tr>
            `).join('');
        }

        function showAddPart() {
            document.getElementById('modalContent').innerHTML = `
                <h2>Add Part</h2>
                <form id="partForm">
                    <div class="form-group">
                        <label>Part Number *</label>
                        <input type="text" name="part_number" required>
                    </div>
                    <div class="form-group">
                        <label>Name *</label>
                        <input type="text" name="name" required>
                    </div>
                    <div class="form-group">
                        <label>Description</label>
                        <textarea name="description"></textarea>
                    </div>
                    <div class="form-group">
                        <label>Quantity *</label>
                        <input type="number" name="quantity" value="0" required>
                    </div>
                    <div class="form-group">
                        <label>Unit Cost *</label>
                        <input type="number" name="unit_cost" step="0.01" required>
                    </div>
                    <div class="form-group">
                        <label>Reorder Level *</label>
                        <input type="number" name="reorder_level" value="10" required>
                    </div>
                    <div class="form-group">
                        <label>Supplier</label>
                        <input type="text" name="supplier">
                    </div>
                    <div class="form-actions">
                        <button type="button" class="btn" onclick="closeModal()">Cancel</button>
                        <button type="submit" class="btn btn-primary">Add Part</button>
                    </div>
                </form>
            `;
            document.getElementById('partForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const formData = new FormData(e.target);
                const data = Object.fromEntries(formData);
                const result = await api('/api/parts', {
                    method: 'POST',
                    body: JSON.stringify(data)
                });
                if (result && result.success) {
                    closeModal();
                    loadData();
                }
            });
            document.getElementById('modal').classList.add('active');
        }

        function editPart(id) {
            const part = parts.find(p => p.id === id);
            if (!part) return;

            document.getElementById('modalContent').innerHTML = `
                <h2>Edit Part</h2>
                <form id="partForm">
                    <div class="form-group">
                        <label>Part Number *</label>
                        <input type="text" name="part_number" value="${part.part_number}" required>
                    </div>
                    <div class="form-group">
                        <label>Name *</label>
                        <input type="text" name="name" value="${part.name}" required>
                    </div>
                    <div class="form-group">
                        <label>Description</label>
                        <textarea name="description">${part.description || ''}</textarea>
                    </div>
                    <div class="form-group">
                        <label>Quantity *</label>
                        <input type="number" name="quantity" value="${part.quantity}" required>
                    </div>
                    <div class="form-group">
                        <label>Unit Cost *</label>
                        <input type="number" name="unit_cost" step="0.01" value="${part.unit_cost}" required>
                    </div>
                    <div class="form-group">
                        <label>Reorder Level *</label>
                        <input type="number" name="reorder_level" value="${part.reorder_level}" required>
                    </div>
                    <div class="form-group">
                        <label>Supplier</label>
                        <input type="text" name="supplier" value="${part.supplier || ''}">
                    </div>
                    <div class="form-actions">
                        <button type="button" class="btn" onclick="closeModal()">Cancel</button>
                        <button type="submit" class="btn btn-primary">Update Part</button>
                    </div>
                </form>
            `;
            document.getElementById('partForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const formData = new FormData(e.target);
                const data = Object.fromEntries(formData);
                const result = await api(`/api/parts/${id}`, {
                    method: 'PUT',
                    body: JSON.stringify(data)
                });
                if (result && result.success) {
                    closeModal();
                    loadData();
                }
            });
            document.getElementById('modal').classList.add('active');
        }

        async function deletePart(id) {
            if (confirm('Delete this part?')) {
                await api(`/api/parts/${id}`, { method: 'DELETE' });
                loadData();
            }
        }

        // Expenses management functions
        function renderExpenses() {
            document.getElementById('expensesTable').innerHTML = expenses.map(e => `
                <tr>
                    <td>${new Date(e.expense_date).toLocaleDateString()}</td>
                    <td>${e.category}</td>
                    <td>${e.description}</td>
                    <td>$${e.amount.toFixed(2)}</td>
                    <td>
                        <button class="btn btn-sm btn-primary" onclick="editExpense(${e.id})">Edit</button>
                        <button class="btn btn-sm btn-danger" onclick="deleteExpense(${e.id})">Delete</button>
                    </td>
                </tr>
            `).join('');
        }

        function showAddExpense() {
            document.getElementById('modalContent').innerHTML = `
                <h2>Add Expense</h2>
                <form id="expenseForm">
                    <div class="form-group">
                        <label>Category *</label>
                        <select name="category" required>
                            <option value="">Select Category</option>
                            <option value="Rent">Rent</option>
                            <option value="Utilities">Utilities</option>
                            <option value="Salaries">Salaries</option>
                            <option value="Equipment">Equipment</option>
                            <option value="Parts Purchase">Parts Purchase</option>
                            <option value="Marketing">Marketing</option>
                            <option value="Insurance">Insurance</option>
                            <option value="Other">Other</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Description *</label>
                        <input type="text" name="description" required>
                    </div>
                    <div class="form-group">
                        <label>Amount *</label>
                        <input type="number" name="amount" step="0.01" required>
                    </div>
                    <div class="form-group">
                        <label>Notes</label>
                        <textarea name="notes"></textarea>
                    </div>
                    <div class="form-actions">
                        <button type="button" class="btn" onclick="closeModal()">Cancel</button>
                        <button type="submit" class="btn btn-primary">Add Expense</button>
                    </div>
                </form>
            `;
            document.getElementById('expenseForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const formData = new FormData(e.target);
                const data = Object.fromEntries(formData);
                const result = await api('/api/expenses', {
                    method: 'POST',
                    body: JSON.stringify(data)
                });
                if (result && result.success) {
                    closeModal();
                    loadData();
                }
            });
            document.getElementById('modal').classList.add('active');
        }

        function editExpense(id) {
            const expense = expenses.find(e => e.id === id);
            if (!expense) return;

            document.getElementById('modalContent').innerHTML = `
                <h2>Edit Expense</h2>
                <form id="expenseForm">
                    <div class="form-group">
                        <label>Category *</label>
                        <select name="category" required>
                            <option value="Rent" ${expense.category === 'Rent' ? 'selected' : ''}>Rent</option>
                            <option value="Utilities" ${expense.category === 'Utilities' ? 'selected' : ''}>Utilities</option>
                            <option value="Salaries" ${expense.category === 'Salaries' ? 'selected' : ''}>Salaries</option>
                            <option value="Equipment" ${expense.category === 'Equipment' ? 'selected' : ''}>Equipment</option>
                            <option value="Parts Purchase" ${expense.category === 'Parts Purchase' ? 'selected' : ''}>Parts Purchase</option>
                            <option value="Marketing" ${expense.category === 'Marketing' ? 'selected' : ''}>Marketing</option>
                            <option value="Insurance" ${expense.category === 'Insurance' ? 'selected' : ''}>Insurance</option>
                            <option value="Other" ${expense.category === 'Other' ? 'selected' : ''}>Other</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Description *</label>
                        <input type="text" name="description" value="${expense.description}" required>
                    </div>
                    <div class="form-group">
                        <label>Amount *</label>
                        <input type="number" name="amount" step="0.01" value="${expense.amount}" required>
                    </div>
                    <div class="form-group">
                        <label>Notes</label>
                        <textarea name="notes">${expense.notes || ''}</textarea>
                    </div>
                    <div class="form-actions">
                        <button type="button" class="btn" onclick="closeModal()">Cancel</button>
                        <button type="submit" class="btn btn-primary">Update Expense</button>
                    </div>
                </form>
            `;
            document.getElementById('expenseForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const formData = new FormData(e.target);
                const data = Object.fromEntries(formData);
                const result = await api(`/api/expenses/${id}`, {
                    method: 'PUT',
                    body: JSON.stringify(data)
                });
                if (result && result.success) {
                    closeModal();
                    loadData();
                }
            });
            document.getElementById('modal').classList.add('active');
        }

        async function deleteExpense(id) {
            if (confirm('Delete this expense?')) {
                await api(`/api/expenses/${id}`, { method: 'DELETE' });
                loadData();
            }
        }

        // Financial summary function
        function renderFinancialSummary() {
            if (!financialData) return;

            document.getElementById('financialSummary').innerHTML = `
                <div class="stat-card">
                    <h3>Total Revenue</h3>
                    <div class="value" style="color: #27ae60;">$${financialData.total_revenue.toFixed(2)}</div>
                    <small>Labor: $${financialData.labor_revenue.toFixed(2)}</small>
                    <small>Parts: $${financialData.parts_revenue.toFixed(2)}</small>
                </div>
                <div class="stat-card">
                    <h3>Total Expenses</h3>
                    <div class="value" style="color: #e74c3c;">$${financialData.total_expenses.toFixed(2)}</div>
                </div>
                <div class="stat-card" style="background: ${financialData.profit >= 0 ? '#d1e7dd' : '#f8d7da'}">
                    <h3>${financialData.profit >= 0 ? 'Profit' : 'Loss'}</h3>
                    <div class="value" style="color: ${financialData.profit >= 0 ? '#0f5132' : '#721c24'};">$${Math.abs(financialData.profit).toFixed(2)}</div>
                </div>
                <div class="stat-card">
                    <h3>Outstanding Payments</h3>
                    <div class="value" style="color: #856404;">$${financialData.outstanding_payments.toFixed(2)}</div>
                </div>
            `;

            // Render monthly revenue chart (simple text for now)
            let chartHTML = '<h3>Monthly Revenue (Last 6 Months)</h3><table style="width: 100%; margin-top: 20px;"><thead><tr><th>Month</th><th>Revenue</th></tr></thead><tbody>';
            financialData.monthly_revenue.forEach(m => {
                chartHTML += `<tr><td>${m.month}</td><td>$${m.revenue.toFixed(2)}</td></tr>`;
            });
            chartHTML += '</tbody></table>';
            document.getElementById('financialCharts').innerHTML = chartHTML;
        }

        // Invoice viewing function
        async function viewInvoice(serviceId) {
            const invoiceData = await api(`/api/services/${serviceId}/invoice`);
            if (!invoiceData) return;

            document.getElementById('modalContent').innerHTML = `
                <div style="max-width: 800px;">
                    <h2>Invoice ${invoiceData.invoice_number}</h2>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 20px 0; border-bottom: 2px solid #667eea; padding-bottom: 20px;">
                        <div>
                            <h3>Customer Information</h3>
                            <p><strong>${invoiceData.customer.name}</strong></p>
                            <p>${invoiceData.customer.email}</p>
                            <p>${invoiceData.customer.phone}</p>
                            <p>${invoiceData.customer.address || ''}</p>
                        </div>
                        <div>
                            <h3>Vehicle Information</h3>
                            <p><strong>${invoiceData.vehicle.year} ${invoiceData.vehicle.make} ${invoiceData.vehicle.model}</strong></p>
                            <p>License: ${invoiceData.vehicle.license_plate}</p>
                        </div>
                    </div>
                    <h3>Service Details</h3>
                    <p><strong>Service Type:</strong> ${invoiceData.service_type}</p>
                    <p><strong>Description:</strong> ${invoiceData.description || 'N/A'}</p>
                    <p><strong>Date:</strong> ${new Date(invoiceData.service_date).toLocaleDateString()}</p>
                    <p><strong>Technician:</strong> ${invoiceData.technician || 'N/A'}</p>

                    <table style="width: 100%; margin-top: 20px; border-collapse: collapse;">
                        <thead>
                            <tr style="background: #f8f9fa;">
                                <th style="text-align: left; padding: 10px;">Item</th>
                                <th style="text-align: right; padding: 10px;">Amount</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td style="padding: 10px;">Labor</td>
                                <td style="text-align: right; padding: 10px;">$${invoiceData.labor_cost.toFixed(2)}</td>
                            </tr>
                            <tr>
                                <td style="padding: 10px;">Parts</td>
                                <td style="text-align: right; padding: 10px;">$${invoiceData.parts_cost.toFixed(2)}</td>
                            </tr>
                            ${invoiceData.parts.map(part => `
                                <tr>
                                    <td style="padding: 10px 10px 10px 30px; font-size: 12px;">${part.name} (x${part.quantity})</td>
                                    <td style="text-align: right; padding: 10px; font-size: 12px;">$${part.total.toFixed(2)}</td>
                                </tr>
                            `).join('')}
                            <tr style="border-top: 2px solid #667eea; font-weight: bold;">
                                <td style="padding: 10px;">Total</td>
                                <td style="text-align: right; padding: 10px;">$${invoiceData.total_cost.toFixed(2)}</td>
                            </tr>
                        </tbody>
                    </table>

                    <div style="margin-top: 20px; padding: 15px; background: ${invoiceData.payment_status === 'paid' ? '#d1e7dd' : '#fff3cd'}; border-radius: 5px;">
                        <strong>Payment Status:</strong> ${invoiceData.payment_status.toUpperCase()}
                    </div>

                    <div class="form-actions">
                        <button class="btn btn-primary" onclick="closeModal()">Close</button>
                    </div>
                </div>
            `;
            document.getElementById('modal').classList.add('active');
        }

        function closeModal() {
            document.getElementById('modal').classList.remove('active');
        }

        document.getElementById('modal').addEventListener('click', (e) => {
            if (e.target.id === 'modal') closeModal();
        });

        if (token) {
            document.getElementById('loginView').classList.add('hidden');
            document.getElementById('mainView').classList.remove('hidden');
            loadData();
        }
    </script>
</body>
</html>'''

        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(html.encode())

    def handle_login(self, data):
        username = data.get('username')
        password = data.get('password')
        password_hash = hashlib.sha256(password.encode()).hexdigest()

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM users WHERE username = ? AND password_hash = ?',
                      (username, password_hash))
        user = cursor.fetchone()
        conn.close()

        if user:
            token = create_session(user[0])
            self.send_json_response({'success': True, 'token': token})
        else:
            self.send_json_response({'success': False, 'message': 'Invalid credentials'}, 401)

    def handle_stats(self):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(*) FROM customers')
        total_customers = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM vehicles')
        total_vehicles = cursor.fetchone()[0]

        # Count services by different statuses
        cursor.execute("SELECT COUNT(*) FROM services WHERE status IN ('scheduled', 'in_progress', 'awaiting_parts', 'quality_check')")
        pending_services = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM services WHERE status = 'ready_for_pickup'")
        ready_for_pickup = cursor.fetchone()[0]

        # Revenue breakdown
        cursor.execute("SELECT SUM(labor_cost), SUM(parts_cost), SUM(total_cost) FROM services WHERE payment_status = 'paid'")
        revenue = cursor.fetchone()
        labor_revenue = revenue[0] or 0
        parts_revenue = revenue[1] or 0
        total_revenue = revenue[2] or 0

        # Unpaid invoices
        cursor.execute("SELECT SUM(total_cost) FROM services WHERE payment_status IN ('unpaid', 'partial')")
        outstanding_amount = cursor.fetchone()[0] or 0

        # Low stock parts count
        cursor.execute("SELECT COUNT(*) FROM parts WHERE quantity <= reorder_level")
        low_stock_count = cursor.fetchone()[0]

        conn.close()

        self.send_json_response({
            'total_customers': total_customers,
            'total_vehicles': total_vehicles,
            'pending_services': pending_services,
            'ready_for_pickup': ready_for_pickup,
            'total_revenue': total_revenue,
            'labor_revenue': labor_revenue,
            'parts_revenue': parts_revenue,
            'outstanding_amount': outstanding_amount,
            'low_stock_parts': low_stock_count
        })

    def handle_get_customers(self):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT id, name, email, phone, address FROM customers ORDER BY name')
        customers = [{'id': row[0], 'name': row[1], 'email': row[2], 'phone': row[3], 'address': row[4]}
                    for row in cursor.fetchall()]
        conn.close()
        self.send_json_response(customers)

    def handle_get_vehicles(self):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT v.id, v.customer_id, v.make, v.model, v.year, v.license_plate, v.vin, v.color, c.name
            FROM vehicles v
            JOIN customers c ON v.customer_id = c.id
            ORDER BY c.name, v.make
        ''')
        vehicles = [{'id': row[0], 'customer_id': row[1], 'make': row[2], 'model': row[3],
                    'year': row[4], 'license_plate': row[5], 'vin': row[6], 'color': row[7],
                    'owner_name': row[8]} for row in cursor.fetchall()]
        conn.close()
        self.send_json_response(vehicles)

    def handle_get_services(self):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT s.id, s.vehicle_id, s.service_type, s.description, s.labor_cost, s.parts_cost,
                   s.total_cost, s.status, s.service_date, s.completed_date, s.technician, s.notes,
                   s.labor_hours, s.payment_status,
                   c.name, v.make, v.model, v.license_plate
            FROM services s
            JOIN vehicles v ON s.vehicle_id = v.id
            JOIN customers c ON v.customer_id = c.id
            ORDER BY s.service_date DESC
        ''')
        services = [{
            'id': row[0], 'vehicle_id': row[1], 'service_type': row[2], 'description': row[3],
            'labor_cost': row[4], 'parts_cost': row[5], 'total_cost': row[6],
            'status': row[7], 'service_date': row[8], 'completed_date': row[9],
            'technician': row[10], 'notes': row[11], 'labor_hours': row[12],
            'payment_status': row[13],
            'vehicle_info': f"{row[14]} - {row[15]} {row[16]} ({row[17]})"
        } for row in cursor.fetchall()]
        conn.close()
        self.send_json_response(services)

    def handle_add_customer(self, data):
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('''INSERT INTO customers (name, email, phone, address) VALUES (?, ?, ?, ?)''',
                          (data['name'], data['email'], data['phone'], data.get('address', '')))
            conn.commit()
            customer_id = cursor.lastrowid
            conn.close()
            self.send_json_response({'success': True, 'id': customer_id})
        except Exception as e:
            self.send_json_response({'success': False, 'message': str(e)}, 400)

    def handle_add_vehicle(self, data):
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO vehicles (customer_id, make, model, year, license_plate, vin, color)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (data['customer_id'], data['make'], data['model'], data['year'],
                  data['license_plate'], data.get('vin', ''), data.get('color', '')))
            conn.commit()
            vehicle_id = cursor.lastrowid
            conn.close()
            self.send_json_response({'success': True, 'id': vehicle_id})
        except Exception as e:
            self.send_json_response({'success': False, 'message': str(e)}, 400)

    def handle_add_service(self, data):
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()

            labor_cost = float(data.get('labor_cost', 0))
            parts_cost = float(data.get('parts_cost', 0))
            total_cost = labor_cost + parts_cost

            cursor.execute('''
                INSERT INTO services (vehicle_id, service_type, description, labor_cost, parts_cost,
                                    total_cost, status, technician, notes, labor_hours, payment_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (data['vehicle_id'], data['service_type'], data.get('description', ''),
                  labor_cost, parts_cost, total_cost,
                  data.get('status', 'scheduled'), data.get('technician', ''),
                  data.get('notes', ''), data.get('labor_hours', 0),
                  data.get('payment_status', 'unpaid')))
            conn.commit()
            service_id = cursor.lastrowid
            conn.close()
            self.send_json_response({'success': True, 'id': service_id})
        except Exception as e:
            self.send_json_response({'success': False, 'message': str(e)}, 400)

    def handle_delete_customer(self, customer_id):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM customers WHERE id = ?', (customer_id,))
        conn.commit()
        conn.close()
        self.send_json_response({'success': True})

    def handle_delete_vehicle(self, vehicle_id):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM vehicles WHERE id = ?', (vehicle_id,))
        conn.commit()
        conn.close()
        self.send_json_response({'success': True})

    def handle_delete_service(self, service_id):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM services WHERE id = ?', (service_id,))
        conn.commit()
        conn.close()
        self.send_json_response({'success': True})

    def handle_dashboard(self):
        self.handle_stats()

    # Missing UPDATE handlers implementation
    def handle_update_customer(self, customer_id, data):
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE customers SET name = ?, email = ?, phone = ?, address = ?
                WHERE id = ?
            ''', (data['name'], data['email'], data['phone'], data.get('address', ''), customer_id))
            conn.commit()
            conn.close()
            self.send_json_response({'success': True})
        except Exception as e:
            self.send_json_response({'success': False, 'message': str(e)}, 400)

    def handle_update_vehicle(self, vehicle_id, data):
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE vehicles SET customer_id = ?, make = ?, model = ?, year = ?,
                                  license_plate = ?, vin = ?, color = ?, engine_type = ?,
                                  transmission = ?, fuel_type = ?, current_odometer = ?,
                                  oil_change_interval = ?
                WHERE id = ?
            ''', (data['customer_id'], data['make'], data['model'], data['year'],
                  data['license_plate'], data.get('vin', ''), data.get('color', ''),
                  data.get('engine_type', ''), data.get('transmission', ''),
                  data.get('fuel_type', ''), data.get('current_odometer', 0),
                  data.get('oil_change_interval', 5000), vehicle_id))
            conn.commit()
            conn.close()
            self.send_json_response({'success': True})
        except Exception as e:
            self.send_json_response({'success': False, 'message': str(e)}, 400)

    def handle_update_service(self, service_id, data):
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()

            labor_cost = float(data.get('labor_cost', 0))
            parts_cost = float(data.get('parts_cost', 0))
            total_cost = labor_cost + parts_cost

            cursor.execute('''
                UPDATE services SET vehicle_id = ?, service_type = ?, description = ?,
                                  labor_cost = ?, parts_cost = ?, total_cost = ?,
                                  status = ?, technician = ?, notes = ?, labor_hours = ?,
                                  payment_status = ?
                WHERE id = ?
            ''', (data['vehicle_id'], data['service_type'], data.get('description', ''),
                  labor_cost, parts_cost, total_cost, data.get('status', 'scheduled'),
                  data.get('technician', ''), data.get('notes', ''),
                  data.get('labor_hours', 0), data.get('payment_status', 'unpaid'), service_id))

            # Update completed_date if status is completed_paid
            if data.get('status') == 'completed_paid':
                cursor.execute('UPDATE services SET completed_date = ? WHERE id = ?',
                             (datetime.now().isoformat(), service_id))

            conn.commit()
            conn.close()
            self.send_json_response({'success': True})
        except Exception as e:
            self.send_json_response({'success': False, 'message': str(e)}, 400)

    # Parts management handlers
    def handle_get_parts(self):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''SELECT id, part_number, name, description, quantity, unit_cost,
                         reorder_level, supplier FROM parts ORDER BY name''')
        parts = [{'id': row[0], 'part_number': row[1], 'name': row[2], 'description': row[3],
                 'quantity': row[4], 'unit_cost': row[5], 'reorder_level': row[6],
                 'supplier': row[7], 'low_stock': row[4] <= row[6]} for row in cursor.fetchall()]
        conn.close()
        self.send_json_response(parts)

    def handle_add_part(self, data):
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO parts (part_number, name, description, quantity, unit_cost, reorder_level, supplier)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (data['part_number'], data['name'], data.get('description', ''),
                  data.get('quantity', 0), data['unit_cost'], data.get('reorder_level', 10),
                  data.get('supplier', '')))
            conn.commit()
            part_id = cursor.lastrowid
            conn.close()
            self.send_json_response({'success': True, 'id': part_id})
        except Exception as e:
            self.send_json_response({'success': False, 'message': str(e)}, 400)

    def handle_update_part(self, part_id, data):
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE parts SET part_number = ?, name = ?, description = ?, quantity = ?,
                               unit_cost = ?, reorder_level = ?, supplier = ?
                WHERE id = ?
            ''', (data['part_number'], data['name'], data.get('description', ''),
                  data['quantity'], data['unit_cost'], data.get('reorder_level', 10),
                  data.get('supplier', ''), part_id))
            conn.commit()
            conn.close()
            self.send_json_response({'success': True})
        except Exception as e:
            self.send_json_response({'success': False, 'message': str(e)}, 400)

    def handle_delete_part(self, part_id):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM parts WHERE id = ?', (part_id,))
        conn.commit()
        conn.close()
        self.send_json_response({'success': True})

    # Expenses management handlers
    def handle_get_expenses(self):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''SELECT id, category, description, amount, expense_date, notes
                         FROM expenses ORDER BY expense_date DESC''')
        expenses = [{'id': row[0], 'category': row[1], 'description': row[2],
                    'amount': row[3], 'expense_date': row[4], 'notes': row[5]}
                   for row in cursor.fetchall()]
        conn.close()
        self.send_json_response(expenses)

    def handle_add_expense(self, data):
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO expenses (category, description, amount, notes)
                VALUES (?, ?, ?, ?)
            ''', (data['category'], data['description'], data['amount'], data.get('notes', '')))
            conn.commit()
            expense_id = cursor.lastrowid
            conn.close()
            self.send_json_response({'success': True, 'id': expense_id})
        except Exception as e:
            self.send_json_response({'success': False, 'message': str(e)}, 400)

    def handle_update_expense(self, expense_id, data):
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE expenses SET category = ?, description = ?, amount = ?, notes = ?
                WHERE id = ?
            ''', (data['category'], data['description'], data['amount'],
                  data.get('notes', ''), expense_id))
            conn.commit()
            conn.close()
            self.send_json_response({'success': True})
        except Exception as e:
            self.send_json_response({'success': False, 'message': str(e)}, 400)

    def handle_delete_expense(self, expense_id):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM expenses WHERE id = ?', (expense_id,))
        conn.commit()
        conn.close()
        self.send_json_response({'success': True})

    # Time tracking handlers
    def handle_get_time_entries(self):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT t.id, t.service_id, t.technician, t.start_time, t.end_time,
                   t.duration_hours, t.notes, s.service_type
            FROM time_entries t
            JOIN services s ON t.service_id = s.id
            ORDER BY t.start_time DESC
        ''')
        entries = [{'id': row[0], 'service_id': row[1], 'technician': row[2],
                   'start_time': row[3], 'end_time': row[4], 'duration_hours': row[5],
                   'notes': row[6], 'service_type': row[7]} for row in cursor.fetchall()]
        conn.close()
        self.send_json_response(entries)

    def handle_add_time_entry(self, data):
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            start_time = data.get('start_time', datetime.now().isoformat())
            cursor.execute('''
                INSERT INTO time_entries (service_id, technician, start_time, notes)
                VALUES (?, ?, ?, ?)
            ''', (data['service_id'], data['technician'], start_time, data.get('notes', '')))
            conn.commit()
            entry_id = cursor.lastrowid
            conn.close()
            self.send_json_response({'success': True, 'id': entry_id})
        except Exception as e:
            self.send_json_response({'success': False, 'message': str(e)}, 400)

    def handle_stop_time_entry(self, entry_id, data):
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            end_time = datetime.now()

            # Get start time
            cursor.execute('SELECT start_time FROM time_entries WHERE id = ?', (entry_id,))
            result = cursor.fetchone()
            if result:
                start_time = datetime.fromisoformat(result[0])
                duration = (end_time - start_time).total_seconds() / 3600  # hours

                cursor.execute('''
                    UPDATE time_entries SET end_time = ?, duration_hours = ?
                    WHERE id = ?
                ''', (end_time.isoformat(), duration, entry_id))
                conn.commit()
                conn.close()
                self.send_json_response({'success': True, 'duration_hours': duration})
            else:
                conn.close()
                self.send_json_response({'success': False, 'message': 'Entry not found'}, 404)
        except Exception as e:
            self.send_json_response({'success': False, 'message': str(e)}, 400)

    def handle_delete_time_entry(self, entry_id):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM time_entries WHERE id = ?', (entry_id,))
        conn.commit()
        conn.close()
        self.send_json_response({'success': True})

    # Customer and vehicle history handlers
    def handle_customer_history(self, customer_id):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        # Get customer info
        cursor.execute('SELECT name, email, phone FROM customers WHERE id = ?', (customer_id,))
        customer = cursor.fetchone()

        # Get all vehicles for this customer
        cursor.execute('SELECT id, make, model, year, license_plate FROM vehicles WHERE customer_id = ?',
                      (customer_id,))
        vehicles = [{'id': row[0], 'make': row[1], 'model': row[2], 'year': row[3],
                    'license_plate': row[4]} for row in cursor.fetchall()]

        # Get all services for this customer's vehicles
        cursor.execute('''
            SELECT s.id, s.service_type, s.total_cost, s.service_date, s.status, v.make, v.model
            FROM services s
            JOIN vehicles v ON s.vehicle_id = v.id
            WHERE v.customer_id = ?
            ORDER BY s.service_date DESC
        ''', (customer_id,))
        services = [{'id': row[0], 'service_type': row[1], 'cost': row[2],
                    'date': row[3], 'status': row[4], 'vehicle': f"{row[5]} {row[6]}"}
                   for row in cursor.fetchall()]

        conn.close()
        self.send_json_response({
            'customer': {'name': customer[0], 'email': customer[1], 'phone': customer[2]} if customer else None,
            'vehicles': vehicles,
            'services': services
        })

    def handle_vehicle_history(self, vehicle_id):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        # Get vehicle info
        cursor.execute('''
            SELECT v.make, v.model, v.year, v.license_plate, v.current_odometer, c.name
            FROM vehicles v
            JOIN customers c ON v.customer_id = c.id
            WHERE v.id = ?
        ''', (vehicle_id,))
        vehicle_data = cursor.fetchone()

        # Get service history
        cursor.execute('''
            SELECT id, service_type, description, total_cost, service_date, status, technician
            FROM services WHERE vehicle_id = ?
            ORDER BY service_date DESC
        ''', (vehicle_id,))
        services = [{'id': row[0], 'service_type': row[1], 'description': row[2],
                    'cost': row[3], 'date': row[4], 'status': row[5], 'technician': row[6]}
                   for row in cursor.fetchall()]

        # Get odometer readings
        cursor.execute('''
            SELECT reading, reading_date FROM odometer_readings
            WHERE vehicle_id = ? ORDER BY reading_date DESC
        ''', (vehicle_id,))
        odometer_readings = [{'reading': row[0], 'date': row[1]} for row in cursor.fetchall()]

        conn.close()
        if vehicle_data:
            self.send_json_response({
                'vehicle': {
                    'make': vehicle_data[0], 'model': vehicle_data[1], 'year': vehicle_data[2],
                    'license_plate': vehicle_data[3], 'current_odometer': vehicle_data[4],
                    'owner': vehicle_data[5]
                },
                'services': services,
                'odometer_readings': odometer_readings
            })
        else:
            self.send_json_response({'error': 'Vehicle not found'}, 404)

    # Financial summary handler
    def handle_financial_summary(self):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        # Total revenue breakdown
        cursor.execute('''
            SELECT SUM(labor_cost), SUM(parts_cost), SUM(total_cost)
            FROM services WHERE payment_status = 'paid'
        ''')
        revenue = cursor.fetchone()
        labor_revenue = revenue[0] or 0
        parts_revenue = revenue[1] or 0
        total_revenue = revenue[2] or 0

        # Total expenses
        cursor.execute('SELECT SUM(amount) FROM expenses')
        total_expenses = cursor.fetchone()[0] or 0

        # Profit
        profit = total_revenue - total_expenses

        # Outstanding payments
        cursor.execute('''
            SELECT SUM(total_cost) FROM services
            WHERE payment_status IN ('unpaid', 'partial')
        ''')
        outstanding = cursor.fetchone()[0] or 0

        # Monthly breakdown (last 6 months)
        cursor.execute('''
            SELECT strftime('%Y-%m', service_date) as month,
                   SUM(total_cost) as revenue
            FROM services
            WHERE payment_status = 'paid'
              AND service_date >= date('now', '-6 months')
            GROUP BY month
            ORDER BY month DESC
        ''')
        monthly_revenue = [{'month': row[0], 'revenue': row[1]} for row in cursor.fetchall()]

        conn.close()
        self.send_json_response({
            'labor_revenue': labor_revenue,
            'parts_revenue': parts_revenue,
            'total_revenue': total_revenue,
            'total_expenses': total_expenses,
            'profit': profit,
            'outstanding_payments': outstanding,
            'monthly_revenue': monthly_revenue
        })

    # Invoice generation handler
    def handle_generate_invoice(self, service_id):
        try:
            service_id = int(service_id)
        except ValueError:
            self.send_json_response({'error': 'Invalid service ID'}, 400)
            return

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        # Get service details with customer and vehicle info
        cursor.execute('''
            SELECT s.id, s.service_type, s.description, s.labor_cost, s.parts_cost,
                   s.total_cost, s.service_date, s.technician, s.payment_status,
                   c.name, c.email, c.phone, c.address,
                   v.make, v.model, v.year, v.license_plate
            FROM services s
            JOIN vehicles v ON s.vehicle_id = v.id
            JOIN customers c ON v.customer_id = c.id
            WHERE s.id = ?
        ''', (service_id,))

        service = cursor.fetchone()
        if not service:
            conn.close()
            self.send_json_response({'error': 'Service not found'}, 404)
            return

        # Get parts used for this service
        cursor.execute('''
            SELECT p.name, sp.quantity, sp.unit_price, (sp.quantity * sp.unit_price) as total
            FROM service_parts sp
            JOIN parts p ON sp.part_id = p.id
            WHERE sp.service_id = ?
        ''', (service_id,))
        parts = [{'name': row[0], 'quantity': row[1], 'unit_price': row[2], 'total': row[3]}
                for row in cursor.fetchall()]

        conn.close()

        invoice_data = {
            'invoice_number': f"INV-{service_id:05d}",
            'service_id': service[0],
            'service_type': service[1],
            'description': service[2],
            'labor_cost': service[3],
            'parts_cost': service[4],
            'total_cost': service[5],
            'service_date': service[6],
            'technician': service[7],
            'payment_status': service[8],
            'customer': {
                'name': service[9],
                'email': service[10],
                'phone': service[11],
                'address': service[12]
            },
            'vehicle': {
                'make': service[13],
                'model': service[14],
                'year': service[15],
                'license_plate': service[16]
            },
            'parts': parts
        }

        self.send_json_response(invoice_data)

    def send_json_response(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, format, *args):
        # Simplified logging
        return

if __name__ == '__main__':
    print("=" * 60)
    print("🔧 GARAGE MANAGEMENT SYSTEM")
    print("=" * 60)
    print(f"\n📊 Initializing database...")
    init_database()
    print(f"\n🚀 Starting server on http://localhost:{PORT}")
    print(f"\n🔐 Default Login:")
    print(f"   Username: admin")
    print(f"   Password: admin123")
    print(f"\n🌐 Open your browser and navigate to:")
    print(f"   http://localhost:{PORT}")
    print("\n✅ Server is running... Press Ctrl+C to stop\n")
    print("=" * 60 + "\n")

    Handler = GarageRequestHandler
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\n👋 Shutting down server...")
            print("=" * 60)
