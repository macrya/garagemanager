#!/bin/bash
# Code Quality and Linting Script

set -e

echo "🔍 Running code quality checks..."
echo ""

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Track overall status
ERRORS=0

# Flake8 - Syntax and style checking
echo "1️⃣  Running Flake8 (syntax and style)..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics; then
    echo "✓ No critical syntax errors found"
    flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics
else
    echo "❌ Critical syntax errors found!"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# Black - Code formatting
echo "2️⃣  Running Black (code formatting)..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if black --check --diff .; then
    echo "✓ Code formatting is correct"
else
    echo "⚠️  Code formatting issues found. Run 'black .' to fix."
    ERRORS=$((ERRORS + 1))
fi
echo ""

# MyPy - Type checking
echo "3️⃣  Running MyPy (type checking)..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if mypy garage_server.py --ignore-missing-imports; then
    echo "✓ Type checking passed"
else
    echo "⚠️  Type checking found issues"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# Bandit - Security scanning
echo "4️⃣  Running Bandit (security scan)..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if bandit -r . -ll; then
    echo "✓ No security issues found"
else
    echo "⚠️  Security issues found"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# Summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ $ERRORS -eq 0 ]; then
    echo "✅ All checks passed!"
    exit 0
else
    echo "⚠️  Found issues in $ERRORS check(s)"
    echo ""
    echo "To auto-fix formatting issues, run:"
    echo "  black ."
    exit 1
fi
