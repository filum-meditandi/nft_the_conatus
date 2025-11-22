"""
Database Session Management

Provides SQLAlchemy engine, session factory, and dependency injection
for FastAPI endpoints. Handles connection pooling, session lifecycle,
and proper cleanup.

Usage in FastAPI routes:
    @router.get("/parties")
    def get_parties(db: Session = Depends(get_db)):
        return db.query(Party).all()
"""

import logging
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool, QueuePool

from config import get_settings

logger = logging.getLogger(__name__)


# ============================================================================
# ENGINE CREATION
# ============================================================================

def create_db_engine(database_url: str | None = None) -> Engine:
    """
    Create SQLAlchemy engine with appropriate settings.

    Args:
        database_url: Database URL (defaults to settings.database_url)

    Returns:
        Configured SQLAlchemy engine

    Connection pool configuration:
    - Production: QueuePool with configurable size
    - Testing: NullPool (no connection pooling)
    """
    settings = get_settings()

    url = database_url or settings.get_effective_database_url()

    # Determine pooling strategy
    if settings.testing:
        # No connection pooling in tests (fresh connections)
        poolclass = NullPool
        pool_kwargs = {}
        logger.info("Creating database engine with NullPool (testing mode)")
    else:
        # Production connection pooling
        poolclass = QueuePool
        pool_kwargs = {
            "pool_size": settings.db_pool_size,
            "max_overflow": settings.db_max_overflow,
            "pool_recycle": settings.db_pool_recycle,
            "pool_pre_ping": True,  # Verify connections before using
        }
        logger.info(
            f"Creating database engine with QueuePool "
            f"(size={settings.db_pool_size}, overflow={settings.db_max_overflow})"
        )

    engine = create_engine(
        url,
        poolclass=poolclass,
        echo=settings.db_echo,
        **pool_kwargs,
    )

    # Set up event listeners
    _setup_engine_events(engine)

    return engine


def _setup_engine_events(engine: Engine) -> None:
    """Set up SQLAlchemy event listeners for monitoring and debugging."""

    @event.listens_for(engine, "connect")
    def receive_connect(dbapi_conn, connection_record):
        """Log new database connections."""
        logger.debug("Database connection established")

    @event.listens_for(engine, "checkout")
    def receive_checkout(dbapi_conn, connection_record, connection_proxy):
        """Log connection checkout from pool."""
        logger.debug("Connection checked out from pool")

    @event.listens_for(engine, "checkin")
    def receive_checkin(dbapi_conn, connection_record):
        """Log connection return to pool."""
        logger.debug("Connection returned to pool")


# ============================================================================
# SESSION FACTORY
# ============================================================================

# Global engine and session factory (initialized by init_db)
_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def init_db(database_url: str | None = None) -> None:
    """
    Initialize database engine and session factory.

    Should be called once at application startup.

    Args:
        database_url: Database URL (defaults to settings.database_url)
    """
    global _engine, _SessionLocal

    _engine = create_db_engine(database_url)
    _SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=_engine,
    )

    logger.info("Database initialized successfully")


def get_engine() -> Engine:
    """Get the global database engine."""
    if _engine is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _engine


def get_session_factory() -> sessionmaker:
    """Get the global session factory."""
    if _SessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _SessionLocal


# ============================================================================
# SESSION MANAGEMENT
# ============================================================================

@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """
    Context manager for database sessions.

    Automatically commits on success, rolls back on exception,
    and ensures session is always closed.

    Usage:
        with get_db_session() as db:
            party = db.query(Party).first()
            db.add(new_party)
            # Automatic commit on exit
    """
    SessionLocal = get_session_factory()
    db = SessionLocal()

    try:
        yield db
        db.commit()
    except SQLAlchemyError as e:
        logger.error(f"Database error, rolling back: {e}")
        db.rollback()
        raise
    except Exception as e:
        logger.error(f"Unexpected error, rolling back: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency for database sessions.

    Usage in routes:
        @router.get("/parties")
        def get_parties(db: Session = Depends(get_db)):
            return db.query(Party).all()

    FastAPI automatically handles commit/rollback and session cleanup.
    """
    SessionLocal = get_session_factory()
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


# ============================================================================
# DATABASE LIFECYCLE
# ============================================================================

def create_all_tables() -> None:
    """
    Create all database tables.

    WARNING: This should typically only be used in development/testing.
    In production, use Alembic migrations instead.
    """
    from models import Base

    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    logger.info("All database tables created")


def drop_all_tables() -> None:
    """
    Drop all database tables.

    WARNING: DESTRUCTIVE OPERATION. Only use in development/testing.
    """
    from models import Base

    engine = get_engine()
    Base.metadata.drop_all(bind=engine)
    logger.warning("All database tables dropped")


def reset_database() -> None:
    """
    Reset database (drop and recreate all tables).

    WARNING: DESTRUCTIVE OPERATION. Only use in development/testing.
    """
    logger.warning("Resetting database (dropping and recreating all tables)")
    drop_all_tables()
    create_all_tables()


def close_db() -> None:
    """
    Close database connections and dispose of engine.

    Should be called on application shutdown.
    """
    global _engine, _SessionLocal

    if _engine is not None:
        _engine.dispose()
        _engine = None
        _SessionLocal = None
        logger.info("Database connections closed")


# ============================================================================
# HEALTH CHECK
# ============================================================================

def check_database_health() -> bool:
    """
    Check if database is accessible and responding.

    Returns:
        True if database is healthy, False otherwise
    """
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False


# ============================================================================
# TESTING UTILITIES
# ============================================================================

def get_test_db_session() -> Generator[Session, None, None]:
    """
    Get a database session for testing.

    Creates tables before yielding session, drops them after.
    Use this in pytest fixtures.

    Usage:
        @pytest.fixture
        def db():
            yield from get_test_db_session()
    """
    from models import Base

    engine = get_engine()

    # Create tables
    Base.metadata.create_all(bind=engine)

    # Create session
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestSessionLocal()

    try:
        yield db
    finally:
        db.close()
        # Drop tables
        Base.metadata.drop_all(bind=engine)
