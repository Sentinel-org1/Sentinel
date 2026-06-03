# ⚡ Sentinel — Quick Start Reference Card

## 🚀 5-Minute Quick Start (Docker)

```bash
cd infra
docker-compose up -d

# Wait 30 seconds for services to start
sleep 30

# Open browser: http://localhost:3000
# Login: admin@sentinel.ai / admin123
```

---

## 🛠️ Local Development (Manual Setup)

### Terminal 1: Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .\.venv\Scripts\activate
pip install -e ".[dev]"
alembic upgrade head               # Initialize database
python scripts/seed_db.py           # Load demo data
uvicorn app.main:app --reload
# Ready: http://localhost:8000
```

### Terminal 2: Frontend
```bash
cd frontend
npm install
npm run dev
# Ready: http://localhost:5173
```

### Terminal 3: Celery Worker (Background Tasks)
```bash
cd backend
source .venv/bin/activate
celery -A app.tasks.celery_app worker --loglevel=info --concurrency=4
```

### Terminal 4: Celery Beat (Scheduled Tasks)
```bash
cd backend
source .venv/bin/activate
celery -A app.tasks.celery_app beat --loglevel=info
```

---

## 🔑 Default Login Credentials

| Field | Value |
|-------|-------|
| **Email** | `admin@sentinel.ai` |
| **Password** | `admin123` |

---

## 📍 Service URLs

| Service | URL | Purpose |
|---------|-----|---------|
| Frontend | `http://localhost:3000` | Dashboard, UI |
| Backend | `http://localhost:8000` | API |
| API Docs | `http://localhost:8000/docs` | Swagger documentation |
| Health Check | `http://localhost:8000/health` | Service status |
| ReDoc | `http://localhost:8000/redoc` | ReDoc documentation |

---

## 🔍 Debugging: Is Everything Running?

```bash
# Backend health check
curl http://localhost:8000/health

# Frontend check (should return HTML)
curl http://localhost:3000

# Database check
psql postgresql://sentinel:sentinel@localhost:5432/sentinel -c "\dt"

# See all services (Docker)
docker-compose ps
```

---

## 🆘 White Screen? Follow This:

**1. Backend running?**
```bash
curl http://localhost:8000/health
# If fails → start backend
```

**2. Frontend in dev mode?**
```bash
# Check if running on :5173 or :3000
# DO NOT use: npm run build
# DO use: npm run dev
```

**3. Database initialized?**
```bash
cd backend && alembic upgrade head
```

**4. Demo data loaded?**
```bash
cd backend && python scripts/seed_db.py
```

**5. Check browser console (F12)**
- Look for red errors
- Check Network tab for failed requests

---

## 📦 Docker Useful Commands

```bash
# Start everything
docker-compose up -d

# View logs (follow in real-time)
docker-compose logs -f backend
docker-compose logs -f frontend

# Stop everything
docker-compose down

# Remove everything including volumes
docker-compose down -v

# Rebuild containers
docker-compose build --no-cache
docker-compose up -d

# Check service status
docker-compose ps

# Execute command in running container
docker-compose exec backend python scripts/seed_db.py
docker-compose exec backend psql postgresql://sentinel:sentinel@localhost:5432/sentinel -c "\dt"
```

---

## 🗄️ Database Commands

```bash
# Connect to database
psql postgresql://sentinel:sentinel@localhost:5432/sentinel

# List tables
\dt

# List databases
\l

# Describe table
\d model_registry

# Quit
\q

# Reset entire database (⚠️ destructive)
cd backend
alembic downgrade base
alembic upgrade head
python scripts/seed_db.py
```

---

## 📊 API Endpoints (Quick Reference)

### Auth
```bash
POST   /auth/login        # Get access token
GET    /auth/me           # Current user info
POST   /auth/refresh      # Refresh token
POST   /auth/logout       # Logout
```

### Models
```bash
GET    /api/models        # List all models
POST   /api/models        # Register new model
GET    /api/models/{id}   # Get model details
PATCH  /api/models/{id}   # Update model
DELETE /api/models/{id}   # Archive model
```

### Predictions & Drift
```bash
POST   /api/predictions/ingest    # Send predictions
GET    /api/drift                 # Get drift events
GET    /api/alerts                # Get alerts
POST   /api/models/{id}/baseline  # Upload baseline
```

---

## 🔧 Environment Variables

Create `backend/.env`:
```
DATABASE_URL=postgresql+asyncpg://sentinel:sentinel@localhost:5432/sentinel
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
SECRET_KEY=your-secret-key-here
ENVIRONMENT=development
CORS_ORIGINS=["http://localhost:3000", "http://localhost:5173"]
API_HOST=0.0.0.0
API_PORT=8000
```

---

## 🎯 Common Tasks

### Seed Database with Demo Data
```bash
cd backend
python scripts/seed_db.py
```

### Run Unit Tests
```bash
# Backend
cd backend && pytest tests/unit/ -v

# Frontend
cd frontend && npm run test
```

### Check TypeScript Errors
```bash
cd frontend
npm run type-check
```

### View API Documentation
```
http://localhost:8000/docs      # Swagger UI
http://localhost:8000/redoc     # ReDoc
```

### Export Database Backup
```bash
pg_dump postgresql://sentinel:sentinel@localhost:5432/sentinel > backup.sql
```

### Restore Database Backup
```bash
psql postgresql://sentinel:sentinel@localhost:5432/sentinel < backup.sql
```

---

## 📚 File Structure

```
Sentinel/
├── backend/                # FastAPI + SQLAlchemy
│   ├── app/
│   │   ├── main.py        # FastAPI app + middleware
│   │   ├── config.py      # Settings
│   │   ├── routers/       # API endpoints
│   │   ├── models/        # SQLAlchemy ORM models
│   │   ├── services/      # Business logic
│   │   └── tasks/         # Celery tasks
│   ├── migrations/        # Alembic migrations
│   └── scripts/           # Seed, demo scripts
│
├── frontend/              # React + TypeScript + Vite
│   ├── src/
│   │   ├── pages/         # Dashboard, Login, etc.
│   │   ├── components/    # UI components
│   │   ├── api/           # API client
│   │   └── store/         # Zustand state
│   ├── vite.config.ts     # Vite configuration
│   └── tailwind.config.ts # Tailwind CSS
│
├── infra/                 # Docker & K8s
│   ├── docker-compose.yml
│   ├── postgres/          # DB init scripts
│   └── k8s/               # Kubernetes manifests
│
├── ml/                    # ML models & notebooks
│   ├── models/            # Trained models
│   └── notebooks/         # Jupyter notebooks
│
└── docs/                  # Documentation
```

---

## 💡 Pro Tips

1. **Use Docker for clean start**: `docker-compose down -v && docker-compose up -d`
2. **Check logs while developing**: `docker-compose logs -f backend`
3. **Browser DevTools is your friend**: F12 → Console + Network tabs
4. **Clear cache if stuck**: `localStorage.clear()` in browser console
5. **Restart everything if uncertain**: `docker-compose restart`

---

**Still stuck?** Read [SETUP_GUIDE.md](SETUP_GUIDE.md) or [BUG_REPORT.md](BUG_REPORT.md) for detailed troubleshooting.
