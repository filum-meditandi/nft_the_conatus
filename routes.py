"""
Phenomenological Evidence API Routes

These endpoints accept pain notes, perspective entries, and other phenomenological
data from various sources (SMS via Twilio, mobile app, intake forms) and chain
them into the attested ledger.

Each submission:
1. Creates the domain object (PainState, PerspectiveNote)
2. Optionally links to a Fact
3. Creates an AttestedEntry in the persona's hash chain
4. Returns the attestation proof
"""

from datetime import datetime, timezone
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, validator
from sqlalchemy.orm import Session

from models import (
    Party, PersonaToken, Fact, PerspectiveNote, PainState, 
    AttestedEntry, Valence, FactCategory
)
from attestation_service import AttestationService, get_or_create_persona_for_party


router = APIRouter(prefix="/phenomenology", tags=["phenomenology"])


# ============================================================================
# REQUEST/RESPONSE SCHEMAS
# ============================================================================

class PainStateCreate(BaseModel):
    """Schema for submitting a pain state reading."""
    
    party_id: UUID
    fact_id: Optional[UUID] = None
    attention_event_id: Optional[UUID] = None
    
    value: float = Field(..., ge=0, le=10, description="Pain level 0-10")
    scale_type: str = Field(default="0-10")
    
    location: Optional[str] = Field(None, max_length=128)
    quality: Optional[str] = Field(None, max_length=128)
    
    functional_impact: Optional[dict] = Field(
        None, 
        description="Structured impact: {sleep: 1-10, work: 1-10, adls: 1-10}"
    )
    
    source: str = Field(default="api", description="sms, app, intake, etc.")
    
    recorded_at: Optional[datetime] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "party_id": "123e4567-e89b-12d3-a456-426614174000",
                "value": 7.0,
                "location": "neck",
                "quality": "burning",
                "functional_impact": {"sleep": 3, "work": 5, "adls": 4},
                "source": "sms"
            }
        }


class PerspectiveNoteCreate(BaseModel):
    """Schema for submitting a perspective note."""
    
    party_id: UUID
    fact_id: Optional[UUID] = None
    attention_event_id: Optional[UUID] = None
    
    title: Optional[str] = Field(None, max_length=255)
    body: str = Field(..., min_length=1)
    
    valence: Optional[Valence] = None
    meaning_tags: Optional[List[str]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "party_id": "123e4567-e89b-12d3-a456-426614174000",
                "title": "How the crash changed my work life",
                "body": "I used to be able to sit at my desk for hours. Now I have to get up every 20 minutes because of the burning in my neck.",
                "valence": "pain",
                "meaning_tags": ["loss_of_capacity", "work_impact"]
            }
        }


class AttestationProof(BaseModel):
    """Proof of attestation for a domain object."""
    
    entry_id: UUID
    sequence_number: int
    payload_hash: str
    prev_hash: Optional[str]
    entry_hash: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class PainStateResponse(BaseModel):
    """Response after creating a pain state."""
    
    id: UUID
    party_id: UUID
    value: float
    location: Optional[str]
    quality: Optional[str]
    recorded_at: datetime
    attestation: AttestationProof
    
    class Config:
        from_attributes = True


class PerspectiveNoteResponse(BaseModel):
    """Response after creating a perspective note."""
    
    id: UUID
    party_id: UUID
    title: Optional[str]
    body: str
    valence: Optional[str]
    created_at: datetime
    attestation: AttestationProof
    
    class Config:
        from_attributes = True


class ChainSummary(BaseModel):
    """Summary of a persona's attestation chain."""
    
    persona_token_id: str
    total_entries: int
    first_entry: Optional[dict]
    latest_entry: Optional[dict]
    entries_by_type: dict


class ChainVerificationResult(BaseModel):
    """Result of verifying a chain's integrity."""
    
    is_valid: bool
    first_broken_sequence: Optional[int]
    error_message: Optional[str]


class SMSPainReport(BaseModel):
    """
    Simplified schema for pain reports coming from SMS/Twilio.
    
    Parses messages like:
    - "Pain 7/10, can't sleep, neck burning"
    - "Note 8 at 8:56 pm it was 126"
    """
    
    party_id: UUID
    raw_message: str
    sender_phone: str
    received_at: datetime
    
    # Parsed fields (can be extracted by AI or regex)
    parsed_value: Optional[float] = None
    parsed_location: Optional[str] = None
    parsed_quality: Optional[str] = None
    parsed_functional_notes: Optional[str] = None


# ============================================================================
# DEPENDENCY
# ============================================================================

