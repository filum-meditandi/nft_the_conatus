"""
Phone Registry

Maps phone numbers to personas, parties, and cases for Twilio integration.

This is the bridge between an incoming SMS/call and the phenomenological
evidence system. When a message arrives, we look up who it's from and
which case it belongs to.
"""

from datetime import datetime, timezone
from typing import Optional, Dict
from uuid import UUID, uuid4

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship, Mapped, mapped_column, Session
from sqlalchemy.sql import func

from models import Base, Party, PersonaToken


class PhoneRegistry(Base):
    """
    Maps phone numbers to personas/parties/cases.
    
    A single phone number is associated with exactly one case context.
    If a client has multiple cases, they'd use different numbers or
    we'd need a disambiguation flow.
    """
    __tablename__ = "phone_registry"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # The phone number (E.164 format: +15551234567)
    phone_number: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    
    # Who this phone belongs to
    party_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("parties.id"),
        nullable=False
    )
    
    persona_token_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("persona_tokens.id"),
        nullable=False
    )
    
    # Which case this phone is registered to
    case_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    
    # Active status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Timestamps
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )
    last_message_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    # Relationships
    party: Mapped["Party"] = relationship("Party")
    persona_token: Mapped["PersonaToken"] = relationship("PersonaToken")


class PhoneRegistryService:
    """
    Service for managing phone-to-persona mappings.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def normalize_phone(self, phone: str) -> str:
        """Normalize phone to E.164 format."""
        # Strip everything except digits and leading +
        cleaned = ''.join(c for c in phone if c.isdigit() or c == '+')
        
        # Ensure starts with +
        if not cleaned.startswith('+'):
            # Assume US if no country code
            if len(cleaned) == 10:
                cleaned = '+1' + cleaned
            elif len(cleaned) == 11 and cleaned.startswith('1'):
                cleaned = '+' + cleaned
        
        return cleaned
    
    def get_by_phone(self, phone: str) -> Optional[PhoneRegistry]:
        """Look up registration by phone number."""
        normalized = self.normalize_phone(phone)
        
        return self.db.query(PhoneRegistry).filter(
            PhoneRegistry.phone_number == normalized,
            PhoneRegistry.is_active == True
        ).first()
    
    def get_context(self, phone: str) -> Optional[Dict[str, UUID]]:
        """
        Get the persona/party/case context for a phone number.
        
        Returns: {"persona_token_id": UUID, "party_id": UUID, "case_id": UUID}
        or None if not found.
        """
        reg = self.get_by_phone(phone)
        
        if not reg:
            return None
        
        return {
            "persona_token_id": reg.persona_token_id,
            "party_id": reg.party_id,
            "case_id": reg.case_id
        }
    
    def register(
        self,
        phone: str,
        party_id: UUID,
        persona_token_id: UUID,
        case_id: UUID
    ) -> PhoneRegistry:
        """Register a phone number to a party/case."""
        normalized = self.normalize_phone(phone)
        
        # Check for existing registration
        existing = self.db.query(PhoneRegistry).filter(
            PhoneRegistry.phone_number == normalized
        ).first()
        
        if existing:
            # Update existing registration
            existing.party_id = party_id
            existing.persona_token_id = persona_token_id
            existing.case_id = case_id
            existing.is_active = True
            self.db.commit()
            return existing
        
        # Create new registration
        reg = PhoneRegistry(
            phone_number=normalized,
            party_id=party_id,
            persona_token_id=persona_token_id,
            case_id=case_id
        )
        self.db.add(reg)
        self.db.commit()
        
        return reg
    
    def deactivate(self, phone: str) -> bool:
        """Deactivate a phone registration."""
        reg = self.get_by_phone(phone)
        
        if reg:
            reg.is_active = False
            self.db.commit()
            return True
        
        return False
    
    def update_last_message(self, phone: str) -> None:
        """Update the last message timestamp."""
        reg = self.get_by_phone(phone)
        
        if reg:
            reg.last_message_at = datetime.now(timezone.utc)
            self.db.commit()
