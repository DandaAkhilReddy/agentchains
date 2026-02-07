"""Indian Loan Analyzer — FastAPI Backend."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, loans, optimizer, scanner, emi, ai_insights
from app.api.middleware import RequestLoggingMiddleware, RateLimitMiddleware, GlobalErrorHandler
from app.config import settings

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Indian Loan Analyzer API",
    description="Smart Repayment Optimizer for Indian Loans",
    version="0.1.0",
)

# Middleware (order matters — outermost first)
app.add_middleware(GlobalErrorHandler)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RateLimitMiddleware, max_requests=100, window_seconds=60)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router)
app.include_router(loans.router)
app.include_router(optimizer.router)
app.include_router(scanner.router)
app.include_router(emi.router)
app.include_router(ai_insights.router)


@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "version": "0.1.0"}


@app.get("/api/health/ready")
async def readiness_check():
    """Readiness probe — checks DB connectivity. Used by Azure App Service."""
    from app.db.session import engine

    try:
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    status = "ready" if db_ok else "degraded"
    return {"status": status, "version": "0.1.0", "database": db_ok}
