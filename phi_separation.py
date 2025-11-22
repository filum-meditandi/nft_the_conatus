"""
PHI-Separated Subjective Notes

This module implements the "hash the shadow, protect the diary" pattern:
- Raw PHI (narrative text, identifiers, clinical details) lives encrypted in SubjectiveNote
- The attestation chain sees only a normalized, PHI-light projection
- Encryption uses key-wrapping with references to a keyring/KMS

The chain proves THAT something was said and WHEN.
The encrypted vault holds WHAT was actually said.
Decryption is a separate, auditable operation.
"""

import json
import os
import hashlib
from datetime import datetime, timezone
from typing import Optional, Any
from uuid import UUID, uuid4
from enum import Enum

from sqlalchemy import (
    Column, String, Text, LargeBinary, Boolean, Integer, Float,
    DateTime, ForeignKey, JSON
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func

# Cryptography imports
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import base64

from models import Base


# ============================================================================
# ENCRYPTION KEY MANAGEMENT
# ============================================================================

class EncryptionKey(Base):
    """
    Represents an encryption key in the keyring.
    
    In production, this would reference keys in AWS KMS, HashiCorp Vault,
    or a hardware security module. For development, keys can be stored
    encrypted in the database itself.
    
    Key hierarchy:
    - Master key (from KMS/env) wraps data encryption keys (DEKs)
    - Each SubjectiveNote uses a DEK referenced by encryption_key_id
    - DEKs can be rotated without re-encrypting all data
    """
    __tablename__ = "encryption_keys"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)  # e.g., "dek:2024-03:notes"
    
    # Key material (encrypted by master key in production)
    # In dev, this might be the raw key; in prod, it's wrapped
    wrapped_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    
    # Key metadata
    algorithm: Mapped[str] = mapped_column(String(32), default="AES-256-GCM")
    key_type: Mapped[str] = mapped_column(String(32), default="data_encryption_key")
    
    # Lifecycle
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    rotated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Association to persona (optional - for persona-specific keys)
    persona_token_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True), 
        ForeignKey("persona_tokens.id"), 
        nullable=True
    )


class NoteType(str, Enum):
    """Types of subjective notes for classification."""
    PAIN_NARRATIVE = "pain_narrative"
    SYMPTOM_REPORT = "symptom_report"
    FUNCTIONAL_IMPACT = "functional_impact"
    EMOTIONAL_STATE = "emotional_state"
    TREATMENT_RESPONSE = "treatment_response"
    GENERAL = "general"


class SubjectiveNote(Base):
    """
    Encrypted storage for PHI-containing subjective narratives.
    
    The raw text (names, dates, clinical details, personal narrative)
    lives here, encrypted. The attestation chain only sees a normalized,
    PHI-light projection derived from this note.
    
    Separation of concerns:
    - SubjectiveNote: stores the FULL narrative, encrypted
    - ChainEntry/AttestedEntry: stores a HASH of the normalized projection
    - The link between them (subjective_note_id) proves the chain entry
      refers to this specific encrypted content
    """
    __tablename__ = "subjective_notes"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    persona_token_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), 
        ForeignKey("persona_tokens.id"), 
        index=True,
        nullable=False
    )
    
    # ========================================================================
    # ENCRYPTED CONTENT
    # ========================================================================
    
    # The actual encrypted blob containing full PHI
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    
    # Reference to the encryption key used
    encryption_key_id: Mapped[str] = mapped_column(
        String(128), 
        ForeignKey("encryption_keys.id"),
        nullable=False
    )
    
    # Initialization vector / nonce (if not embedded in ciphertext)
    iv: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    
    # ========================================================================
    # PHI-LIGHT NORMALIZED FIELDS (safe for chain payload)
    # ========================================================================
    
    # These fields are derived from the encrypted content but contain
    # NO identifiable information. They enable search and classification
    # without decryption.
    
    note_type: Mapped[str] = mapped_column(String(32), default=NoteType.GENERAL.value)
    
    # Normalized summary (PHI-stripped, for chain payload)
    # e.g., "Pain report: moderate cervical, burning quality, sleep impact"
    normalized_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Structured tags (PHI-free)
    symptom_tags: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    # e.g., ["cervical_pain", "sleep_disruption", "burning_sensation"]
    
    # Coarse severity (no PHI)
    severity_level: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 1-10
    
    # Hash of the plaintext (for integrity verification after decrypt)
    plaintext_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    
    # ========================================================================
    # TEMPORAL
    # ========================================================================
    
    # When the experience/event occurred (subjective/reported time)
    event_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # When the note was recorded in the system
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(),
        nullable=False
    )
    
    # ========================================================================
    # AUDIT
    # ========================================================================
    
    # Track decryption events for audit
    last_decrypted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    decryption_count: Mapped[int] = mapped_column(Integer, default=0)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    encryption_key: Mapped["EncryptionKey"] = relationship("EncryptionKey")


