# Garage Manager - Development Guide

## 🚀 Quick Start

### Initial Setup (First Time Only)

```bash
# Clone the repository
git clone <repository-url>
cd garagemanager

# Set up development environment
make setup

# Or manually:
chmod +x dev-setup.sh
./dev-setup.sh
```

### Daily Development Workflow

```bash
# Start development server
make run

# Or manually:
./dev-run.sh
```

Access the application at: http://localhost:5000

## 🛠️ Automation Tools

### Make Commands

The project uses a Makefile to automate common tasks:

```bash
make help          # Show all available commands
make setup         # Set up development environment
make run           # Start development server
make lint          # Run code quality checks
make format        # Auto-format code
make test          # Run tests
make security      # Run security scans
make deploy-check  # Verify deployment config
make all           # Run all checks (lint + security + test)
make clean         # Clean generated files
```

### Development Scripts

| Script | Purpose |
|--------|---------|
| `dev-setup.sh` | Initialize development environment with virtual env and dependencies |
| `dev-run.sh` | Start development server with proper environment variables |
| `dev-lint.sh` | Run all code quality checks (flake8, black, mypy, bandit) |
| `dev-test.sh` | Run test suite with coverage reporting |
| `install-hooks.sh` | Install git pre-commit hooks |

## 🔍 Code Quality

### Automated Checks

The project enforces code quality through multiple layers:

1. **Syntax & Style** (Flake8)
   - PEP 8 compliance
   - Maximum line length: 127 characters
   - Complexity checks

2. **Code Formatting** (Black)
   - Consistent code style
   - Auto-formatting available

3. **Type Checking** (MyPy)
   - Static type analysis
   - Catches type-related bugs early

4. **Security Scanning** (Bandit)
   - Detects common security issues
   - OWASP compliance checks

### Running Checks

```bash
# Run all checks
make lint

# Auto-fix formatting issues
make format

# Check security
make security
```

## 🧪 Testing

### Running Tests

```bash
# Run all tests with coverage
make test

# Or manually
./dev-test.sh
```

### Test Coverage

Coverage reports are generated in `htmlcov/` directory.

```bash
# View coverage report
open htmlcov/index.html
```

## 🪝 Git Hooks

### Pre-commit Hooks

Pre-commit hooks automatically run before each commit to ensure code quality.

**Install hooks:**
```bash
./install-hooks.sh
```

**What gets checked:**
- ✅ Trailing whitespace removal
- ✅ End-of-file fixer
- ✅ YAML/JSON validation
- ✅ Large file detection
- ✅ Merge conflict detection
- ✅ Python syntax (flake8)
- ✅ Code formatting (black)
- ✅ Security scanning (bandit)

**Run manually:**
```bash
pre-commit run --all-files
```

**Skip hooks (not recommended):**
```bash
git commit --no-verify
```

## 🚢 Deployment

### Automated Deployment (Render)

The project uses `render.yaml` for infrastructure-as-code deployment.

**Configuration:**
- Auto-deploys from `main` branch
- Python 3.11 runtime
- Automatic PORT binding
- Health checks enabled

**Deploy:**
1. Push to `main` branch
2. Render automatically builds and deploys
3. Check deployment status in Render dashboard

### Manual Deployment Verification

```bash
make deploy-check
```

This verifies all required deployment files exist and are valid.

## 📋 CI/CD Pipeline

### GitHub Actions

Automated workflows run on every push and pull request:

**Workflow: CI/CD Pipeline** (`.github/workflows/ci.yml`)

#### Jobs:

1. **Lint and Test** (Matrix: Python 3.8, 3.9, 3.10, 3.11)
   - Install dependencies
   - Run flake8 linting
   - Check code formatting
   - Type checking with mypy
   - Test server startup
   - Verify requirements.txt

2. **Security Scan**
   - Bandit security analysis
   - Safety vulnerability checks

3. **Deploy Check** (main branch only)
   - Verify deployment files exist
   - Validate render.yaml syntax

### Viewing CI Results

