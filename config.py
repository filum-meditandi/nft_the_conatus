"""
Configuration Management

Loads configuration from environment variables using Pydantic Settings.
Supports multiple environments (development, staging, production) with
appropriate defaults and validation.

Security considerations:
- Secrets loaded from environment only (never committed)
- Master encryption keys must be 32 bytes (Fernet requirement)
- Database URLs validated for proper formatting
- Twilio credentials required for SMS functionality
"""

import secrets
from functools import lru_cache
from typing import Optional

from pydantic import Field, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ========================================================================
    # APPLICATION
    # ========================================================================

    app_name: str = "Phenomenological Evidence System"
    app_version: str = "0.1.0"
    environment: str = Field(default="development", pattern="^(development|staging|production)$")
    debug: bool = Field(default=True)

    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_prefix: str = "/api/v1"

    # CORS
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"],
        description="Allowed CORS origins (comma-separated in env)"
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    # ========================================================================
    # DATABASE
    # ========================================================================

    database_url: PostgresDsn = Field(
        default="postgresql://conatus:conatus@localhost:5432/phenomenological_evidence",
        description="PostgreSQL connection URL"
    )

    # Connection pool settings
    db_pool_size: int = Field(default=5, ge=1, le=50)
    db_max_overflow: int = Field(default=10, ge=0, le=50)
    db_pool_recycle: int = Field(default=3600, ge=60)  # seconds
    db_echo: bool = Field(default=False, description="Log all SQL queries")

    # ========================================================================
    # CRYPTOGRAPHY
    # ========================================================================

    # Master encryption key for PHI (Fernet symmetric encryption)
    # MUST be 32 URL-safe base64-encoded bytes
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    master_encryption_key: str = Field(
        default="",
        description="Master key for encrypting PHI (32-byte Fernet key)"
    )

    # Signing key for attestation chains (Ed25519 private key)
    # Generate with: python -c "from cryptography.hazmat.primitives.asymmetric import ed25519; print(ed25519.Ed25519PrivateKey.generate())"
    server_signing_key: Optional[str] = Field(
        default=None,
        description="Server's Ed25519 private key for signing attestations"
    )

    # Key rotation
    allow_key_rotation: bool = Field(default=False)
    previous_master_keys: list[str] = Field(
        default=[],
        description="Previous master keys for decrypting old data"
    )

    @field_validator("previous_master_keys", mode="before")
    @classmethod
    def parse_previous_keys(cls, v):
        if isinstance(v, str):
            return [key.strip() for key in v.split(",") if key.strip()]
        return v

    @field_validator("master_encryption_key")
    @classmethod
    def validate_master_key(cls, v):
        if not v:
            # In development, generate a temporary key with warning
            import warnings
            warnings.warn(
                "MASTER_ENCRYPTION_KEY not set. Using temporary key. "
                "DO NOT USE IN PRODUCTION!",
                RuntimeWarning
            )
            from cryptography.fernet import Fernet
            return Fernet.generate_key().decode()

        # Validate it's a valid Fernet key (32 bytes base64)
        try:
            from cryptography.fernet import Fernet
            Fernet(v.encode())
        except Exception as e:
            raise ValueError(f"Invalid master encryption key: {e}")

        return v

    # ========================================================================
    # TWILIO (SMS)
    # ========================================================================

    twilio_account_sid: str = Field(default="", description="Twilio Account SID")
    twilio_auth_token: str = Field(default="", description="Twilio Auth Token")
    twilio_phone_number: str = Field(
        default="",
        description="Twilio phone number in E.164 format (+1234567890)"
    )

    # SMS Configuration
    sms_enabled: bool = Field(default=True)
    sms_rate_limit_per_hour: int = Field(default=100, ge=1)

    @field_validator("twilio_phone_number")
    @classmethod
    def validate_phone_number(cls, v):
        if v and not v.startswith("+"):
            raise ValueError("Twilio phone number must be in E.164 format (+1234567890)")
        return v

    # ========================================================================
    # SECURITY
    # ========================================================================

    # Session/JWT settings (if implementing authentication)
    secret_key: str = Field(
        default_factory=lambda: secrets.token_urlsafe(32),
        description="Secret key for session management"
    )

    # Rate limiting
    rate_limit_enabled: bool = True
    rate_limit_requests: int = Field(default=100, ge=1)
    rate_limit_window: int = Field(default=60, ge=1)  # seconds

    # HIPAA/PHI Settings
    phi_encryption_required: bool = Field(
        default=True,
        description="Require encryption for all PHI data"
    )
    audit_log_enabled: bool = Field(
        default=True,
        description="Enable audit logging for PHI access"
    )

    # ========================================================================
    # HMM INFERENCE
    # ========================================================================

    hmm_enabled: bool = Field(default=True, description="Enable HMM pain trajectory inference")
    hmm_min_observations: int = Field(default=5, ge=3, description="Minimum observations for HMM")
    hmm_state_count: int = Field(default=4, ge=2, description="Number of latent states")

    # ========================================================================
    # LOGGING
    # ========================================================================

    log_level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    log_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    log_file: Optional[str] = Field(default=None, description="Log file path (if file logging)")

    # ========================================================================
    # TESTING
    # ========================================================================

    testing: bool = Field(default=False, description="Enable testing mode")
    test_database_url: Optional[PostgresDsn] = Field(
        default=None,
        description="Separate database for testing"
    )

    # ========================================================================
    # FEATURE FLAGS
    # ========================================================================

    feature_voice_input: bool = Field(default=False, description="Enable voice input processing")
    feature_nft_minting: bool = Field(default=False, description="Enable NFT minting")
    feature_intentionality_bridge: bool = Field(
        default=False,
        description="Enable intentionality ledger bridge"
    )

    # ========================================================================
    # HELPERS
    # ========================================================================

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"

    @property
    def database_url_str(self) -> str:
        """Get database URL as string."""
        return str(self.database_url)

    def get_effective_database_url(self) -> str:
        """Get the appropriate database URL (test DB if testing)."""
        if self.testing and self.test_database_url:
            return str(self.test_database_url)
        return self.database_url_str


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.

    Uses lru_cache to ensure settings are only loaded once per process.
    This is the recommended way to access settings throughout the application.
    """
    return Settings()


# Convenience export
settings = get_settings()
