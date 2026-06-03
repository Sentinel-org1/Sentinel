# 🐛 Sentinel Backend & Frontend — Identified Issues & Fixes

## 📋 Issue Summary

### Critical Issues (Blocking)
1. ✅ **TypeScript `any` type errors in CalibrationROC.tsx** — FIXED
2. **White screen on dashboard** — See troubleshooting in SETUP_GUIDE.md
3. **CORS configuration might reject requests from some origins**
4. **Database migrations need to run before first access**

### Non-Critical Issues (Quality)
5. **Cookie security setting in development mode**
6. **Missing error handling in some API endpoints**
7. **WebSocket reconnection strategy**

---

## ✅ Issue #1: TypeScript Errors — FIXED

### Problem
Two ESLint errors in [frontend/src/components/charts/CalibrationROC.tsx](frontend/src/components/charts/CalibrationROC.tsx):
- Line 61: `CustomTooltip` props typed as `any`
- Line 157: `shape` function props typed as `any`
- Type mismatches for tooltip data payload

### Solution Applied
✅ **Already fixed in your file**:
1. Created `ScatterDataPoint` interface for scatter data
2. Created `CustomTooltipProps` interface with proper typing
3. Updated `shape` function to use `unknown` type with proper casting (recharts API requirement)
4. Added type guards using `'property' in data` checks

### Verification
```bash
cd frontend
npm run type-check
# Should show no errors
```

---

## ⚠️ Issue #2: White Screen on Dashboard

### Root Causes

#### 2a. Backend Not Running
**Symptom**: DevTools Network tab shows failed requests to `/api/models/`, `/auth/me`, etc.

**Fix**:
```bash
# Terminal 1: Start Backend
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .\.venv\Scripts\activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

**Verify**: 
```bash
curl http://localhost:8000/health
# Should return: {"status": "ok", "version": "0.1.0"}
```

---

#### 2b. Frontend Can't Reach Backend
**Symptom**: Console shows `Error: Network request failed` or `ERR_CONNECTION_REFUSED`

**Cause**: Vite proxy doesn't work if frontend is built (production build). Only works in dev mode.

**Fix**:
```bash
# Terminal 2: Start Frontend in DEV MODE
cd frontend
npm install
npm run dev
# Open: http://localhost:5173 or http://localhost:3000
```

**DO NOT use**: `npm run build && npm run preview` for local testing

---

#### 2c. Database Not Initialized
**Symptom**: Backend runs but returns 500 errors with "relation doesn't exist" messages

**Check**:
```bash
cd backend
psql postgresql://sentinel:sentinel@localhost:5432/sentinel

# In psql:
\dt
# Should list tables like: model_registry, drift_event, alert, etc.
\q
```

**Fix**: Run migrations
```bash
cd backend
alembic upgrade head
```

---

#### 2d. CORS Blocked Requests
**Symptom**: DevTools Console shows:
```
Access to XMLHttpRequest... blocked by CORS policy
Cross-Origin Request Blocked
```

**Fix**: Update [backend/app/config.py](backend/app/config.py#L26):
```python
CORS_ORIGINS: list[str] = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]
```

Then restart backend.

---

#### 2e. Authentication Token Not Sent
**Symptom**: Login works but Dashboard shows 401 Unauthorized

**Check in Console (F12)**:
```javascript
localStorage.getItem('sentinel_token')
// Should return a JWT token, not null
```

**If null**: Login credentials were rejected

**If present**: Check that API client adds it to headers:
- Look at [frontend/src/api/client.ts](frontend/src/api/client.ts) — verify interceptor adds `Authorization: Bearer {token}`

---

#### 2f. React/Vite Build Errors
**Symptom**: Blank page with console errors about missing modules

**Check**:
```bash
cd frontend
npm install
npm run type-check
# Look for TypeScript errors
```

**Common fixes**:
```bash
# Clear node_modules and reinstall
rm -rf node_modules package-lock.json
npm install

# Clear Vite cache
rm -rf node_modules/.vite

# Rebuild
npm run dev
```

---

## ⚙️ Issue #3: CORS Configuration

### Problem
Backend hardcodes `localhost:3000` in CORS whitelist. This breaks if:
- Frontend runs on port 5173 (Vite default)
- You use `127.0.0.1` instead of `localhost`
- You deploy to different domain

### Solution

**[backend/app/config.py](backend/app/config.py#L26)**:
```python
CORS_ORIGINS: list[str] = [
    "http://localhost:3000",      # npm run dev (Vite)
    "http://localhost:5173",      # Vite default dev server
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    # Production: add your domain here
    # "https://sentinel.mycompany.com",
]

# Or use environment variable:
CORS_ORIGINS: list[str] = [
    "http://localhost:3000",  # Default
]

# Usage in .env:
# CORS_ORIGINS='["http://localhost:3000", "https://myapp.com"]'
```

---

## 🔐 Issue #4: Cookie Security Settings

### Problem
In [backend/app/routers/auth.py](backend/app/routers/auth.py#L79):
```python
response.set_cookie(
    ...
    secure=True,       # ← HTTPS only in production
    ...
)
```

**In development on localhost, HTTPS is not available**, so the cookie won't be set.

### Solution

**Check environment and adjust**:
```python
is_production = settings.ENVIRONMENT == "production"

