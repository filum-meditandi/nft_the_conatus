"""
Signature & Key Infrastructure

Implements cryptographic signing for attestation entries.

Trust modes:
1. Server-signed only (implemented first)
   - Server has a key pair in env/KMS
   - Every attestation signed as "Seen by server X"

2. Persona-bound keys (future)
   - Each user device has its own key
   - They sign before sending to server
   - Server can countersign

3. Hybrid (future)
   - Client signs, server countersigns
   - Maximum non-repudiation

What gets signed (canonical signing message):
    {
        "persona_token_id": <uuid>,
        "sequence_number": <int>,
        "previous_hash": <hex>,
        "payload_hash": <hex>,
        "timestamp": <iso8601>
    }
"""

import os
import json
import base64
from datetime import datetime, timezone
from typing import Optional, Tuple
from uuid import UUID, uuid4
from enum import Enum

from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func

# Cryptography imports
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, ec
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidSignature

from models import Base
from canonical_json import to_canonical_json


# ============================================================================
# KEY MODELS
# ============================================================================

class KeyAlgorithm(str, Enum):
    """Supported signing algorithms."""
    ED25519 = "Ed25519"      # EdDSA - fast, small signatures
    ES256 = "ES256"          # ECDSA with P-256 - widely supported
    ES384 = "ES384"          # ECDSA with P-384 - higher security


class KeyPurpose(str, Enum):
    """What the key is used for."""
    ATTESTATION = "attestation"      # Signing chain entries
    PERSONA_IDENTITY = "persona_identity"  # Persona's own key
    SERVER_WITNESS = "server_witness"  # Server witnessing entries
    COUNTERSIGN = "countersign"      # Secondary signature


class SigningKey(Base):
    """
    A signing key in the keyring.
    
    Keys can be:
    - Server-managed (for system attestation)
    - Persona-bound (for user device signing)
    - External (for third-party witnesses)
    """
    __tablename__ = "signing_keys"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    # e.g., "server:attestation:primary"
    # e.g., "persona:123e4567:ios-device-1"
    
    # Optional persona association
    persona_token_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("persona_tokens.id"),
        nullable=True,
        index=True
    )
    
    # Key material (public only in DB - private in KMS/env)
    public_key_pem: Mapped[str] = mapped_column(Text, nullable=False)
    public_key_jwk: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    
    # Algorithm
    algorithm: Mapped[str] = mapped_column(String(32), nullable=False)
    
    # Purpose and trust
    purpose: Mapped[str] = mapped_column(String(32), default=KeyPurpose.ATTESTATION.value)
    is_server_managed: Mapped[bool] = mapped_column(Boolean, default=False)
    trust_level: Mapped[int] = mapped_column(Integer, default=1)  # 1=self, 2=server, 3=notarized
    
    # Human-readable description
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Device/client info (for persona keys)
    device_info: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    
    # Lifecycle
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    activated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revocation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    @property
    def is_active(self) -> bool:
        """Key is active if activated and not revoked."""
        return (
            self.activated_at is not None and 
            self.revoked_at is None
        )


# ============================================================================
# SIGNING SERVICE
# ============================================================================

