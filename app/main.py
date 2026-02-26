<<<<<<< Updated upstream
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.exceptions import register_exception_handlers
from app.routers import auth, tenants, districts
from app.routers import roles, users, categories
from app.routers import stocks, orders, reports
from app.routers import set_types, products, seed, shop

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
app.include_router(users.router, prefix=API_PREFIX)
app.include_router(categories.router, prefix=API_PREFIX)
app.include_router(set_types.router, prefix=API_PREFIX)
app.include_router(products.router, prefix=API_PREFIX)
app.include_router(seed.router, prefix=API_PREFIX)
app.include_router(shop.router, prefix=API_PREFIX)
app.include_router(stocks.router, prefix=API_PREFIX)
app.include_router(orders.router, prefix=API_PREFIX)
app.include_router(reports.router, prefix=API_PREFIX)


@app.get("/", tags=["Health"])
async def root():
    return {"status": "success", "message": "vismay-pavos-core is running", "data": {"app": settings.APP_NAME, "version": "1.0.0"}}


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "success", "message": "Service is healthy", "data": []}


=======
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.exceptions import register_exception_handlers
from app.routers import auth, tenants, districts
from app.routers import roles, users, categories
from app.routers import stocks, orders, reports
from app.routers import set_types, products, seed, shop

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
app.include_router(users.router, prefix=API_PREFIX)
app.include_router(categories.router, prefix=API_PREFIX)
app.include_router(set_types.router, prefix=API_PREFIX)
app.include_router(products.router, prefix=API_PREFIX)
app.include_router(seed.router, prefix=API_PREFIX)
app.include_router(shop.router, prefix=API_PREFIX)
app.include_router(stocks.router, prefix=API_PREFIX)
app.include_router(orders.router, prefix=API_PREFIX)
app.include_router(reports.router, prefix=API_PREFIX)


@app.get("/", tags=["Health"])
async def root():
    return {"status": "success", "message": "vismay-pavos-core is running", "data": {"app": settings.APP_NAME, "version": "1.0.0"}}


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "success", "message": "Service is healthy", "data": []}


>>>>>>> Stashed changes
