#!/bin/bash
# Development Environment Setup Script

set -e

echo "🚀 Setting up Garage Manager development environment..."

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "✓ Found Python $PYTHON_VERSION"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

# Activate virtual environment
echo "🔄 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install production dependencies
echo "📥 Installing production dependencies..."
pip install -r requirements.txt

# Install development dependencies
echo "📥 Installing development dependencies..."
pip install flake8 pylint black mypy bandit safety pytest pytest-cov

# Create requirements-dev.txt
echo "📝 Creating requirements-dev.txt..."
pip freeze > requirements-dev.txt

echo ""
echo "✅ Development environment setup complete!"
echo ""
echo "To activate the environment, run:"
echo "  source venv/bin/activate"
echo ""
echo "To start the development server, run:"
echo "  ./dev-run.sh"
echo ""
