# 🚀 Deploying to Render.com

This guide walks you through deploying the Garage Management System to Render.com using the included Blueprint configuration.

## 🎯 Prerequisites

- GitHub account with this repository pushed
- Render.com account (free to create)

## ⚡ Quick Deploy (Recommended)

### Method 1: Using render.yaml Blueprint (Automated)

1. **Push your code to GitHub** (if not already done)

2. **Go to Render Dashboard**
   - Visit https://dashboard.render.com
   - Click "New +" → "Blueprint"

3. **Connect Repository**
   - Select "Connect a repository"
   - Authorize Render to access your GitHub
   - Select the `garagemanager` repository

4. **Deploy!**
   - Render will automatically read `render.yaml`
   - It will create:
     - PostgreSQL database (`garage-db`)
     - Web service (`garage-api`)
     - All environment variables
   - Click "Apply"

5. **Wait for deployment** (~5 minutes)
   - Database provisions first
   - Then web service builds and deploys
   - Watch the logs for any errors

6. **Access your API**
   - Once deployed, you'll get a URL like: `https://garage-api.onrender.com`
   - Visit: `https://garage-api.onrender.com/docs` for interactive API docs

## 🔧 Method 2: Manual Setup

### Step 1: Create PostgreSQL Database

1. In Render Dashboard, click "New +" → "PostgreSQL"
2. Configure:
   - **Name**: `garage-db`
   - **Database**: `garage_db`
   - **User**: `garage_user`
   - **Region**: Oregon (or closest to you)
   - **Plan**: Starter ($7/mo) or Free (for testing)
3. Click "Create Database"
4. **Copy the Internal Database URL** - you'll need this!

### Step 2: Create Web Service

1. Click "New +" → "Web Service"
2. Connect your GitHub repository
3. Configure:

   **Basic Settings:**
   - **Name**: `garage-api`
   - **Region**: Same as database (e.g., Oregon)
   - **Branch**: `main` or your branch name
   - **Root Directory**: Leave blank
   - **Runtime**: Python 3

   **Build Settings:**
   - **Build Command**:
     ```bash
     pip install -r requirements.txt
     ```

   - **Start Command**:
     ```bash
     gunicorn app.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT
     ```

   **Instance Type:**
   - **Plan**: Starter ($7/mo) - Recommended
   - Or Free (sleeps after 15 min inactivity)

4. **Add Environment Variables:**

   Click "Advanced" → "Add Environment Variable" for each:

   | Key | Value | Notes |
   |-----|-------|-------|
   | `PYTHONUNBUFFERED` | `1` | Required |
   | `SECRET_KEY` | Generate: `openssl rand -hex 32` | Important! |
   | `DEBUG` | `false` | Production setting |
   | `DATABASE_URL` | See below | From database |
   | `DATABASE_URL_SYNC` | See below | From database |
   | `ALGORITHM` | `HS256` | JWT algorithm |
   | `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | 24 hours |
   | `CORS_ORIGINS` | `*` or your domain | CORS settings |

   **For Database URLs:**
   - Get the Internal Database URL from your database settings
   - Example: `postgresql://user:pass@host.render.com:5432/dbname`

   ```
   DATABASE_URL: postgresql+asyncpg://user:pass@host.render.com:5432/dbname
   DATABASE_URL_SYNC: postgresql://user:pass@host.render.com:5432/dbname
   ```

   **Important**: For `DATABASE_URL`, replace `postgresql://` with `postgresql+asyncpg://`

5. Click "Create Web Service"

### Step 3: Deploy & Monitor

1. Watch the deployment logs
2. Wait for "Build successful" and "Deploy live"
3. Check health: `https://your-service.onrender.com/health`

## 🎉 Post-Deployment

### 1. Create Your First User

Visit the interactive docs: `https://your-service.onrender.com/docs`

1. Navigate to **POST /api/v1/auth/register**
2. Click "Try it out"
3. Enter:
   ```json
   {
     "username": "admin",
     "email": "admin@yourdomain.com",
     "password": "YourSecurePassword123!",
     "full_name": "Admin User",
     "role": "admin"
   }
   ```
4. Click "Execute"

### 2. Login & Get Token

