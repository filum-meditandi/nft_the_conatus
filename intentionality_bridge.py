"""
Integration: Intentionality Ledger → Phenomenological Evidence

This module bridges your existing Observer → Session → AttentionEvent
chain with the new phenomenological evidence system.

The key mappings:
- Observer → Party (when it's a legal actor)
- NftToken → PersonaToken
- AttentionEvent → links into PerspectiveNote and PainState

When a client sends an SMS or interacts with the system, data flows:
1. AttentionEvent created (intentionality ledger)
2. PerspectiveNote and/or PainState created (phenomenological layer)
3. AttestedEntry created (cryptographic chain)
4. Optionally anchored on-chain (external verification)
"""

from datetime import datetime, timezone
from typing import Optional, Tuple, Any
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import select

from models import (
    Party, PersonaToken, PerspectiveNote, PainState, 
    AttestedEntry, Valence, PartyRole
)
from attestation_service import AttestationService, get_or_create_persona_for_party


# ============================================================================
# INTEGRATION SERVICE
# ============================================================================

class IntentionalityBridge:
    """
    Bridges the intentionality ledger with phenomenological evidence.
    
    The intentionality ledger tracks:
    - Observer: who is experiencing
    - Session: bounded period of activity
    - AttentionEvent: specific moments of directed attention
    - NftToken: cryptographic identity anchor
    
    The phenomenological layer adds:
    - Party: legal role (plaintiff, defendant, etc.)
    - PersonaToken: legal persona's cryptographic identity
    - PerspectiveNote: narrative experience
    - PainState: structured suffering data
    - AttestedEntry: tamper-evident chain
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.attestation_service = AttestationService(db)
    
    def link_observer_to_party(
        self,
        observer_id: UUID,
        party_id: UUID
    ) -> Party:
        """
        Link an Observer from the intentionality ledger to a Party.
        
        Call this when you want to connect a client's intentionality data
        (glucose readings, time entries, notes) to their legal identity.
        """
        party = self.db.query(Party).filter(Party.id == party_id).first()
        if not party:
            raise ValueError(f"Party {party_id} not found")
        
        party.observer_id = observer_id
        self.db.flush()
        
        return party
    
    def create_party_with_persona(
        self,
        legal_name: str,
        role: PartyRole,
        case_id: Optional[UUID] = None,
        observer_id: Optional[UUID] = None,
        nft_id: Optional[str] = None,
        contract_address: Optional[str] = None,
        chain_id: Optional[int] = None
    ) -> Tuple[Party, PersonaToken]:
        """
        Create a Party and their PersonaToken in one operation.
        
        This sets up the complete identity anchor for a legal actor.
        """
        party = Party(
            legal_name=legal_name,
            role=role,
            case_id=case_id,
            observer_id=observer_id
        )
        self.db.add(party)
        self.db.flush()
        
        persona_token = PersonaToken(
            party_id=party.id,
            nft_id=nft_id,
            contract_address=contract_address,
            chain_id=chain_id
        )
        self.db.add(persona_token)
        self.db.flush()
        
        return party, persona_token
    
    def record_from_attention_event(
        self,
        party_id: UUID,
        attention_event_id: UUID,
        content: str,
        pain_value: Optional[float] = None,
        pain_location: Optional[str] = None,
        pain_quality: Optional[str] = None,
        valence: Optional[Valence] = None,
        meaning_tags: Optional[list] = None,
        source: str = "intentionality_ledger"
    ) -> Tuple[Optional[PerspectiveNote], Optional[PainState], list]:
        """
        Record phenomenological data linked to an AttentionEvent.
        
        This is the main integration point. When something happens in
        the intentionality ledger, call this to create the corresponding
        phenomenological records.
        
        Returns: (perspective_note, pain_state, [attestation_entries])
        """
        persona_token = get_or_create_persona_for_party(self.db, party_id)
        entries = []
        perspective_note = None
        pain_state = None
        
        # Create perspective note if there's narrative content
        if content:
            perspective_note = PerspectiveNote(
                party_id=party_id,
                attention_event_id=attention_event_id,
                body=content,
                valence=valence,
                meaning_tags=meaning_tags
            )
            self.db.add(perspective_note)
            self.db.flush()
            
            entry = self.attestation_service.attest_perspective_note(
                note=perspective_note,
                persona_token_id=persona_token.id
            )
            entries.append(entry)
        
        # Create pain state if there's pain data
        if pain_value is not None:
            pain_state = PainState(
                party_id=party_id,
                attention_event_id=attention_event_id,
                value=pain_value,
                location=pain_location,
                quality=pain_quality,
                source=source,
                recorded_at=datetime.now(timezone.utc)
            )
            self.db.add(pain_state)
            self.db.flush()
            
            entry = self.attestation_service.attest_pain_state(
                pain_state=pain_state,
                persona_token_id=persona_token.id
            )
            entries.append(entry)
        
        return perspective_note, pain_state, entries


# ============================================================================
# GLUCOSE READING INTEGRATION
# ============================================================================

def process_glucose_attention_event(
    db: Session,
    party_id: UUID,
    attention_event_id: UUID,
    glucose_value: float,
    previous_value: Optional[float],
    elapsed_minutes: Optional[int],
    raw_note: str
) -> Tuple[PerspectiveNote, AttestedEntry]:
    """
    Process a glucose reading from the intentionality ledger.
    
    Example: "Note 8 at 8:56 pm it was 126. So from 127 to 126 in 27 minutes. 
             That's 0.037 change per minute. I'm not concerned."
    
    This creates:
    1. A PerspectiveNote capturing the client's interpretation
    2. An AttestedEntry in their chain
    
    The glucose data itself should be stored as a Fact with evidence
    (the meter reading, CGM log, etc.)
    """
    bridge = IntentionalityBridge(db)
    
    # Determine valence based on glucose trajectory
    if previous_value and glucose_value:
        if glucose_value < 70:
            valence = Valence.FEAR  # Hypoglycemia concern
        elif glucose_value > 180:
            valence = Valence.PAIN  # Hyperglycemia distress
        elif abs(glucose_value - previous_value) > 30:
            valence = Valence.FEAR  # Rapid change
        else:
            valence = Valence.NEUTRAL
    else:
        valence = Valence.NEUTRAL
    
    # Create meaning tags based on the content
    meaning_tags = ["glucose_monitoring"]
    if "concern" in raw_note.lower() or "worried" in raw_note.lower():
        meaning_tags.append("health_anxiety")
    if "not concerned" in raw_note.lower():
        meaning_tags.append("self_reassurance")
    
    perspective_note, pain_state, entries = bridge.record_from_attention_event(
        party_id=party_id,
        attention_event_id=attention_event_id,
        content=raw_note,
        valence=valence,
        meaning_tags=meaning_tags,
        source="glucose_tracker"
    )
    
    db.commit()
    
    return perspective_note, entries[0] if entries else None


# ============================================================================
# EXAMPLE: FULL CASE SETUP
# ============================================================================

def setup_plaintiff_case(
    db: Session,
    legal_name: str,
    case_id: UUID,
    observer_id: Optional[UUID] = None
) -> Tuple[Party, PersonaToken]:
    """
    Set up a plaintiff with full phenomenological evidence infrastructure.
    
    After calling this, the plaintiff has:
    1. A Party record (legal identity)
    2. A PersonaToken (cryptographic anchor)
    3. An empty attestation chain ready to receive entries
    
    Now you can:
    - Record their pain states
    - Capture their perspective notes
    - Link everything to facts and evidence
    - Build the duty → breach → harm chain
    """
    bridge = IntentionalityBridge(db)
    
    party, persona_token = bridge.create_party_with_persona(
        legal_name=legal_name,
        role=PartyRole.PLAINTIFF,
        case_id=case_id,
        observer_id=observer_id
    )
    
    db.commit()
    
    print(f"Created plaintiff: {legal_name}")
    print(f"  Party ID: {party.id}")
    print(f"  PersonaToken ID: {persona_token.id}")
    print(f"  Ready to receive phenomenological data")
    
    return party, persona_token