# ============================================================================
# ENCRYPTION SERVICE
# ============================================================================

class EncryptionService:
    """
    Handles encryption/decryption of subjective notes.
    
    In production, this would integrate with:
    - AWS KMS for key management
    - HashiCorp Vault for secrets
    - Hardware security modules for high-security deployments
    
    For development, uses Fernet (AES-128-CBC with HMAC) with
    keys stored in environment or database.
    """
    
    def __init__(self, master_key: Optional[bytes] = None):
        """
        Initialize with master key.
        
        Args:
            master_key: 32-byte key for wrapping/unwrapping DEKs.
                       In production, this comes from KMS/HSM.
                       If None, reads from MASTER_KEY env var.
        """
        if master_key:
            self._master_key = master_key
        else:
            # Try to get from environment
            key_b64 = os.environ.get("PHI_MASTER_KEY")
            if key_b64:
                self._master_key = base64.urlsafe_b64decode(key_b64)
            else:
                # Development fallback - generate ephemeral key
                # WARNING: Data encrypted with this key is NOT recoverable after restart
                self._master_key = Fernet.generate_key()
                print("WARNING: Using ephemeral master key. Set PHI_MASTER_KEY for persistence.")
        
        self._fernet = Fernet(self._ensure_fernet_key(self._master_key))
    
    def _ensure_fernet_key(self, key: bytes) -> bytes:
        """Ensure key is valid Fernet format (32 bytes, base64-encoded)."""
        if len(key) == 44:  # Already base64-encoded Fernet key
            return key
        elif len(key) == 32:  # Raw 32-byte key
            return base64.urlsafe_b64encode(key)
        else:
            # Derive a key from whatever we got
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b"phi_encryption_salt",  # In production, use proper salt management
                iterations=100000,
                backend=default_backend()
            )
            derived = kdf.derive(key)
            return base64.urlsafe_b64encode(derived)
    
    def encrypt_note(self, plaintext: str) -> tuple[bytes, str]:
        """
        Encrypt a subjective note.
        
        Args:
            plaintext: The raw PHI-containing text
        
        Returns:
            (ciphertext, plaintext_hash) where plaintext_hash is SHA-256 of original
        """
        plaintext_bytes = plaintext.encode('utf-8')
        plaintext_hash = hashlib.sha256(plaintext_bytes).hexdigest()
        ciphertext = self._fernet.encrypt(plaintext_bytes)
        return ciphertext, plaintext_hash
    
    def decrypt_note(self, ciphertext: bytes, expected_hash: Optional[str] = None) -> str:
        """
        Decrypt a subjective note.
        
        Args:
            ciphertext: The encrypted blob
            expected_hash: If provided, verify plaintext hash matches
        
        Returns:
            Decrypted plaintext
        
        Raises:
            ValueError: If hash verification fails
        """
        plaintext_bytes = self._fernet.decrypt(ciphertext)
        plaintext = plaintext_bytes.decode('utf-8')
        
        if expected_hash:
            actual_hash = hashlib.sha256(plaintext_bytes).hexdigest()
            if actual_hash != expected_hash:
                raise ValueError(
                    f"Plaintext hash mismatch. Expected {expected_hash[:16]}..., "
                    f"got {actual_hash[:16]}... Content may have been corrupted."
                )
        
        return plaintext
    
    def generate_data_encryption_key(self) -> tuple[str, bytes]:
        """
        Generate a new data encryption key (DEK) and wrap it with master key.
        
        Returns:
            (key_id, wrapped_key) where wrapped_key is encrypted by master key
        """
        # Generate a fresh DEK
        dek = Fernet.generate_key()
        
        # Wrap it with master key
        wrapped = self._fernet.encrypt(dek)
        
        # Generate key ID
        key_id = f"dek:{datetime.now(timezone.utc).strftime('%Y-%m')}:{uuid4().hex[:8]}"
        
        return key_id, wrapped
    
    def unwrap_data_encryption_key(self, wrapped_key: bytes) -> bytes:
        """Unwrap a DEK using the master key."""
        return self._fernet.decrypt(wrapped_key)


# ============================================================================
# NORMALIZATION SERVICE
# ============================================================================

