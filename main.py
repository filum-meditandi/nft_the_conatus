"""
Phenomenological Evidence System - Main Application

FastAPI application entry point. Configures the API server, middleware,
routers, and lifecycle hooks.

Run with:
    uvicorn main:app --reload                    # Development
    uvicorn main:app --host 0.0.0.0 --port 8000  # Production
"""

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from config import get_settings
from database import init_db, close_db, check_database_health

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# ============================================================================
# APPLICATION LIFECYCLE
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Handles startup and shutdown events:
    - Startup: Initialize database, validate configuration
    - Shutdown: Close database connections, cleanup resources
    """
    settings = get_settings()

    # ========================================
    # STARTUP
    # ========================================
    logger.info("=" * 70)
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.environment}")
    logger.info("=" * 70)

    # Initialize database
    logger.info("Initializing database connection...")
    try:
        init_db()
        if check_database_health():
            logger.info("✓ Database connection healthy")
        else:
            logger.error("✗ Database connection failed")
            raise RuntimeError("Database health check failed")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

    # Validate critical configuration
    logger.info("Validating configuration...")
    if settings.is_production:
        if not settings.master_encryption_key:
            raise RuntimeError("MASTER_ENCRYPTION_KEY required in production")
        if settings.debug:
            logger.warning("⚠ DEBUG=true in production environment!")
        logger.info("✓ Production configuration validated")
    else:
        logger.info("✓ Development configuration loaded")

    # Log feature flags
    logger.info("Feature flags:")
    logger.info(f"  - SMS Enabled: {settings.sms_enabled}")
    logger.info(f"  - HMM Inference: {settings.hmm_enabled}")
    logger.info(f"  - Voice Input: {settings.feature_voice_input}")
    logger.info(f"  - NFT Minting: {settings.feature_nft_minting}")
    logger.info(f"  - Intentionality Bridge: {settings.feature_intentionality_bridge}")

    logger.info("Application startup complete")
    logger.info("=" * 70)

    yield

    # ========================================
    # SHUTDOWN
    # ========================================
    logger.info("Shutting down application...")
    close_db()
    logger.info("Application shutdown complete")


# ============================================================================
# APPLICATION CREATION
# ============================================================================

def create_app() -> FastAPI:
    """
    Create and configure FastAPI application.

    Returns:
        Configured FastAPI application instance
    """
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="""
        Phenomenological Evidence System - Cryptographically verified lived experience
        documentation for legal use.

        This API enables plaintiffs to submit pain reports and perspective notes via
        SMS or web interface, which are then cryptographically chained into an
        immutable attestation ledger with proper PHI separation.

        Key features:
        - Accessible SMS-based pain reporting
        - Cryptographic attestation chains
        - PHI separation and encryption
        - Hidden Markov Model pain trajectory inference
        - NFT-based proof generation
        """,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # ========================================
    # MIDDLEWARE
    # ========================================

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Trusted Host (production security)
    if settings.is_production:
        # Add your production domains here
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=["*.yourdomain.com", "yourdomain.com"]
        )

    # ========================================
    # EXCEPTION HANDLERS
    # ========================================

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Global exception handler for unhandled errors."""
        logger.error(f"Unhandled exception: {exc}", exc_info=True)

        # Don't expose internal errors in production
        if settings.is_production:
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Internal server error"},
            )
        else:
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": str(exc), "type": type(exc).__name__},
            )

    # ========================================
    # ROUTERS
    # ========================================

    # Import routers
    from routes import router as phenomenology_router
    from twilio_handler import router as twilio_router

    # Include routers
    app.include_router(phenomenology_router, prefix=settings.api_prefix)
    app.include_router(twilio_router, prefix=settings.api_prefix)

    # ========================================
    # HEALTH CHECK
    # ========================================

    @app.get("/health", tags=["monitoring"])
    async def health_check():
        """
        Health check endpoint.

        Returns:
            System health status including database connectivity
        """
        db_healthy = check_database_health()

        return {
            "status": "healthy" if db_healthy else "unhealthy",
            "version": settings.app_version,
            "environment": settings.environment,
            "database": "connected" if db_healthy else "disconnected",
        }

    @app.get("/", tags=["root"])
    async def root():
        """Root endpoint with API information."""
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "description": "Phenomenological Evidence System",
            "docs": "/docs" if not settings.is_production else None,
        }

    return app


# ============================================================================
# APPLICATION INSTANCE
# ============================================================================

app = create_app()


# ============================================================================
# CLI ENTRYPOINT
# ============================================================================

def main():
    """
    Main entry point for running the server via CLI.

    Usage:
        python main.py
        OR
        conatus-server  (if installed via pip)
    """
    import uvicorn

    settings = get_settings()

    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.is_development,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
