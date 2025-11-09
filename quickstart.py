#!/usr/bin/env python3
"""
Quick Start Script for Garage Management System
Simplified version for quick testing
"""

import os
import sys
import subprocess
import time
import requests
from pathlib import Path

def quick_start():
    print("🚀 Quick Starting Garage Management System...\n")
    
    # Check dependencies
    try:
        import flask
        import flask_sqlalchemy
        import flask_bcrypt
        import flask_jwt_extended
        import flask_cors
        import requests
        print("✅ All dependencies found")
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("Please run: pip install flask flask-sqlalchemy flask-bcrypt flask-jwt-extended flask-cors requests")
        return
    
    # Create and start backend
    backend_script = """
from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import sys

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///garage.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'quick-start-secret'

db = SQLAlchemy(app)
CORS(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True)

@app.route('/api/system/health')
def health():
    return jsonify({"status": "healthy", "message": "Garage System Running"})

@app.route('/api/auth/login', methods=['POST'])
def login():
    return jsonify({
        "access_token": "quick-start-token",
        "user": {"username": "admin", "name": "Administrator"}
    })

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    print("✅ Backend running on http://localhost:5000")
    app.run(debug=True, port=5000)
"""
    
    with open('quick_backend.py', 'w') as f:
        f.write(backend_script)
    
    # Start backend
    try:
        process = subprocess.Popen([sys.executable, 'quick_backend.py'])
        print("⏳ Starting backend...")
        time.sleep(3)
        
        # Test connection
        response = requests.get('http://localhost:5000/api/system/health')
        if response.status_code == 200:
            print("✅ Backend started successfully!")
            print("\n🔧 Available endpoints:")
            print("   - http://localhost:5000/api/system/health")
            print("   - http://localhost:5000/api/auth/login")
            print("\nPress Ctrl+C to stop")
            
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n🛑 Shutting down...")
        else:
            print("❌ Backend failed to start")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        process.terminate()
        # Cleanup
        for file in ['quick_backend.py', 'garage.db']:
            if os.path.exists(file):
                os.remove(file)

if __name__ == "__main__":
    quick_start()