# In production, this would come from your database session dependency
def get_db():
    """Database session dependency - implement based on your setup."""
    # from database import SessionLocal
    # db = SessionLocal()
    # try:
    #     yield db
    # finally:
    #     db.close()
    raise NotImplementedError("Implement get_db() with your database session")


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post(
    "/pain-states",
    response_model=PainStateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record a pain state with attestation"
)
async def create_pain_state(
    data: PainStateCreate,
    db: Session = Depends(get_db)
):
    """
    Record a pain state measurement and attest it to the plaintiff's chain.
    
    This endpoint:
    1. Validates the party exists
    2. Creates the PainState record
    3. Gets/creates the party's PersonaToken
    4. Creates an AttestedEntry chained to previous entries
    5. Returns the pain state with attestation proof
    """
    # Verify party exists
    party = db.query(Party).filter(Party.id == data.party_id).first()
    if not party:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Party {data.party_id} not found"
        )
    
    # Verify fact exists if provided
    if data.fact_id:
        fact = db.query(Fact).filter(Fact.id == data.fact_id).first()
        if not fact:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Fact {data.fact_id} not found"
            )
    
    # Create PainState
    pain_state = PainState(
        party_id=data.party_id,
        fact_id=data.fact_id,
        attention_event_id=data.attention_event_id,
        value=data.value,
        scale_type=data.scale_type,
        location=data.location,
        quality=data.quality,
        functional_impact=data.functional_impact,
        source=data.source,
        recorded_at=data.recorded_at or datetime.now(timezone.utc)
    )
    db.add(pain_state)
    db.flush()  # Get the ID
    
    # Get or create PersonaToken
    persona_token = get_or_create_persona_for_party(db, data.party_id)
    
    # Create attestation
    attestation_service = AttestationService(db)
    entry = attestation_service.attest_pain_state(
        pain_state=pain_state,
        persona_token_id=persona_token.id
    )
    
    db.commit()
    
    return PainStateResponse(
        id=pain_state.id,
        party_id=pain_state.party_id,
        value=pain_state.value,
        location=pain_state.location,
        quality=pain_state.quality,
        recorded_at=pain_state.recorded_at,
        attestation=AttestationProof(
            entry_id=entry.id,
            sequence_number=entry.sequence_number,
            payload_hash=entry.payload_hash,
            prev_hash=entry.prev_hash,
            entry_hash=entry.entry_hash,
            created_at=entry.created_at
        )
    )


@router.post(
    "/perspective-notes",
    response_model=PerspectiveNoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record a perspective note with attestation"
)
async def create_perspective_note(
    data: PerspectiveNoteCreate,
    db: Session = Depends(get_db)
):
    """
    Record a perspective note and attest it to the plaintiff's chain.
    
    Perspective notes capture the plaintiff's narrative experience:
    - How facts feel from their point of view
    - Meaning and purpose impacts
    - Emotional valence
    """
    # Verify party exists
    party = db.query(Party).filter(Party.id == data.party_id).first()
    if not party:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Party {data.party_id} not found"
        )
    
    # Create PerspectiveNote
    note = PerspectiveNote(
        party_id=data.party_id,
        fact_id=data.fact_id,
        attention_event_id=data.attention_event_id,
        title=data.title,
        body=data.body,
        valence=data.valence,
        meaning_tags=data.meaning_tags
    )
    db.add(note)
    db.flush()
    
    # Get or create PersonaToken
    persona_token = get_or_create_persona_for_party(db, data.party_id)
    
    # Create attestation
    attestation_service = AttestationService(db)
    entry = attestation_service.attest_perspective_note(
        note=note,
        persona_token_id=persona_token.id
    )
    
    db.commit()
    
    return PerspectiveNoteResponse(
        id=note.id,
        party_id=note.party_id,
        title=note.title,
        body=note.body,
        valence=note.valence.value if note.valence else None,
        created_at=note.created_at,
        attestation=AttestationProof(
            entry_id=entry.id,
            sequence_number=entry.sequence_number,
            payload_hash=entry.payload_hash,
            prev_hash=entry.prev_hash,
            entry_hash=entry.entry_hash,
            created_at=entry.created_at
        )
    )