1. Navigate to **POST /api/v1/auth/login**
2. Enter your credentials
3. Copy the `access_token`
4. Click "Authorize" button (top right)
5. Enter: `Bearer <your-token>`
6. Now all endpoints are accessible!

### 3. Test the API

Try creating a customer, vehicle, or service using the interactive docs.

## 🔒 Security Checklist

- ✅ Generated secure `SECRET_KEY`
- ✅ Set `DEBUG=false`
- ✅ Using PostgreSQL (not SQLite)
- ✅ HTTPS enabled (automatic on Render)
- ✅ Environment variables (not hardcoded secrets)
- ✅ Strong database password

## 🔧 Updating Your Deployment

### Auto-Deploy (Recommended)

1. Push changes to GitHub:
   ```bash
   git add .
   git commit -m "Update feature"
   git push
   ```

2. Render automatically:
   - Detects the push
   - Builds new version
   - Deploys with zero downtime (paid plans)

### Manual Deploy

In Render Dashboard:
1. Go to your service
2. Click "Manual Deploy" → "Deploy latest commit"

## 📊 Monitoring & Logs

### View Logs
```
Dashboard → Your Service → Logs
```

### Health Check
```bash
curl https://your-service.onrender.com/health
```

Expected response:
```json
{
  "status": "healthy",
  "version": "2.0.0"
}
```

### Database Connection

In Render Dashboard → Database → Connect:
```bash
# Use the provided connection string
psql <CONNECTION_STRING>
```

## 💰 Cost Breakdown

### Free Tier (Testing Only)
- Database: Free (90 days, then $7/mo)
- Web Service: Free
- **Limitations**: Sleeps after 15 min inactivity, slow cold starts

### Starter (Recommended)
- Database: $7/month
- Web Service: $7/month
- **Total: $14/month**
- Features: Always on, faster, zero downtime deploys

### Production
- Database: $7-$450/month (based on size)
- Web Service: $7-$450/month (based on traffic)
- **Recommended**: Start with Starter, scale as needed

## 🐛 Troubleshooting

### Deployment Failed

**Check logs for:**
```
Dashboard → Service → Logs
```

**Common issues:**
1. **Database connection failed**
   - Verify `DATABASE_URL` is correct
   - Ensure database is in same region
   - Check database is running

2. **Module not found**
   - Verify `requirements.txt` is complete
   - Check build logs for pip errors

3. **Port binding error**
   - Start command must use `$PORT` variable
   - Don't hardcode port 8000

### Database Connection Issues

1. **Test connection:**
   ```bash
   # In service shell (Dashboard → Shell)
   python -c "from app.database import engine; print('Connected!')"
   ```

2. **Check environment variables:**
   ```bash
   env | grep DATABASE
   ```

### Slow Response Times

- Upgrade to Starter plan (faster CPU)
- Check database queries (add indexes)
- Monitor logs for slow requests

## 🔄 Database Migrations

When you update models:

1. **Using Alembic** (recommended for future):
   ```bash
   # Add to requirements.txt: alembic
   # In service shell:
   alembic revision --autogenerate -m "description"
   alembic upgrade head
   ```

2. **Manual** (current setup):
   - Database tables auto-create on first run
   - For schema changes, may need to drop/recreate

## 🌐 Custom Domain

1. In Render Dashboard → Service → Settings
2. Click "Add Custom Domain"
3. Enter your domain
4. Add DNS records as shown
5. Wait for SSL certificate (automatic)

## 📈 Scaling

### Horizontal Scaling
```
Dashboard → Service → Settings → Instance Count
```
Increase workers for more traffic.

### Vertical Scaling
```
Dashboard → Service → Settings → Instance Type
```
Upgrade to Standard/Pro for more resources.

## 🎓 Next Steps

- Set up monitoring (Render provides metrics)
- Configure automated backups (Database settings)
- Add custom domain
- Set up staging environment
- Implement CI/CD with GitHub Actions

## 📞 Support

- Render Docs: https://render.com/docs
- Render Status: https://status.render.com
- FastAPI Docs: https://fastapi.tiangolo.com

---

**Your API is now live!** 🚀

Visit: `https://your-service.onrender.com/docs`
