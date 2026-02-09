"""Indian Loan Analyzer — FastAPI Backend."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.routes import auth, loans, optimizer, scanner, emi, ai_insights, user
from app.api.middleware import RequestLoggingMiddleware, RateLimitMiddleware, GlobalErrorHandler
from app.config import settings

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown hooks."""
    from app.db.session import engine

    # Startup: verify DB connection
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Database connection verified on startup.")
    except Exception as exc:
        logger.error("Database connection failed on startup: %s", exc)

    yield

    # Shutdown: dispose engine
    await engine.dispose()
    logger.info("Database engine disposed on shutdown.")


app = FastAPI(
    title="Indian Loan Analyzer API",
    description="Smart Repayment Optimizer for Indian Loans",
    version="0.1.0",
    lifespan=lifespan,
)

# Middleware (order matters — outermost first)
app.add_middleware(GlobalErrorHandler)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RateLimitMiddleware, max_requests=100, window_seconds=60)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Accept-Language"],
)

# Routers
app.include_router(auth.router)
app.include_router(loans.router)
app.include_router(optimizer.router)
app.include_router(scanner.router)
app.include_router(emi.router)
app.include_router(ai_insights.router)
app.include_router(user.router)


@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "version": "0.1.0"}


@app.get("/api/health/ready")
async def readiness_check():
    """Readiness probe — checks DB connectivity. Used by Azure App Service."""
    from app.db.session import engine

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ready", "version": "0.1.0", "database": True}
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "version": "0.1.0", "database": False},
        )


@app.get("/api/health/startup")
async def startup_check():
    """Startup probe — checks if the users table exists (schema is applied)."""
    from app.db.session import engine

    try:
        async with engine.connect() as conn:
            await conn.execute(text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_name = 'users' LIMIT 1"
            ))
        return {"status": "started", "version": "0.1.0", "schema_ready": True}
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "starting", "version": "0.1.0", "schema_ready": False},
        )
