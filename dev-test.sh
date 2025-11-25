#!/bin/bash
# Test Runner Script

set -e

echo "🧪 Running tests..."
echo ""

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Create tests directory if it doesn't exist
if [ ! -d "tests" ]; then
    echo "📁 Creating tests directory..."
    mkdir -p tests
    touch tests/__init__.py
fi

# Run pytest if test files exist
if [ -f "tests/test_*.py" ] || [ -f "test_*.py" ]; then
    echo "Running pytest with coverage..."
    pytest --cov=. --cov-report=term-missing --cov-report=html -v
    echo ""
    echo "✅ Tests complete! Coverage report generated in htmlcov/"
else
    echo "⚠️  No test files found. Creating basic test structure..."
    echo "Create test files in the 'tests/' directory following the pattern 'test_*.py'"

    # Basic server startup test
    echo "Running basic server startup test..."
    timeout 10 python3 garage_server.py &
    PID=$!
    sleep 5

    if curl -f http://localhost:5000/ > /dev/null 2>&1; then
        echo "✅ Server started successfully!"
        kill $PID 2>/dev/null || true
        exit 0
    else
        echo "❌ Server failed to start!"
        kill $PID 2>/dev/null || true
        exit 1
    fi
fi
