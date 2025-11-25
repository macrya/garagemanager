#!/bin/bash
# Development Server Runner with Auto-reload

set -e

echo "🚀 Starting Garage Manager Development Server..."

# Check if virtual environment exists
if [ -d "venv" ]; then
    echo "📦 Activating virtual environment..."
    source venv/bin/activate
fi

# Set development environment variables
export PORT=5000
export PYTHONUNBUFFERED=1

echo "🌐 Server will be available at: http://localhost:$PORT"
echo "📊 Database: garage_management.db"
echo ""
echo "Press Ctrl+C to stop the server"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Run the server
python3 garage_server.py