class SigningService:
    """
    Handles cryptographic signing of attestation entries.
    
    In production:
    - Server private keys live in KMS/HSM
    - This service calls KMS APIs for signing
    - Private key material never enters application memory
    
    For development:
    - Private key can be in environment variable
    - Or generated ephemerally (not recommended for real use)
    """
    
    def __init__(
        self,
        server_private_key_pem: Optional[str] = None,
        server_key_id: str = "server:attestation:primary"
    ):
        """
        Initialize with server signing key.
        
        Args:
            server_private_key_pem: PEM-encoded private key
                                   If None, reads from ATTESTATION_PRIVATE_KEY env var
            server_key_id: Identifier for the server's signing key
        """
        self.server_key_id = server_key_id
        
        if server_private_key_pem:
            self._server_private_key = self._load_private_key(server_private_key_pem)
        else:
            key_pem = os.environ.get("ATTESTATION_PRIVATE_KEY")
            if key_pem:
                self._server_private_key = self._load_private_key(key_pem)
            else:
                # Generate ephemeral key for development
                print("WARNING: Generating ephemeral signing key. Set ATTESTATION_PRIVATE_KEY for persistence.")
                self._server_private_key = ed25519.Ed25519PrivateKey.generate()
        
        self._server_public_key = self._server_private_key.public_key()
        self._algorithm = KeyAlgorithm.ED25519
    
    def _load_private_key(self, pem: str):
        """Load a private key from PEM format."""
        pem_bytes = pem.encode('utf-8') if isinstance(pem, str) else pem
        return serialization.load_pem_private_key(
            pem_bytes,
            password=None,
            backend=default_backend()
        )
    
    def get_server_public_key_pem(self) -> str:
        """Get the server's public key in PEM format."""
        return self._server_public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')
    
    def get_server_public_key_jwk(self) -> dict:
        """Get the server's public key in JWK format."""
        # For Ed25519, we need to extract the raw public key bytes
        raw_public = self._server_public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        return {
            "kty": "OKP",
            "crv": "Ed25519",
            "x": base64.urlsafe_b64encode(raw_public).rstrip(b'=').decode('ascii'),
            "kid": self.server_key_id
        }
    
    def build_signing_message(
        self,
        persona_token_id: UUID,
        sequence_number: int,
        previous_hash: Optional[str],
        payload_hash: str,
        timestamp: datetime
    ) -> str:
        """
        Build the canonical message to be signed.
        
        This is the exact data structure that gets signed.
        Any change to this format would require key rotation.
        """
        message = {
            "version": "attestation_v1",
            "persona_token_id": str(persona_token_id),
            "sequence_number": sequence_number,
            "previous_hash": previous_hash or "GENESIS",
            "payload_hash": payload_hash,
            "timestamp": timestamp.replace(microsecond=0).isoformat()
        }
        return to_canonical_json(message)
    
    def sign_entry(
        self,
        persona_token_id: UUID,
        sequence_number: int,
        previous_hash: Optional[str],
        payload_hash: str,
        timestamp: datetime
    ) -> Tuple[str, str]:
        """
        Sign an attestation entry with the server key.
        
        Returns:
            (signature_base64, signer_key_id)
        """
        message = self.build_signing_message(
            persona_token_id=persona_token_id,
            sequence_number=sequence_number,
            previous_hash=previous_hash,
            payload_hash=payload_hash,
            timestamp=timestamp
        )
        
        signature = self._server_private_key.sign(message.encode('utf-8'))
        signature_b64 = base64.b64encode(signature).decode('ascii')
        
        return signature_b64, self.server_key_id
    
    def verify_signature(
        self,
        signature_base64: str,
        persona_token_id: UUID,
        sequence_number: int,
        previous_hash: Optional[str],
        payload_hash: str,
        timestamp: datetime,
        public_key_pem: Optional[str] = None
    ) -> bool:
        """
        Verify a signature on an attestation entry.
        
        Args:
            signature_base64: The signature to verify
            public_key_pem: Public key to verify against.
                           If None, uses the server's public key.
        
        Returns:
            True if signature is valid, False otherwise
        """
        message = self.build_signing_message(
            persona_token_id=persona_token_id,
            sequence_number=sequence_number,
            previous_hash=previous_hash,
            payload_hash=payload_hash,
            timestamp=timestamp
        )
        
        signature = base64.b64decode(signature_base64)
        
        if public_key_pem:
            public_key = serialization.load_pem_public_key(
                public_key_pem.encode('utf-8'),
                backend=default_backend()
            )
        else:
            public_key = self._server_public_key
        
        try:
            public_key.verify(signature, message.encode('utf-8'))
            return True
        except InvalidSignature:
            return False