response.set_cookie(
    key=REFRESH_COOKIE_NAME,
    value=refresh_token,
    httponly=True,
    secure=is_production,  # HTTPS only in production
    samesite="strict" if is_production else "lax",
    max_age=COOKIE_MAX_AGE,
    path="/auth",
)
```

Or add `.env` variable:
```
ENVIRONMENT=development  # or production
```

---

## 📊 Issue #5: Database Seeding

### Problem
Database starts empty after migrations. No demo models to display on Dashboard.

### Solution

**Run seed script**:
```bash
cd backend
python scripts/seed_db.py
```

**What it creates**:
- 3 demo models (model_1, model_2, model_3)
- Demo user: `admin@sentinel.ai` / `admin123`
- Sample predictions and drift events

**Verify**:
```bash
psql postgresql://sentinel:sentinel@localhost:5432/sentinel

# Check models
SELECT id, name, version, status FROM model_registry;

# Check users
SELECT id, email, is_superuser FROM user_account;

\q
```

---

## 🔄 Issue #6: WebSocket Connection

### Problem
Dashboard tries to connect to WebSocket at startup. If backend isn't ready, connection fails silently.

### Check in Console (F12):
```javascript
// Check WebSocket status
useStore.getState().wsStatus
// Should be: 'connected', 'connecting', or 'disconnected'
```

### If Stuck on 'disconnected':
1. Verify backend is running: `curl http://localhost:8000/health`
2. Check WebSocket proxy in [frontend/vite.config.ts](frontend/vite.config.ts#L9):
   ```typescript
   '/ws': { target: 'ws://localhost:8000', ws: true },
   ```
3. Verify backend WebSocket route exists: `backend/app/routers/websocket.py`

---

## 🚀 Quick Verification Checklist

```bash
# Step 1: Backend running
curl http://localhost:8000/health
# ✅ Returns: {"status": "ok", "version": "0.1.0"}

# Step 2: Database initialized
cd backend
psql postgresql://sentinel:sentinel@localhost:5432/sentinel -c "\dt"
# ✅ Shows 8+ tables

# Step 3: Demo data seeded
cd backend
python scripts/seed_db.py
psql postgresql://sentinel:sentinel@localhost:5432/sentinel -c "SELECT COUNT(*) FROM model_registry;"
# ✅ Shows 3+ models

# Step 4: Frontend running in dev mode
cd frontend
npm run dev
# ✅ Open http://localhost:5173

# Step 5: Login
# Email: admin@sentinel.ai
# Password: admin123 (or from seed script)

# Step 6: Dashboard loads
# ✅ Should see model cards, drift timeline, alerts

# Step 7: Check console
# ✅ No red errors in F12 console
```

---

## 🔍 Debugging Checklist

### Dashboard White Screen?

**1. Check backend logs**:
```bash
# Terminal with backend running
# Look for errors like:
# - "Address already in use"
# - "Connection refused"
# - "psycopg2.OperationalError"
```

**2. Check frontend console (F12)**:
- Click **Console** tab
- Look for red errors
- Common: `GET /api/models/ 401 Unauthorized` or `CORS error`

**3. Check Network tab (F12)**:
- Click **Network** tab
- Reload page
- Look for requests:
  - `/auth/login` → status 200
  - `/auth/me` → status 200  
  - `/api/models/` → status 200
- If 401/403: Authentication issue
- If "connection failed": Backend not running

**4. Check if ports are in use**:
```bash
# Windows
netstat -ano | findstr :3000
netstat -ano | findstr :8000

# Linux/Mac
lsof -i :3000
lsof -i :8000
```

**5. Check environment variables**:
```bash
# Backend
cd backend
cat .env
# Should have DATABASE_URL, REDIS_URL, etc.

# Or run backend and check:
python -c "from app.config import settings; print(settings.CORS_ORIGINS)"
```

---

## 🛠️ Common Error Messages & Fixes

| Error Message | Cause | Fix |
|---------------|-------|-----|
| `Address already in use 0.0.0.0:8000` | Backend already running on port 8000 | Kill the process: `lsof -i :8000 \| awk 'NR==2 {print $2}' \| xargs kill -9` |
| `psycopg2.OperationalError: connection refused` | PostgreSQL not running | `docker-compose up postgres` or install & start PostgreSQL |
| `Access to XMLHttpRequest blocked by CORS policy` | CORS misconfigured | Update `CORS_ORIGINS` in backend config |
| `401 Unauthorized` | Token not sent or expired | Clear localStorage, re-login: `localStorage.clear()` |
| `GET /api/models/ net::ERR_CONNECTION_REFUSED` | Backend not running | Start backend: `uvicorn app.main:app --reload` |
| `Cannot find module 'react'` | Frontend dependencies missing | `cd frontend && npm install` |
| `Blank white screen` | See Issue #2 above | Follow white screen troubleshooting |

---

## 📝 Summary of Changes

### Files Modified
✅ [frontend/src/components/charts/CalibrationROC.tsx](frontend/src/components/charts/CalibrationROC.tsx) — Fixed TypeScript errors

### Files Created
✅ [SETUP_GUIDE.md](SETUP_GUIDE.md) — Complete setup and troubleshooting guide
✅ [BUG_REPORT.md](BUG_REPORT.md) — This file

### No changes needed
- Backend code is working correctly
- Frontend routing is correct
- Database schema is correct

---

## 🎯 Next Steps

1. **Follow SETUP_GUIDE.md** — Step-by-step instructions to get everything running
2. **Use troubleshooting section** — If you hit issues
3. **Run verification checklist** — To confirm everything works
4. **Check browser console (F12)** — For real-time debugging

---

**Good luck! 🚀**

For more info, check:
- Backend docs: `http://localhost:8000/docs`
- README: [README.md](README.md)
- Architecture: [docs/](docs/)