class NormalizationService:
    """
    Extracts PHI-free normalized data from raw subjective notes.
    
    This is where you'd integrate NLP/AI for:
    - Entity recognition (to REMOVE PHI)
    - Symptom extraction
    - Severity classification
    - Temporal parsing
    """
    
    # PHI patterns to strip (simplified - use proper NER in production)
    PHI_PATTERNS = [
        r'\b\d{3}-\d{2}-\d{4}\b',  # SSN
        r'\b\d{3}-\d{3}-\d{4}\b',  # Phone
        r'\b[A-Z][a-z]+ [A-Z][a-z]+\b',  # Names (very crude)
        r'\b\d+ [A-Z][a-z]+ (St|Ave|Rd|Blvd)\b',  # Addresses
        r'\bMRN[:\s]*\d+\b',  # Medical record numbers
    ]
    
    # Symptom keywords for tagging
    SYMPTOM_KEYWORDS = {
        "cervical_pain": ["neck", "cervical", "c-spine"],
        "lumbar_pain": ["low back", "lower back", "lumbar", "l-spine"],
        "headache": ["headache", "head pain", "migraine"],
        "radiculopathy": ["shooting", "radiating", "down my arm", "down my leg"],
        "sleep_disruption": ["can't sleep", "sleep", "insomnia", "wake up"],
        "burning_sensation": ["burning", "burn"],
        "numbness": ["numb", "numbness", "tingling"],
        "weakness": ["weak", "weakness", "can't lift"],
    }
    
    def normalize(self, raw_text: str) -> dict:
        """
        Extract normalized, PHI-free data from raw subjective text.
        
        Returns:
            {
                "normalized_summary": str,  # PHI-stripped summary
                "symptom_tags": list[str],  # Detected symptom categories
                "severity_level": int | None,  # 1-10 if detectable
                "note_type": str  # Classification
            }
        """
        import re
        
        text_lower = raw_text.lower()
        
        # Extract symptom tags
        symptom_tags = []
        for tag, keywords in self.SYMPTOM_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                symptom_tags.append(tag)
        
        # Extract severity (pain level)
        severity_level = None
        severity_patterns = [
            r'(\d+)\s*/\s*10',
            r'pain\s+(?:level\s+)?(\d+)',
            r'(\d+)\s+out\s+of\s+10',
        ]
        for pattern in severity_patterns:
            match = re.search(pattern, text_lower)
            if match:
                severity_level = min(int(match.group(1)), 10)
                break
        
        # Classify note type
        if severity_level is not None or "pain" in text_lower:
            note_type = NoteType.PAIN_NARRATIVE.value
        elif any(tag in symptom_tags for tag in ["sleep_disruption", "weakness"]):
            note_type = NoteType.FUNCTIONAL_IMPACT.value
        elif any(word in text_lower for word in ["anxious", "scared", "depressed", "worried"]):
            note_type = NoteType.EMOTIONAL_STATE.value
        else:
            note_type = NoteType.SYMPTOM_REPORT.value
        
        # Build PHI-stripped summary
        summary_parts = []
        if note_type:
            summary_parts.append(f"Type: {note_type}")
        if severity_level:
            summary_parts.append(f"Severity: {severity_level}/10")
        if symptom_tags:
            summary_parts.append(f"Symptoms: {', '.join(symptom_tags)}")
        
        normalized_summary = "; ".join(summary_parts) if summary_parts else "General note"
        
        return {
            "normalized_summary": normalized_summary,
            "symptom_tags": symptom_tags,
            "severity_level": severity_level,
            "note_type": note_type
        }


# ============================================================================
# CANONICAL PAYLOAD FOR CHAIN (PHI-LIGHT)
# ============================================================================

def build_subjective_note_payload(note: SubjectiveNote) -> dict:
    """
    Build the canonical payload for chain attestation.
    
    CRITICAL: This payload contains NO PHI. It is safe to:
    - Store in the attestation chain
    - Include in verification reports
    - Share with opposing counsel (in discovery)
    
    The chain proves this note existed at this time with these
    characteristics, without revealing the actual content.
    """
    from canonical_json import to_canonical_json
    
    return {
        "schema_version": "1.0",
        "note_id": str(note.id),
        "persona_token_id": str(note.persona_token_id),
        "note_type": note.note_type,
        "normalized_summary": note.normalized_summary,
        "symptom_tags": note.symptom_tags,
        "severity_level": note.severity_level,
        "event_time": note.event_time.isoformat() if note.event_time else None,
        "recorded_at": note.recorded_at.isoformat() if note.recorded_at else None,
        # Include hash of encrypted content for integrity binding
        "ciphertext_hash": hashlib.sha256(note.ciphertext).hexdigest(),
    }
