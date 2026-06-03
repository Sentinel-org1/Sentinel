# Sentinel — Complete Setup & Troubleshooting Guide

## 🚀 Quick Start (Docker Compose - Recommended)

### Prerequisites
- Docker & Docker Compose installed
- Port availability: 3000 (frontend), 8000 (backend), 5433 (postgres), 6379 (redis)

### Start Everything
```bash
cd infra
docker-compose up -d
```

### First Login
- Navigate to: `http://localhost:3000`
- Use credentials from `/backend/scripts/seed_db.py`:
  - **Email**: `admin@sentinel.ai`
  - **Password**: `admin123` (or check seed script for actual value)

### Database Initialization
Database migrations run automatically in Docker via:
```bash
alembic upgrade head
```

---

## 🔧 Local Development Setup

### 1. Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL 15+
- Redis 7+
- Virtual environment

### 2. Backend Setup

#### Install Dependencies
```bash
cd backend
python -m venv .venv

# Activate (Windows)
.\.venv\Scripts\activate

# Activate (Linux/Mac)
source .venv/bin/activate

# Install packages
pip install -e ".[dev]"
```

#### Configure Environment
Create `backend/.env`:
```
DATABASE_URL=postgresql+asyncpg://sentinel:sentinel@localhost:5432/sentinel
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
SECRET_KEY=your-secret-key-here-change-in-production
ENVIRONMENT=development
CORS_ORIGINS=["http://localhost:3000", "http://localhost:5173"]
API_HOST=0.0.0.0
API_PORT=8000
```

#### Initialize Database
```bash
cd backend
alembic upgrade head
```

#### Seed Demo Data (Optional)
```bash
cd backend
python scripts/seed_db.py
```

#### Start Backend Server
```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Backend ready at**: `http://localhost:8000`
- **Docs**: `http://localhost:8000/docs`
- **Health**: `http://localhost:8000/health`

---

### 3. Frontend Setup

#### Install Dependencies
```bash
cd frontend
npm install
```

#### Start Development Server
```bash
cd frontend
npm run dev
```

**Frontend ready at**: `http://localhost:5173` or `http://localhost:3000`

---

### 4. Celery Worker (Background Tasks)

#### Terminal in `backend/` with venv activated:
```bash
celery -A app.tasks.celery_app worker \
  --loglevel=info \
  --concurrency=4 \
  -Q default,drift,shap
```

---

### 5. Celery Beat (Scheduled Tasks)

#### Another terminal in `backend/` with venv activated:
```bash
celery -A app.tasks.celery_app beat --loglevel=info
```

---

## 🐛 White Screen Troubleshooting

### Issue: Blank White Screen After Login

#### **Check #1: Backend is Running**
```bash
curl http://localhost:8000/health
# Should return: {"status": "ok", "version": "0.1.0"}
```
If fails → **Start backend** (see Backend Setup above)

---

#### **Check #2: Frontend Can Connect to Backend**
Open browser DevTools (F12) → **Console** tab:
```javascript
// Should return 200 if backend is reachable
fetch('http://localhost:8000/health').then(r => r.json()).then(console.log)
```

If fails → Backend not running or port is wrong

---

#### **Check #3: CORS Configuration**
In DevTools **Network** tab, look for failed requests with error:
```
Access to XMLHttpRequest... blocked by CORS policy
```

**Fix**: Update `backend/app/config.py`:
```python
CORS_ORIGINS: list[str] = [
    "http://localhost:3000",
    "http://localhost:5173",  # Vite dev server
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]
```

Then restart backend.

---

#### **Check #4: API Request Failing (DevTools → Network)**
Look for 401/403/500 errors on `/api/models/` or `/auth/me`

**Solutions**:
- **401 Unauthorized**: Token not being sent
  - Check: `localStorage.getItem('sentinel_token')` in console
  - If empty, login credentials were wrong
  
- **500 Internal Server Error**: Backend crashed
  - Check backend terminal for stack trace
  - Common: Database not initialized (run `alembic upgrade head`)
  
- **Connection Refused**: Backend not running
  - Restart backend with correct host/port

---

#### **Check #5: Frontend Build Issues**
If seeing console errors about missing modules:

```bash
cd frontend
npm install  # Reinstall dependencies
npm run type-check  # Check TypeScript errors
npm run dev  # Rebuild
```

---

#### **Check #6: Check Database Connection**
```bash
psql postgresql://sentinel:sentinel@localhost:5432/sentinel

# In psql:
\dt  # List all tables - should see 8+ tables
\q   # Quit
```

If no tables → Run migrations:
```bash
cd backend
alembic upgrade head
```

---

## 📊 Expected Dashboard Contents

After successful login, you should see:
- **Model Cards** showing registered models
- **Drift Timeline** with recent drift events
- **Alert Bell** (top right) with unread counts
- **WebSocket Status** indicator