@router.post(
    "/sms/pain-report",
    response_model=PainStateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Process an SMS pain report (from Twilio webhook)"
)
async def process_sms_pain_report(
    data: SMSPainReport,
    db: Session = Depends(get_db)
):
    """
    Process a pain report received via SMS.
    
    This endpoint:
    1. Accepts the raw SMS + any parsed fields
    2. Creates a PainState (and optionally a PerspectiveNote for narrative)
    3. Attests to the chain
    
    Designed to integrate with your Twilio SMS webhook flow.
    
    Example incoming SMS: "Pain 7/10, can't sleep, neck burning"
    """
    # Verify party exists
    party = db.query(Party).filter(Party.id == data.party_id).first()
    if not party:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Party {data.party_id} not found"
        )
    
    # Create PainState from parsed or default values
    pain_state = PainState(
        party_id=data.party_id,
        value=data.parsed_value or 5.0,  # Default to 5 if not parsed
        scale_type="0-10",
        location=data.parsed_location,
        quality=data.parsed_quality,
        functional_impact=(
            {"notes": data.parsed_functional_notes} 
            if data.parsed_functional_notes else None
        ),
        source="sms",
        recorded_at=data.received_at
    )
    db.add(pain_state)
    db.flush()
    
    # Also create a perspective note with the raw message for full context
    note = PerspectiveNote(
        party_id=data.party_id,
        body=f"[SMS from {data.sender_phone}] {data.raw_message}",
        valence=Valence.PAIN if (data.parsed_value and data.parsed_value > 5) else None
    )
    db.add(note)
    db.flush()
    
    # Get or create PersonaToken
    persona_token = get_or_create_persona_for_party(db, data.party_id)
    
    # Attest both
    attestation_service = AttestationService(db)
    
    # Attest the perspective note first (raw context)
    attestation_service.attest_perspective_note(
        note=note,
        persona_token_id=persona_token.id
    )
    
    # Then attest the pain state (structured data)
    entry = attestation_service.attest_pain_state(
        pain_state=pain_state,
        persona_token_id=persona_token.id
    )
    
    db.commit()
    
    return PainStateResponse(
        id=pain_state.id,
        party_id=pain_state.party_id,
        value=pain_state.value,
        location=pain_state.location,
        quality=pain_state.quality,
        recorded_at=pain_state.recorded_at,
        attestation=AttestationProof(
            entry_id=entry.id,
            sequence_number=entry.sequence_number,
            payload_hash=entry.payload_hash,
            prev_hash=entry.prev_hash,
            entry_hash=entry.entry_hash,
            created_at=entry.created_at
        )
    )


@router.get(
    "/chain/{persona_token_id}/summary",
    response_model=ChainSummary,
    summary="Get attestation chain summary"
)
async def get_chain_summary(
    persona_token_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Get a summary of the attestation chain for a persona.
    
    Returns:
    - Total entry count
    - First and latest entry info
    - Breakdown by domain type
    """
    attestation_service = AttestationService(db)
    summary = attestation_service.get_chain_summary(persona_token_id)
    return ChainSummary(**summary)


@router.get(
    "/chain/{persona_token_id}/verify",
    response_model=ChainVerificationResult,
    summary="Verify chain integrity"
)
async def verify_chain(
    persona_token_id: UUID,
    from_sequence: int = 1,
    to_sequence: Optional[int] = None,
    verify_payloads: bool = False,
    db: Session = Depends(get_db)
):
    """
    Verify the cryptographic integrity of a persona's attestation chain.
    
    Checks that each entry's hash correctly chains from the previous entry.
    Returns the first broken sequence number if integrity is compromised.
    
    Args:
        verify_payloads: If True, also verify domain objects haven't been
                        modified outside the attestation system.
    """
    attestation_service = AttestationService(db)
    is_valid, broken_seq, error = attestation_service.verify_chain(
        persona_token_id=persona_token_id,
        from_sequence=from_sequence,
        to_sequence=to_sequence,
        recompute_payload_hashes=verify_payloads
    )
    
    return ChainVerificationResult(
        is_valid=is_valid,
        first_broken_sequence=broken_seq,
        error_message=error
    )


class VerificationReport(BaseModel):
    """Comprehensive verification report for court/audit use."""
    
    persona_token_id: str
    verification_timestamp: str
    chain_summary: dict
    verification_result: dict
    entries: List[dict]
    entry_count: int
    payload_verification_included: bool


@router.get(
    "/chain/{persona_token_id}/report",
    response_model=VerificationReport,
    summary="Generate verification report for court/audit"
)
async def generate_verification_report(
    persona_token_id: UUID,
    verify_payloads: bool = True,
    db: Session = Depends(get_db)
):
    """
    Generate a comprehensive verification report.
    
    This is the "courtroom button" - produces a detailed report showing:
    - Complete chain summary
    - Verification status
    - Every entry with its hashes
    - Any anomalies detected
    
    The report can be exported and presented as evidence that the
    phenomenological record has not been tampered with.
    """
    attestation_service = AttestationService(db)
    report = attestation_service.generate_verification_report(
        persona_token_id=persona_token_id,
        include_payload_verification=verify_payloads
    )
    return VerificationReport(**report)


@router.get(
    "/chain/{persona_token_id}/entries",
    response_model=List[AttestationProof],
    summary="List attestation entries"
)
async def list_chain_entries(
    persona_token_id: UUID,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    List attestation entries for a persona, newest first.
    """
    entries = (
        db.query(AttestedEntry)
        .filter(AttestedEntry.persona_token_id == persona_token_id)
        .order_by(AttestedEntry.sequence_number.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    
    return [
        AttestationProof(
            entry_id=e.id,
            sequence_number=e.sequence_number,
            payload_hash=e.payload_hash,
            prev_hash=e.prev_hash,
            entry_hash=e.entry_hash,
            created_at=e.created_at
        )
        for e in entries
    ]
