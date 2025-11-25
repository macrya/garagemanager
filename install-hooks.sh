#!/bin/bash
# Install Git Pre-commit Hooks

set -e

echo "🪝 Installing pre-commit hooks..."

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Install pre-commit package
pip install pre-commit

# Install the git hooks
pre-commit install

echo "✅ Pre-commit hooks installed!"
echo ""
echo "The following checks will run automatically before each commit:"
echo "  • Trailing whitespace removal"
echo "  • End-of-file fixer"
echo "  • YAML/JSON validation"
echo "  • Large file detection"
echo "  • Merge conflict detection"
echo "  • Python syntax checking (flake8)"
echo "  • Code formatting (black)"
echo "  • Security scanning (bandit)"
echo ""
echo "To run checks manually: pre-commit run --all-files"
echo "To skip hooks (not recommended): git commit --no-verify"