1. Go to GitHub repository
2. Click "Actions" tab
3. View workflow runs and results

## 📦 Dependencies

### Production Dependencies

Defined in `requirements.txt`:
- gunicorn (WSGI server for production)
- Standard library only (no external dependencies for core app)

### Development Dependencies

Defined in `requirements-dev.txt`:
- Testing: pytest, pytest-cov
- Linting: flake8, pylint
- Formatting: black
- Type checking: mypy
- Security: bandit, safety
- Hooks: pre-commit
- Utilities: pyyaml

**Install dev dependencies:**
```bash
pip install -r requirements-dev.txt
```

## 🏗️ Project Structure

```
garagemanager/
├── .github/
│   └── workflows/
│       └── ci.yml              # GitHub Actions CI/CD
├── garage_server.py            # Main application
├── requirements.txt            # Production dependencies
├── requirements-dev.txt        # Development dependencies
├── Procfile                    # Process file for deployment
├── render.yaml                 # Render deployment config
├── Makefile                    # Task automation
├── dev-setup.sh               # Setup script
├── dev-run.sh                 # Run development server
├── dev-lint.sh                # Linting script
├── dev-test.sh                # Testing script
├── install-hooks.sh           # Hook installation
├── .pre-commit-config.yaml    # Pre-commit configuration
├── DEVELOPMENT.md             # This file
├── DEPLOYMENT.md              # Deployment guide
└── README.md                  # Project overview
```

## 🔧 Environment Variables

### Development

```bash
PORT=5000                      # Server port
PYTHONUNBUFFERED=1            # Unbuffered output
```

### Production (Render)

```bash
PORT                           # Auto-set by Render
PYTHON_VERSION=3.11.0         # Python runtime version
```

## 🐛 Troubleshooting

### Common Issues

**Issue: Virtual environment not activating**
```bash
# Recreate virtual environment
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt
```

**Issue: Pre-commit hooks failing**
```bash
# Update pre-commit
pre-commit autoupdate

# Clear cache and retry
pre-commit clean
pre-commit run --all-files
```

**Issue: Tests failing**
```bash
# Clean up and retry
make clean
make test
```

**Issue: Port already in use**
```bash
# Find and kill process on port 5000
lsof -ti:5000 | xargs kill -9

# Or change port
export PORT=8000
make run
```

## 📝 Best Practices

### Before Committing

1. ✅ Run `make lint` to check code quality
2. ✅ Run `make test` to ensure tests pass
3. ✅ Run `make format` to auto-format code
4. ✅ Write descriptive commit messages

### Before Pushing

1. ✅ Ensure all CI checks pass locally
2. ✅ Update documentation if needed
3. ✅ Test deployment configuration if changed

### Code Style

- Follow PEP 8 guidelines
- Use type hints where appropriate
- Keep functions small and focused
- Write docstrings for complex functions
- Maximum line length: 127 characters

## 🔐 Security

### Security Best Practices

1. **Never commit sensitive data**
   - API keys
   - Passwords
   - Database credentials

2. **Run security scans regularly**
   ```bash
   make security
   ```

3. **Keep dependencies updated**
   ```bash
   pip install --upgrade -r requirements-dev.txt
   safety check
   ```

## 📚 Additional Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Render Documentation](https://render.com/docs)
- [Python Style Guide (PEP 8)](https://peps.python.org/pep-0008/)
- [Black Code Formatter](https://black.readthedocs.io/)
- [Pre-commit Framework](https://pre-commit.com/)

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Set up development environment: `make setup`
4. Make your changes
5. Run all checks: `make all`
6. Commit with descriptive messages
7. Push and create a pull request

## ✅ Checklist for New Contributors

- [ ] Fork and clone repository
- [ ] Run `make setup`
- [ ] Install pre-commit hooks: `./install-hooks.sh`
- [ ] Verify setup: `make all`
- [ ] Read `DEPLOYMENT.md` for deployment info
- [ ] Create feature branch
- [ ] Make changes
- [ ] Run `make all` before committing
- [ ] Push and create PR

---

**Happy coding! 🚀**
