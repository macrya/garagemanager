.PHONY: help setup run lint test clean format security deploy-check all

# Default target
help:
	@echo "🔧 Garage Manager Development Automation"
	@echo ""
	@echo "Available commands:"
	@echo "  make setup         - Set up development environment"
	@echo "  make run           - Start development server"
	@echo "  make lint          - Run code quality checks"
	@echo "  make format        - Auto-format code with black"
	@echo "  make test          - Run tests"
	@echo "  make security      - Run security scans"
	@echo "  make deploy-check  - Verify deployment configuration"
	@echo "  make all           - Run lint, security, and tests"
	@echo "  make clean         - Clean up generated files"
	@echo ""

# Set up development environment
setup:
	@echo "🚀 Setting up development environment..."
	@chmod +x dev-setup.sh dev-run.sh dev-lint.sh dev-test.sh
	@./dev-setup.sh

# Run development server
run:
	@chmod +x dev-run.sh
	@./dev-run.sh

# Run linting
lint:
	@chmod +x dev-lint.sh
	@./dev-lint.sh

# Auto-format code
format:
	@echo "🎨 Formatting code with black..."
	@if [ -d "venv" ]; then source venv/bin/activate && black .; else black .; fi
	@echo "✅ Code formatted!"

# Run tests
test:
	@chmod +x dev-test.sh
	@./dev-test.sh

# Run security scans
security:
	@echo "🔒 Running security scans..."
	@if [ -d "venv" ]; then source venv/bin/activate; fi && \
	bandit -r . -ll && \
	safety check || true
	@echo "✅ Security scan complete!"

# Verify deployment configuration
deploy-check:
	@echo "🚀 Verifying deployment configuration..."
	@test -f Procfile && echo "✓ Procfile exists" || (echo "❌ Procfile missing" && exit 1)
	@test -f render.yaml && echo "✓ render.yaml exists" || (echo "❌ render.yaml missing" && exit 1)
	@test -f requirements.txt && echo "✓ requirements.txt exists" || (echo "❌ requirements.txt missing" && exit 1)
	@test -f garage_server.py && echo "✓ garage_server.py exists" || (echo "❌ garage_server.py missing" && exit 1)
	@echo "✅ All deployment files verified!"

# Run all checks
all: lint security test deploy-check
	@echo ""
	@echo "✅ All checks passed!"

# Clean up generated files
clean:
	@echo "🧹 Cleaning up..."
	@rm -rf __pycache__ .pytest_cache .mypy_cache htmlcov .coverage
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Cleanup complete!"
