"""
Pytest Configuration and Fixtures

Provides reusable fixtures for testing the Phenomenological Evidence System.
"""

import pytest
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from fastapi.testclient import TestClient

from config import Settings, get_settings
from database import init_db, close_db
from models import Base
from main import create_app


# ============================================================================
# TEST SETTINGS
# ============================================================================

@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """
    Create test-specific settings.

    Override default settings with test-specific values.
    """
    return Settings(
        testing=True,
        environment="development",
        debug=True,
        database_url="sqlite:///./test.db",  # In-memory SQLite for tests
        sms_enabled=False,  # Disable SMS in tests
        hmm_enabled=True,
    )


# ============================================================================
# DATABASE FIXTURES
# ============================================================================

@pytest.fixture(scope="session")
def engine(test_settings):
    """
    Create a test database engine.

    Uses SQLite in-memory database for fast tests.
    """
    return create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        echo=False,
    )


@pytest.fixture(scope="session")
def tables(engine):
    """
    Create all database tables for testing.

    Creates tables once per session, drops them after all tests complete.
    """
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(engine, tables) -> Generator[Session, None, None]:
    """
    Provide a transactional database session for each test.

    Each test gets a fresh session that is rolled back after the test completes,
    ensuring test isolation.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection)()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


# ============================================================================
# API CLIENT FIXTURES
# ============================================================================

@pytest.fixture
def app(test_settings, monkeypatch):
    """
    Create FastAPI app for testing.

    Overrides settings with test-specific configuration.
    """
    # Override get_settings to return test settings
    monkeypatch.setattr("config.get_settings", lambda: test_settings)
    monkeypatch.setattr("main.get_settings", lambda: test_settings)

    # Initialize database for testing
    init_db("sqlite:///:memory:")

    app = create_app()

    yield app

    # Cleanup
    close_db()


@pytest.fixture
def client(app) -> TestClient:
    """
    Provide a test client for making API requests.

    Usage:
        def test_endpoint(client):
            response = client.get("/health")
            assert response.status_code == 200
    """
    return TestClient(app)


# ============================================================================
# MODEL FIXTURES
# ============================================================================

@pytest.fixture
def sample_party(db_session):
    """Create a sample Party for testing."""
    from models import Party, PartyRole
    from uuid import uuid4

    party = Party(
        id=uuid4(),
        role=PartyRole.PLAINTIFF,
        name="Test Plaintiff",
        email="plaintiff@example.com",
    )
    db_session.add(party)
    db_session.commit()
    return party


@pytest.fixture
def sample_persona(db_session, sample_party):
    """Create a sample PersonaToken for testing."""
    from models import PersonaToken
    from uuid import uuid4

    persona = PersonaToken(
        id=uuid4(),
        party_id=sample_party.id,
        key_type="ed25519",
        public_key=b"test_public_key",
        private_key=b"test_private_key",
    )
    db_session.add(persona)
    db_session.commit()
    return persona


# ============================================================================
# CRYPTOGRAPHY FIXTURES
# ============================================================================

@pytest.fixture
def encryption_service():
    """Provide an EncryptionService for testing."""
    from phi_separation import EncryptionService
    from cryptography.fernet import Fernet

    # Generate a test master key
    master_key = Fernet.generate_key()
    return EncryptionService(master_key.decode())


@pytest.fixture
def signing_service():
    """Provide a SigningService for testing."""
    from signing_infrastructure import SigningService

    return SigningService()


# ============================================================================
# MARKERS
# ============================================================================

# Register custom markers (defined in pyproject.toml)
def pytest_configure(config):
    """Register custom pytest markers."""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "crypto: Cryptography tests")
    config.addinivalue_line("markers", "database: Database tests")
    config.addinivalue_line("markers", "api: API endpoint tests")
