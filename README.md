# vismay-pavos-core

Production-grade multi-tenant REST API built with **FastAPI 0.115** and **Python 3.12**.

---

## Stack
| | |
|---|---|
| Framework | FastAPI |
| Database | PostgreSQL 16 |
| ORM | SQLAlchemy 2.x (async) |
| Migrations | Alembic |
| Auth | JWT (access + refresh tokens) |
| Validation | Pydantic v2 |
| Deploy | Docker / docker-compose |

---

## Quick Start (Local)

### 1. Clone & setup env
```bash
cp .env.example .env
# Edit .env and set your DATABASE_URL, SECRET_KEY etc.
```

### 2. Install dependencies
```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Run PostgreSQL (or use Docker)
```bash
docker-compose up -d postgres
```

### 4. Run migrations
```bash
alembic upgrade head
```

### 5. Seed initial data
```bash
python seed.py
```
This creates:
- 4 sample tenants (CHANNEL_FASHION, CHANNEL_INTIMATES, SIS, SOR)
- 4 sample districts
- System roles (super_admin, admin, distributor, executive)
- Super Admin user: `superadmin@vismay.com` / `Admin@1234`

### 6. Start the API
```bash
uvicorn app.main:app --reload
```

API docs: http://localhost:8000/docs

---

## Docker (Full Stack)
```bash
cp .env.example .env
docker-compose up --build
```
- App: http://localhost:8000/docs
- pgAdmin: http://localhost:5050 (admin@vismay.com / admin123)

---

## API Endpoints

All endpoints are prefixed with `/api/v1`.

| Group | Prefix | Methods |
|---|---|---|
| Auth | `/auth` | POST login, refresh, logout · GET me |
| Tenants | `/tenants` | CRUD |
| Districts | `/districts` | CRUD |
| Roles | `/roles` | CRUD + assign permissions |
| Permissions | `/permissions` | CRUD |
| Users | `/users` | CRUD |
| Categories | `/categories` | CRUD |
| Set Types | `/set-types` | CRUD |
| Products | `/products` | CRUD |

---

## Project Layout

```
app/
├── main.py          # FastAPI entry + router registration
├── config.py        # pydantic-settings
├── database.py      # async engine + Base
├── dependencies.py  # auth / role guards
├── core/
│   ├── security.py  # JWT + password hash
│   └── exceptions.py
├── models/          # SQLAlchemy ORM models
├── schemas/         # Pydantic v2 schemas
└── routers/         # FastAPI APIRouters
alembic/             # Migrations
seed.py              # DB seeder
```

---

## Creating an Alembic Migration
```bash
alembic revision --autogenerate -m "describe your change"
alembic upgrade head
```
