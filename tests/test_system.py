import unittest
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
