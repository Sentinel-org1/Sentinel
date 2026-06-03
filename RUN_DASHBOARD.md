# 🎯 How to Run Sentinel & See the Dashboard

## The Problem You're Experiencing

**White screen when opening browser** → This means the frontend loads but the Dashboard content doesn't render. Causes:
1. Backend not running or unreachable
2. Database not initialized
3. Authentication failed
4. API call failed (see console errors)
5. Vite proxy not configured correctly

---

## ✅ Solution: Step-by-Step to Working Dashboard

### **Option A: Docker Compose (Easiest - 2 minutes)**

#### Step 1: Start Everything
```bash
cd infra
docker-compose up -d
```

#### Step 2: Wait for Services to Be Ready
```bash
# Check if all services are running
docker-compose ps

# All should show "Up" status. If any show "Exited", check logs:
docker-compose logs backend
docker-compose logs frontend
```

#### Step 3: Verify Backend is Ready
```bash
curl http://localhost:8000/health

# Expected response:
# {"status": "ok", "version": "0.1.0"}
```

#### Step 4: Open Browser
- Go to: **http://localhost:3000**
- Login with:
  - Email: `admin@sentinel.ai`
  - Password: `admin123`

#### Step 5: Dashboard Should Load
You should now see:
- ✅ Model cards on the left (showing registered models)
- ✅ Drift timeline in the center
- ✅ Alert bell in top right
- ✅ WebSocket status indicator