# ============================================================================
# KEY GENERATION UTILITIES
# ============================================================================

def generate_ed25519_keypair() -> Tuple[str, str]:
    """
    Generate a new Ed25519 key pair.
    
    Returns:
        (private_key_pem, public_key_pem)
    """
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode('utf-8')
    
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode('utf-8')
    
    return private_pem, public_pem


def generate_signing_key_record(
    key_id: str,
    persona_token_id: Optional[UUID] = None,
    purpose: KeyPurpose = KeyPurpose.ATTESTATION,
    is_server_managed: bool = False,
    description: Optional[str] = None,
    device_info: Optional[dict] = None
) -> Tuple[SigningKey, str]:
    """
    Generate a SigningKey record with a fresh key pair.
    
    Returns:
        (signing_key_record, private_key_pem)
        
        The private_key_pem should be stored securely (KMS, env, etc.)
        and NOT in the database.
    """
    private_pem, public_pem = generate_ed25519_keypair()
    
    # Build JWK
    private_key = serialization.load_pem_private_key(
        private_pem.encode('utf-8'),
        password=None,
        backend=default_backend()
    )
    public_key = private_key.public_key()
    raw_public = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    jwk = {
        "kty": "OKP",
        "crv": "Ed25519",
        "x": base64.urlsafe_b64encode(raw_public).rstrip(b'=').decode('ascii'),
        "kid": key_id
    }
    
    record = SigningKey(
        id=key_id,
        persona_token_id=persona_token_id,
        public_key_pem=public_pem,
        public_key_jwk=jwk,
        algorithm=KeyAlgorithm.ED25519.value,
        purpose=purpose.value,
        is_server_managed=is_server_managed,
        description=description,
        device_info=device_info,
        activated_at=datetime.now(timezone.utc)
    )
    
    return record, private_pem


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    from uuid import uuid4
    
    print("=== Signing Infrastructure Demo ===\n")
    
    # Generate a server key
    print("1. Generating server signing key...")
    server_key, server_private_pem = generate_signing_key_record(
        key_id="server:attestation:demo",
        purpose=KeyPurpose.SERVER_WITNESS,
        is_server_managed=True,
        description="Demo server attestation key"
    )
    print(f"   Key ID: {server_key.id}")
    print(f"   Algorithm: {server_key.algorithm}")
    print(f"   Public key (first 64 chars): {server_key.public_key_pem[:64]}...")
    
    # Initialize signing service with the private key
    print("\n2. Initializing signing service...")
    signer = SigningService(
        server_private_key_pem=server_private_pem,
        server_key_id=server_key.id
    )
    
    # Sign a sample entry
    print("\n3. Signing a sample attestation entry...")
    persona_id = uuid4()
    timestamp = datetime.now(timezone.utc)
    
    signature, key_id = signer.sign_entry(
        persona_token_id=persona_id,
        sequence_number=1,
        previous_hash=None,
        payload_hash="abc123def456",
        timestamp=timestamp
    )
    print(f"   Signature: {signature[:32]}...")
    print(f"   Signer key ID: {key_id}")
    
    # Verify the signature
    print("\n4. Verifying signature...")
    is_valid = signer.verify_signature(
        signature_base64=signature,
        persona_token_id=persona_id,
        sequence_number=1,
        previous_hash=None,
        payload_hash="abc123def456",
        timestamp=timestamp
    )
    print(f"   Signature valid: {is_valid}")
    
    # Try to verify with wrong data
    print("\n5. Verifying with tampered data...")
    is_valid_tampered = signer.verify_signature(
        signature_base64=signature,
        persona_token_id=persona_id,
        sequence_number=1,
        previous_hash=None,
        payload_hash="TAMPERED_HASH",  # Wrong!
        timestamp=timestamp
    )
    print(f"   Signature valid (should be False): {is_valid_tampered}")
    
    print("\n=== Demo complete ===")
