# Garage Management System - Deployment Guide

## 🚀 Quick Deployment Checklist

Before deploying, ensure:
- ✅ `requirements.txt` exists (even if empty)
- ✅ Start command uses `$PORT` environment variable
- ✅ Server binds to `0.0.0.0` (not `localhost` or `127.0.0.1`)
- ✅ All environment variables are properly configured
- ✅ Database path is persistent and writable

---

## 📋 Table of Contents

1. [Deployment Error Troubleshooting](#deployment-error-troubleshooting)
2. [Platform-Specific Guides](#platform-specific-guides)
3. [Environment Variables](#environment-variables)
4. [Database Persistence](#database-persistence)
5. [Security Best Practices](#security-best-practices)

---

## 🔍 Deployment Error Troubleshooting

A deployment process error can occur at several stages, leading to your application failing to start or run correctly. Since you are deploying a Python app on a platform like Render, the errors usually fall into three categories: **Build Errors**, **Start Command Errors**, or **Runtime Environment Errors**.

### Critical First Step: Check Deployment Logs

Go to your platform's dashboard and check the deployment logs. This is the most important diagnostic step!

---

## 1. 🛑 Build Errors (Installation Fails)

The Build Command (e.g., `pip install -r requirements.txt`) runs first. Errors here usually mean the build process can't find or install your dependencies.

| Cause | Error in Logs | Solution |
|---|---|---|
| **Missing requirements.txt** | `No such file or directory: 'requirements.txt'` | ✅ **FIXED** - We've added `requirements.txt` to the root directory. Make sure it's committed to git. |
| **Missing Dependencies** | `ModuleNotFoundError: No module named '...'` | ✅ **NOT APPLICABLE** - This app uses only Python standard library (no external dependencies). |
| **Wrong Python Version** | `python: command not found` or version mismatch | Ensure your platform is using Python 3.6+. Set `PYTHON_VERSION` environment variable if needed. |

### ✅ Build Command (Use this in your platform):
```bash
pip install -r requirements.txt
```

**Note:** Our `requirements.txt` is minimal since we use only Python standard library!

---

## 2. ❌ Start Command Errors (Application Won't Launch)

The server runs your Start Command but the application process immediately exits or fails to bind.

| Cause | Error in Logs | Solution |
|---|---|---|
| **Wrong Module Name** | `ModuleNotFoundError: No module named 'main'` | ✅ **FIXED** - Use `python3 garage_server.py` (not `main:app`). This is NOT a FastAPI/WSGI app. |
| **Server Not Found** | `bash: gunicorn: command not found` | ✅ **NOT NEEDED** - We use Python's built-in HTTP server. No gunicorn/uvicorn required. |
| **Wrong Port Binding** | `Error binding to address` or `Address already in use` | ✅ **FIXED** - App now uses `$PORT` environment variable automatically. |
| **Hardcoded localhost** | Server starts but can't receive external connections | ✅ **FIXED** - App now binds to `0.0.0.0` to accept external connections. |
| **Syntax/Indentation Error** | `SyntaxError: invalid syntax` or `IndentationError` | Check `garage_server.py` for any syntax errors. |

### ✅ Start Command (Use this in your platform):
```bash
python3 garage_server.py
```

**For Render:** The platform automatically sets `$PORT` - our app reads it correctly.

**For Heroku:** Same - uses the `Procfile` we've provided.

---

## 3. ⚙️ Runtime/Environment Errors

These errors occur after the app has started successfully but before it can fully serve requests.

| Cause | Error in Logs | Solution |
|---|---|---|
| **Database Connection Fails** | `sqlite3.OperationalError: unable to open database file` | Ensure the `DB_FILE` path is writable and persistent. Use platform disk/volume storage. |
| **Database Permission Denied** | `Permission denied` when creating/accessing DB | Check file permissions and ensure the app has write access to the database directory. |
| **Missing Environment Variables** | `KeyError: 'SOME_VAR'` | ✅ **FIXED** - All env vars now have defaults. Check `.env.example` for optional configuration. |
| **Database Lost After Restart** | Data disappears after redeployment | ⚠️ **CRITICAL** - Use persistent storage (see [Database Persistence](#database-persistence) below). |

---

## 📝 Platform-Specific Guides

### Render

#### Option 1: Using render.yaml (Recommended)

1. **Add render.yaml to your repository** (already provided)
2. **Connect your repository** to Render
3. **Render will auto-detect** the configuration
4. **Deploy!**

The `render.yaml` file includes:
- Persistent disk for database storage
- Correct build and start commands
- Environment variables

#### Option 2: Manual Configuration

1. **Create a new Web Service** on Render
2. **Connect your repository**
3. **Configure settings:**
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python3 garage_server.py`
   - **Environment Variables:**
     - `PORT` - Auto-set by Render (don't change)
     - `DB_FILE` - Set to `/opt/render/project/src/garage_management.db`
4. **Add Persistent Disk:**
   - Go to "Disks" section
   - Add disk with mount path: `/opt/render/project/src`
   - Size: 1GB (free tier)
5. **Deploy!**

**Important for Render:**
- ✅ Port binding: Handled automatically via `$PORT`
- ✅ External access: App binds to `0.0.0.0`
- ⚠️ Database persistence: **MUST use persistent disk** (see above)

---

### Heroku

1. **Install Heroku CLI**
```bash
heroku login
```

2. **Create Heroku app**
```bash
heroku create your-garage-app
```

3. **Deploy**
```bash
git push heroku main
```

The `Procfile` (already provided) tells Heroku how to run the app.

4. **Open your app**
```bash
heroku open
```

**Important for Heroku:**
- ✅ Uses `Procfile` for start command
- ✅ `$PORT` is set automatically
- ⚠️ Database: Heroku's ephemeral filesystem means DB will be lost on restart
  - For persistent storage, consider upgrading to use PostgreSQL addon or file storage service

---

### Railway

1. **Create new project** on Railway
2. **Connect GitHub repository**
3. **Railway auto-detects** Python and uses our configurations
4. **Set environment variables** (if needed):
   - `DB_FILE` - Path to persistent storage location
5. **Deploy!**

Railway automatically:
- Installs from `requirements.txt`
- Runs using the detected Python app
- Sets `$PORT` environment variable

---

### DigitalOcean App Platform

1. **Create new app** from GitHub repository
2. **Configure:**
   - **Build Command:** `pip install -r requirements.txt`
   - **Run Command:** `python3 garage_server.py`
3. **Add environment variables** (optional)
4. **Deploy!**

---

### Docker Deployment

Create a `Dockerfile` (example provided below):

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Copy application files
COPY garage_server.py .
COPY requirements.txt .

# Install dependencies (minimal/none for this app)
RUN pip install --no-cache-dir -r requirements.txt

# Expose port
EXPOSE 5000

# Run the application
CMD ["python3", "garage_server.py"]
```

Build and run:
```bash
docker build -t garage-manager .
docker run -p 5000:5000 -v $(pwd)/data:/app garage-manager
```

---

### AWS EC2 / VPS / Bare Metal

```bash
# 1. SSH into your server
ssh user@your-server-ip

# 2. Install Python 3
sudo apt update
sudo apt install python3 python3-pip

# 3. Clone or upload your application
git clone https://github.com/yourusername/garagemanager.git
cd garagemanager

# 4. Run the application
python3 garage_server.py

# 5. For production, run in background with screen/tmux
screen -S garage
python3 garage_server.py
# Press Ctrl+A then D to detach

# Or use nohup
nohup python3 garage_server.py > garage.log 2>&1 &
```

#### Using systemd (Recommended for production VPS):

Create `/etc/systemd/system/garage-manager.service`:

```ini
[Unit]
Description=Garage Management System
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/garagemanager
ExecStart=/usr/bin/python3 /opt/garagemanager/garage_server.py
Restart=always
Environment="PORT=5000"
Environment="DB_FILE=/var/lib/garagemanager/garage_management.db"

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable garage-manager
sudo systemctl start garage-manager
sudo systemctl status garage-manager
```

---

## 🌍 Environment Variables

Our application supports the following environment variables:

| Variable | Default | Description | Required? |
|----------|---------|-------------|-----------|
| `PORT` | `5000` | Port the server listens on | ❌ Auto-set by platforms |
| `HOST` | `0.0.0.0` | Host address to bind to | ❌ Defaults to public |
| `DB_FILE` | `garage_management.db` | Path to SQLite database | ❌ Use for custom location |
| `PYTHON_VERSION` | `3.11.0` | Python version (for platforms) | ❌ Optional |

### Setting Environment Variables

**Render:**
```bash
# In Render Dashboard > Environment
PORT=<auto-set>
DB_FILE=/opt/render/project/src/garage_management.db
```

**Heroku:**
```bash
heroku config:set DB_FILE=/app/garage_management.db
```

**Docker:**
```bash
docker run -e PORT=8080 -e DB_FILE=/data/garage.db ...
```

**Local development (.env file):**
```bash
# Copy .env.example to .env
cp .env.example .env
# Edit .env with your values
```

---

## 💾 Database Persistence

**CRITICAL:** SQLite database files can be lost during redeployment on cloud platforms!

### Solutions by Platform:

#### Render - Use Persistent Disks ✅
```yaml
# In render.yaml (already configured)
disk:
  name: garage-data
  mountPath: /opt/render/project/src
  sizeGB: 1
```

Then set `DB_FILE=/opt/render/project/src/garage_management.db`

#### Heroku - Options:
1. **Upgrade to use Heroku Postgres** (recommended)
2. **Use AWS S3** or another file storage service
3. **Accept ephemeral storage** (data lost on restart - not recommended)

#### Docker - Use Volumes:
```bash
docker run -v $(pwd)/data:/app garage-manager
```

This maps your local `./data` directory to `/app` in the container.

#### VPS/EC2 - No special configuration needed
Database persists automatically on the server's filesystem.

### Backup Strategies

```bash
# Daily backup cron job
0 2 * * * cp /path/to/garage_management.db /backups/garage_$(date +\%Y\%m\%d).db

# Manual backup
cp garage_management.db garage_backup_$(date +%Y%m%d_%H%M%S).db

# Restore from backup
cp garage_backup_20240115_120000.db garage_management.db
```

---

## 🔒 Security Best Practices

### Before Going to Production:

1. **Change Default Admin Password** ⚠️
   - Default credentials: `admin` / `admin123`
   - Log in and change immediately!

2. **Use HTTPS** 🔐
   - Most platforms (Render, Heroku) provide free SSL
   - For VPS: Use Nginx/Caddy as reverse proxy with Let's Encrypt

3. **Environment Variables**
   - Never commit `.env` file to git
   - Use platform's secret management for sensitive data

4. **Firewall Configuration**
   - Only expose necessary ports
   - Use platform's firewall features

5. **Database Security**
   - Regular backups (automated)
   - Restrict file permissions: `chmod 600 garage_management.db`
   - Consider encrypting backups

6. **Rate Limiting** (Advanced)
   - Consider adding rate limiting for production
   - Use Nginx/Cloudflare for DDoS protection

7. **Monitoring**
   - Set up uptime monitoring (UptimeRobot, Pingdom)
   - Monitor logs for errors
   - Track database growth

---

## ✅ Deployment Verification Checklist

After deployment, verify:

- [ ] Application starts without errors
- [ ] Can access the web interface
- [ ] Login works with default credentials
- [ ] Can create/read/update/delete customers
- [ ] Can create/read/update/delete vehicles
- [ ] Can create/read/update/delete services
- [ ] Dashboard shows correct statistics
- [ ] Data persists after application restart
- [ ] HTTPS is working (production)
- [ ] Admin password has been changed (production)

---

## 🐛 Common Issues & Solutions

### Issue: "Address already in use"
**Solution:** Another process is using the port. Kill it or change PORT.
```bash
# Find process
lsof -i :5000
# Kill it
kill -9 <PID>
```

### Issue: "Permission denied" for database
**Solution:** Ensure write permissions:
```bash
chmod 755 /path/to/database/directory
chmod 644 garage_management.db
```

### Issue: App starts but can't connect
**Solution:** Check if binding to correct host:
- Should bind to `0.0.0.0` (not `127.0.0.1`)
- ✅ This is now fixed in the code

### Issue: Data lost after restart
**Solution:** Database is not persistent. Use platform's persistent storage (see [Database Persistence](#database-persistence)).

### Issue: 502 Bad Gateway
**Solution:**
- App crashed or didn't start - check logs
- Port binding issue - verify `$PORT` is used correctly
- Health check failing - ensure `/` endpoint works

---

## 📊 Monitoring & Logs

### View Logs:

**Render:**
```
Dashboard > Logs tab
```

**Heroku:**
```bash
heroku logs --tail
```

**Docker:**
```bash
docker logs <container-id>
```

**VPS/systemd:**
```bash
journalctl -u garage-manager -f
```

### Health Check Endpoint

The root endpoint `/` serves the application and can be used for health checks.

---

## 🎓 Additional Resources

- [Python Deployment Best Practices](https://docs.python.org/3/using/deployment.html)
- [Render Documentation](https://render.com/docs)
- [Heroku Python Guide](https://devcenter.heroku.com/articles/getting-started-with-python)
- [Docker Python Best Practices](https://docs.docker.com/language/python/)

---

## 🆘 Getting Help

If you encounter issues:

1. **Check the logs** (most important!)
2. **Verify all files are committed** to git
3. **Ensure environment variables** are set correctly
4. **Test locally first** with `python3 garage_server.py`
5. **Check this guide** for your specific error message

---

## 📝 Summary

This garage management system is now **deployment-ready** for all major platforms:

✅ **Requirements.txt** - Present (even though minimal)
✅ **Environment Variables** - Uses `$PORT` and other platform-provided vars
✅ **Network Binding** - Binds to `0.0.0.0` for external access
✅ **Start Command** - Simple: `python3 garage_server.py`
✅ **Configuration Files** - Includes `render.yaml`, `Procfile`, `.env.example`
✅ **Documentation** - Comprehensive error handling guide

**Deployment Time:** < 5 minutes
**Dependencies:** Zero (pure Python)
**Complexity:** Minimal

Happy deploying! 🚀