**If still white screen → Jump to [Troubleshooting](#troubleshooting) section below**

---

### **Option B: Local Development (5 minutes - Better for Debugging)**

This approach helps you see exactly where things fail. Use 4 terminal windows.

#### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL 15+ running (or use Docker just for DB)
- Redis running (or use Docker just for Redis)

#### Terminal 1: Start PostgreSQL (if not already running)
```bash
# Option 1: Use Docker just for the database
docker run --name sentinel-postgres -e POSTGRES_PASSWORD=sentinel -e POSTGRES_USER=sentinel -e POSTGRES_DB=sentinel -p 5433:5432 -d postgres:15-alpine

# Option 2: Use existing PostgreSQL
# Make sure it's running and database "sentinel" exists
createdb -U sentinel sentinel
```

#### Terminal 2: Start Redis (if not already running)
```bash
# Option 1: Use Docker just for Redis
docker run --name sentinel-redis -p 6379:6379 -d redis:7-alpine

# Option 2: Use existing Redis
# Make sure it's running on port 6379
redis-cli ping  # Should return: PONG
```

#### Terminal 3: Start Backend
```bash
cd backend

# Create virtual environment
python -m venv .venv

# Activate it
# Windows:
.\.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Initialize database (run migrations)
alembic upgrade head

# Load demo data
python scripts/seed_db.py

# Start the backend server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Expected output**:
```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete [uvicorn]
INFO:     Uvicorn running on http://0.0.0.0:8000
```

✅ Backend is ready when you see the last line.

#### Terminal 4: Start Frontend
```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

**Expected output**:
```
  VITE v5.0.0  ready in 123 ms

  ➜  Local:   http://localhost:5173/
  ➜  press h to show help
```

#### Step 5: Open Browser
- **Primary**: http://localhost:5173 (Vite dev server)
- **Alternative**: http://localhost:3000 (if you configured it that way)

#### Step 6: Login & See Dashboard
1. You should see **Login Page** with:
   - Sentinel logo
   - Email & password inputs
   - Sign In button

2. Enter credentials:
   - Email: `admin@sentinel.ai`
   - Password: `admin123`

3. Click "Sign In"

4. After successful login, you should see **Dashboard** with:
   - 📊 **Model Health Cards** (left side) — showing your 3 demo models
   - 📈 **Drift Event Timeline** (center) — showing recent drift detection events
   - 🔔 **Alert Bell** (top right) — showing unread alerts count
   - 🟢 **WebSocket Status** — shows "CONNECTED" (green)

---

## 🔍 Troubleshooting: White Screen Solutions

### **Problem 1: Nothing loads, completely blank page**

**Check #1: Browser can reach frontend**
```bash
# In browser console (F12):
console.log(window.location)
# Should show: http://localhost:3000 or http://localhost:5173
```

**Check #2: No JavaScript errors**
- Open F12 → **Console** tab
- Look for red errors
- Common: `Uncaught Error: Root element #root not found`
  - Fix: Check `frontend/index.html` has `<div id="root"></div>`

**Check #3: Vite dev server running**
```bash
# In frontend terminal, should show:
# ➜  Local:   http://localhost:5173/
```

---

### **Problem 2: Login page loads, but can't login**

**Error: "Invalid email or password"**
- Check you're using: `admin@sentinel.ai` and `admin123` (case-sensitive)
- If still fails, re-seed the database:
  ```bash
  cd backend
  python scripts/seed_db.py
  ```

**Error: "Network error" or "Could not connect to server"**
1. Check backend is running:
   ```bash
   curl http://localhost:8000/health
   ```
   - If fails → Start backend in Terminal 3

2. Check CORS is configured:
   ```bash
   # In backend terminal, should see:
   # CORSMiddleware: add_middleware CORSMiddleware
   ```

3. Check API proxy (if using dev server):
   ```bash
   # In browser console (F12):
   fetch('http://localhost:8000/health').then(r => r.json()).then(console.log)
   # Should return: {status: "ok", version: "0.1.0"}
   ```

---

### **Problem 3: Login works, but Dashboard shows white screen**

**Check #1: Backend API responding**
- Open F12 → **Network** tab
- Reload the page
- Look for requests:
  - `GET /api/models/` → should be 200 ✅
  - `GET /api/drift/` → should be 200 ✅
  - `GET /api/alerts/` → should be 200 ✅

**If seeing 401 Unauthorized**:
- Token not sent or expired
- Check console: `localStorage.getItem('sentinel_token')`
- Should return a JWT token (long string starting with `eyJ`)
- If empty: Re-login
- If present: Check that API client is sending it

**If seeing 500 Internal Server Error**:
- Backend crashed or database issue
- Check backend terminal for error
- Common: "relation model_registry does not exist"
  - Fix: Run migrations: `alembic upgrade head`

**Check #2: Models exist in database**
```bash
# In backend terminal or psql:
psql postgresql://sentinel:sentinel@localhost:5432/sentinel
SELECT id, name, status FROM model_registry;
# Should return 3 demo models

# If empty, seed the data:
python scripts/seed_db.py
```

**Check #3: No TypeScript errors**
```bash
cd frontend
npm run type-check
```
- Should show no errors

**Check #4: Check browser console for errors**
- F12 → Console tab
- Look for red text
- Common: `Cannot read property 'map' of undefined`
  - This means API returned empty/null instead of array

---

### **Problem 4: Dashboard partially loads but components are missing**

**Check #1: All required components exist**
```bash
ls frontend/src/components/
# Should have: ModelHealthCard.tsx, DriftEventTimeline.tsx, etc.
```

**Check #2: No module import errors**
- F12 → Console tab
- Look for: `Cannot find module 'xyz'`
- Fix: `cd frontend && npm install`

**Check #3: Styles not loading (everything is unstyled)**
- Check Tailwind CSS:
  ```bash
  cd frontend
  npm run build
  # Check if build succeeds
  ```

---

### **Problem 5: WebSocket shows "DISCONNECTED" (red)**

This doesn't block functionality but means real-time alerts won't work.

**Check #1: Backend WebSocket server running**
```bash
# Should see in backend terminal:
# "WebSocket" or "application_startup"
```

**Check #2: WebSocket proxy configured**
- In `frontend/vite.config.ts`:
  ```typescript
  '/ws': { target: 'ws://localhost:8000', ws: true }
  ```
  - This only works in dev mode, not in production build

**Check #3: Try connecting manually**
```bash
# In browser console:
new WebSocket('ws://localhost:8000/ws')
# Should show connection attempt in backend logs
```

---

## 🚨 Emergency Reset (Nuclear Option)

If everything is broken and you want to start fresh:

```bash
# Stop and remove everything
docker-compose down -v

# Delete database file (if using local PostgreSQL)
rm -rf /var/lib/postgresql/sentinel

# Clear frontend cache
cd frontend
rm -rf node_modules .vite
npm install

# Start fresh
cd infra
docker-compose up -d
```

---

## ✅ Verification: Dashboard Should Have These Elements

Once everything is working, you should see:

### Top Bar
- [ ] Sentinel logo/title (left)
- [ ] Alert bell icon (right) — red dot if unread alerts
- [ ] User profile dropdown (right)

### Left Sidebar
- [ ] Navigation: Dashboard, Models Registry, Alerts, Calibration
- [ ] Dashboard selected (active/highlighted)
- [ ] User info at bottom with logout button

### Main Content
- [ ] **KPI Cards** (top): Model count, critical alerts, connection status
- [ ] **Model Health Cards** (left section): 
  - 3 cards labeled "model_1", "model_2", "model_3"
  - Each showing: status, predictions count, last drift detection
- [ ] **Drift Event Timeline** (right section):
  - Graph showing drift events over time
  - Or "No drift events" message if no data
- [ ] **Alert Section** (bottom):
  - List of recent alerts or "No alerts" message

---

## 🎯 Next Steps After Getting Dashboard Working

1. **Upload a Baseline Dataset**
   - Go to "Models Registry" → select a model → upload baseline CSV

2. **Send Predictions**
   - Use API: `POST /api/predictions/ingest`
   - Trigger drift detection

3. **Monitor Drift**
   - Go to "Calibration" to see drift detection results
   - Set custom thresholds

4. **Set Up Alerts**
   - Go to "Alerts" to see alerts and manage status

---

## 📞 Still Stuck?

1. **Check detailed guides**:
   - [SETUP_GUIDE.md](SETUP_GUIDE.md) — Comprehensive setup
   - [BUG_REPORT.md](BUG_REPORT.md) — Issue diagnosis
   - [QUICK_START.md](QUICK_START.md) — Command reference

2. **Collect diagnostic info**:
   ```bash
   # Backend logs
   docker-compose logs backend > backend.log
   
   # Frontend logs (browser console F12)
   # Copy and save
   
   # Check services
   docker-compose ps
   
   # Share these logs for debugging
   ```

3. **Common fixes**:
   - Restart services: `docker-compose restart`
   - Clear cache: `docker-compose down -v && docker-compose up -d`
   - Check ports: `netstat -ano | findstr :3000 && netstat -ano | findstr :8000`

---

**Good luck! 🚀 You should see your Dashboard now!**