If these don't load:
1. Check backend `/api/models/` endpoint:
   ```bash
   curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8000/api/models/
   ```

2. Seed demo models:
   ```bash
   cd backend
   python scripts/seed_db.py
   ```

---

## 🔌 Vite Proxy Configuration

**Frontend `vite.config.ts` proxies requests**:
```typescript
proxy: {
  '/api': 'http://localhost:8000',      // API requests
  '/auth': 'http://localhost:8000',     // Auth endpoints
  '/ws': { target: 'ws://localhost:8000', ws: true },  // WebSocket
}
```

This means:
- `http://localhost:3000/api/models` → forwards to `http://localhost:8000/api/models`
- ✅ Works in **dev mode** (`npm run dev`)
- ❌ **Does NOT work** in production build - needs reverse proxy (nginx/Apache)

---

## 🚀 Production Deployment

### Option 1: Docker Compose (with prod config)
```bash
cd infra
docker-compose -f docker-compose.prod.yml up -d
```

### Option 2: Docker Multi-Stage Build
Backend Dockerfile uses multi-stage:
- `builder`: Installs dependencies
- `runtime`: Runs uvicorn

Frontend Dockerfile:
- `build`: TypeScript compilation
- Serves static files via Nginx

---

## 📝 Environment Variables Reference

### Backend `.env`
| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | (required) | PostgreSQL connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis broker |
| `SECRET_KEY` | `change-me-in-production-use-secrets-manager` | JWT signing key |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | Allowed frontend domains |
| `ENVIRONMENT` | `development` | `development\|staging\|production` |
| `SENTRY_DSN` | (empty) | Error tracking (optional) |

---

## 🧪 Testing

### Backend Unit Tests
```bash
cd backend
pytest tests/unit/ -v
```

### Frontend Unit Tests
```bash
cd frontend
npm run test
```

### Frontend E2E Tests
```bash
cd frontend
npm run test:e2e  # If configured
```

---

## 📋 Common Commands Cheat Sheet

```bash
# Start everything (Docker)
cd infra && docker-compose up -d

# View logs
docker-compose logs -f backend
docker-compose logs -f frontend

# Stop everything
docker-compose down

# Backend only (local dev)
cd backend && uvicorn app.main:app --reload

# Frontend only (local dev)
cd frontend && npm run dev

# Database migrations
cd backend && alembic upgrade head

# Seed demo data
cd backend && python scripts/seed_db.py

# Reset database
psql postgresql://sentinel:sentinel@localhost:5432/sentinel
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
\q
cd backend && alembic upgrade head
```

---

## 🆘 Still Not Working?

1. **Check all services running**:
   ```bash
   docker-compose ps
   # All should show "Up" status
   ```

2. **Restart everything**:
   ```bash
   docker-compose down
   docker-compose up -d
   docker-compose logs -f  # Watch logs
   ```

3. **Clear browser cache** (Ctrl+Shift+Delete) and hard refresh (Ctrl+Shift+R)

4. **Check browser console** (F12) for errors

5. **Check backend logs**:
   ```bash
   docker-compose logs backend
   ```

6. **Verify ports are free**:
   ```bash
   # Windows
   netstat -ano | findstr :3000
   netstat -ano | findstr :8000
   
   # Linux/Mac
   lsof -i :3000
   lsof -i :8000
   ```

---

## 📚 Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                     Browser (React)                     │
│              http://localhost:3000                      │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP/WebSocket
                       ↓
    ┌──────────────────────────────────────────┐
    │     Vite Dev Server (Port 5173)          │
    │  (proxies /api & /auth to Backend)      │
    └──────────────────┬───────────────────────┘
                       │
                       ↓
┌─────────────────────────────────────────────────────────┐
│              FastAPI Backend (8000)                     │
│  ┌──────────────┐  ┌──────────┐  ┌────────────┐       │
│  │ Auth Router  │  │ Drift API│  │ WebSocket  │       │
│  └──────────────┘  └──────────┘  └────────────┘       │
└──────────┬─────────────────────────────┬────────────────┘
           │                             │
           ↓                             ↓
    ┌─────────────┐             ┌─────────────────┐
    │ PostgreSQL  │             │ Redis Streams   │
    │ (Port 5433) │             │ (Port 6379)     │
    └─────────────┘             └─────────────────┘
                                       │
                                       ↓
                                ┌─────────────────┐
                                │ Celery Worker   │
                                │ (Background)    │
                                └─────────────────┘
```

---

## ✅ Verification Checklist

- [ ] Backend running: `curl http://localhost:8000/health` → 200
- [ ] Database initialized: `alembic upgrade head` completed
- [ ] Frontend running: `http://localhost:3000` loads
- [ ] Can reach login page without errors
- [ ] Can login with demo credentials
- [ ] Dashboard loads with model cards
- [ ] Check browser console (F12) for errors
- [ ] Check DevTools Network tab for failed requests

---

Good luck! 🚀
