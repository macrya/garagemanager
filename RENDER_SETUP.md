# Render.com Deployment Setup Guide

## Issue: "ModuleNotFoundError: No module named 'your_application'"

If you're seeing this error, it means your Render service is configured with incorrect start command settings that are overriding the `render.yaml` configuration.

### The Problem

Your Render service is trying to run:
```bash
gunicorn your_application.wsgi
```

But this application is a **standalone Python HTTP server** that doesn't use or need gunicorn or WSGI.

### The Solution

You need to update your Render service configuration to use the correct start command. Here are two methods:

---

## Method 1: Update Existing Service via Dashboard (Recommended)

1. **Log in to your Render dashboard** at https://dashboard.render.com
2. **Find your service** (likely named "garage-manager" or similar)
3. **Click on the service** to open its settings
4. **Go to the "Settings" tab**
5. **Scroll down to "Build & Deploy"**
6. **Update the following fields:**
   - **Build Command:** `pip install -r requirements.txt` (or leave empty)
   - **Start Command:** `python3 garage_server.py`
7. **Click "Save Changes"**
8. **Trigger a manual deploy** to test the new configuration

---

## Method 2: Delete and Recreate Service from render.yaml

1. **Delete the existing service** from your Render dashboard
2. **Create a new Web Service** and select "Deploy from render.yaml"
3. **Connect your GitHub repository**
4. **Render will automatically use the configuration** from `render.yaml`

---

## Verification

After updating, your deployment logs should show:
```
==> Running 'python3 garage_server.py'
```

NOT:
```
==> Running 'gunicorn your_application.wsgi'
```

---

## Configuration Files Reference

### render.yaml (correct configuration)
```yaml
services:
  - type: web
    name: garage-manager
    env: python
    buildCommand: pip install -r requirements.txt || true
    startCommand: python3 garage_server.py
```

### Procfile (correct configuration)
```
web: python3 garage_server.py
```

---

## Why This Application Doesn't Need Gunicorn

This Garage Management System is built as a **standalone HTTP server** using Python's built-in `http.server` module. It:

- ✅ Uses only Python standard library
- ✅ Has its own HTTP server implementation
- ✅ Handles concurrent requests via `socketserver`
- ✅ Is production-ready as-is

Gunicorn is typically used for WSGI applications (Django, Flask, etc.), but this app doesn't use the WSGI interface.

---

## Quick Deploy Checklist

- [ ] Remove `gunicorn` from requirements.txt (already done in this commit)
- [ ] Ensure render.yaml has correct `startCommand: python3 garage_server.py`
- [ ] Update Render dashboard service settings to use correct start command
- [ ] Deploy and verify logs show `Running 'python3 garage_server.py'`
- [ ] Test the application at your Render URL

---

## Support

If you continue to have issues:

1. Check that you're looking at the correct service in Render dashboard
2. Verify the service is deploying from the correct branch (`main`)
3. Check the deployment logs for the exact command being run
4. Ensure the render.yaml file is in the root of your repository

---

## Additional Notes

### Environment Variables

The application automatically uses the `PORT` environment variable provided by Render. The default port is 5000 for local development, but Render will override this with its own port.

### Database

The application uses SQLite (`garage_management.db`). This file will be created automatically on first run. Note that Render's free tier uses ephemeral storage, so the database will reset when the service restarts. For persistent storage, consider:

- Upgrading to a paid Render plan with persistent disk
- Using a PostgreSQL database (requires code modifications)
- Using an external database service

### Health Checks

The application responds to health checks at the root path (`/`). This is configured in render.yaml as:
```yaml
healthCheckPath: /
```

---

**Last Updated:** 2025-11-25
**Application:** Garage Management System
**Issue:** Start command configuration
