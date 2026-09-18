"""
TradeGuard AI - Main FastAPI application.

Autonomous Multi-Agent Options Trading with Adaptive Risk Protection.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from app.config import settings
from app.utils.logging import setup_logging, get_logger, log_security_event
from app.api.health import router as health_router
from app.api.debate import router as debate_router
from app.api.autonomous import router as autonomous_router
from app.api.portfolio import router as portfolio_router
from app.api.alpaca import router as alpaca_router
from app.api.intelligence import router as intelligence_router
from app.api.demo_auth import router as demo_auth_router
from app.api.analytics import router as analytics_router
from app.api.paper import router as paper_router
from app.api.demo import router as demo_router
from app.api.backtest import router as backtest_router
from app.api.falsification import router as falsification_router
from app.api.volatility import router as volatility_router
from app.api.review import router as review_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    
    Handles startup and shutdown tasks.
    """
    logger = get_logger(__name__)
    
    # Startup
    logger.info(
        "Starting TradeGuard AI",
        version=settings.app_version,
        environment=settings.environment,
        paper_trading=settings.alpaca_paper_trade
    )
    
    # Security validation
    if not settings.alpaca_paper_trade:
        log_security_event(
            "startup_security_violation",
            {"message": "Live trading attempted - blocking startup"},
            "critical"
        )
        raise RuntimeError("SECURITY: Live trading is disabled")
    
    if settings.dry_run is False:
        log_security_event(
            "startup_security_violation",
            {"message": "DRY_RUN must remain true"},
            "critical",
        )
        raise RuntimeError("SECURITY: Dry run is required")

    logger.info("✅ Security validation passed - Paper trading enabled")

    from app.db.session import dialect_name, init_db

    init_db()
    logger.info("Database schema ready", dialect=dialect_name())

    from app.api.autonomous import autonomous_engine
    from app.alpaca.iex_stream import get_iex_hub

    started = await autonomous_engine.start()
    if started:
        logger.info("Autonomous engine started; portfolio monitor initialized")
    else:
        logger.error("Autonomous engine failed to initialize (Alpaca paper connection)")

    await get_iex_hub().start()
    logger.info("IEX market-data stream started")

    logger.info("🚀 TradeGuard AI started successfully")
    
    yield
    
    # Shutdown
    logger.info("🛑 TradeGuard AI shutting down")
    await get_iex_hub().stop()


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    description="Autonomous Multi-Agent Options Trading with Adaptive Risk Protection",
    version=settings.app_version,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan
)

# Setup logging
setup_logging()
logger = get_logger(__name__)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with structured logging."""
    logger.error(
        "HTTP exception",
        status_code=exc.status_code,
        detail=exc.detail,
        path=request.url.path,
        method=request.method
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code,
            "service": settings.app_name
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions with structured logging."""
    logger.error(
        "Unhandled exception",
        error=str(exc),
        type=type(exc).__name__,
        path=request.url.path,
        method=request.method,
        exc_info=True
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "status_code": 500,
            "service": settings.app_name
        }
    )


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all HTTP requests."""
    logger.info(
        "HTTP request",
        method=request.method,
        path=request.url.path,
    )
    
    response = await call_next(request)
    
    logger.info(
        "HTTP response",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code
    )
    
    return response


# Include routers
app.include_router(health_router, tags=["Health"])
app.include_router(
    health_router,
    prefix=settings.api_v1_prefix,
    tags=["Health"]
)
app.include_router(debate_router)
app.include_router(autonomous_router)
app.include_router(portfolio_router)
app.include_router(alpaca_router)
app.include_router(intelligence_router)
app.include_router(demo_auth_router)
app.include_router(analytics_router)
app.include_router(paper_router)
app.include_router(demo_router)
app.include_router(backtest_router)
app.include_router(falsification_router)
app.include_router(volatility_router)
app.include_router(review_router)


@app.get("/")
async def root():
    """
    Root endpoint with basic service information.
    
    Returns:
        dict: Service information and status
    """
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "environment": settings.environment,
        "paper_trading": settings.alpaca_paper_trade,
        "docs_url": "/docs" if settings.debug else "disabled",
        "api_prefix": settings.api_v1_prefix
    }


if __name__ == "__main__":
    import os

    port_env = os.environ.get("PORT")
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0" if port_env else "127.0.0.1",
        port=int(port_env) if port_env else 8001,
        reload=settings.debug and not port_env,
        log_level=settings.log_level.lower()
    )