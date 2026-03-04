from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.exceptions import register_exception_handlers
from app.routers import auth, tenants, districts, users
from app.routers import roles, permissions, seed
# add after health check routes

app = FastAPI(
    title=settings.APP_NAME,
    description="Multi-tenant backend API for Vismay — manages tenants, users, roles, permissions, products and more.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─── CORS ─────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Exception Handlers ────────────────────────────────────────────────────
register_exception_handlers(app)

# ─── Routers ───────────────────────────────────────────────────────────────
API_PREFIX = "/api/v1"

app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(tenants.router, prefix=API_PREFIX)
app.include_router(districts.router, prefix=API_PREFIX)
app.include_router(roles.router, prefix=API_PREFIX)
app.include_router(permissions.router, prefix=API_PREFIX)
app.include_router(seed.router, prefix=API_PREFIX)
app.include_router(users.router, prefix=API_PREFIX)


@app.get("/", tags=["Health"])
async def root():
    return {
        "status": "success",
        "message": "vismay-pavos-core is running",
        "data": {
            "app": settings.APP_NAME,
            "version": "1.0.0",
            f"settings": vars(settings)
        }
    }


@app.get("/health", tags=["Health"])
async def health():
    return {
        "status": "success",
        "message": "Service is healthy",
        "data": []
    }
