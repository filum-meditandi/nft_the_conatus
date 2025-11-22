"""
Example: SMS Pain Report Flow

This demonstrates how a single SMS from your Twilio tracker becomes:
1. An AttentionEvent (lived moment)
2. A PainState (structured intensity)
3. A PerspectiveNote (narrative context)
4. An AttestedEntry on the plaintiff's hash chain

Example SMS: "Pain 7/10, can't sleep, neck burning"
"""

import re
from datetime import datetime, timezone
from typing import Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from models import (
    Party, PersonaToken, Fact, PerspectiveNote, PainState,
    AttestedEntry, Valence, FactCategory, PartyRole
)
from attestation_service import AttestationService, get_or_create_persona_for_party


# ============================================================================
# SMS PARSING
# ============================================================================

class ParsedPainReport:
    """Structured data extracted from a pain SMS."""
    
    def __init__(
        self,
        value: Optional[float] = None,
        location: Optional[str] = None,
        quality: Optional[str] = None,
        functional_notes: Optional[str] = None,
        raw_message: str = ""
    ):
        self.value = value
        self.location = location
        self.quality = quality
        self.functional_notes = functional_notes
        self.raw_message = raw_message


def parse_pain_sms(message: str) -> ParsedPainReport:
    """
    Parse a pain report SMS into structured data.
    
    Handles messages like:
    - "Pain 7/10, can't sleep, neck burning"
    - "pain level 8"
    - "7/10 pain neck sharp"
    - "my neck hurts 6 out of 10"
    """
    message_lower = message.lower()
    result = ParsedPainReport(raw_message=message)
    
    # Extract pain value
    # Pattern: "7/10" or "7 out of 10" or "pain 7" or "level 7"
    patterns = [
        r'(\d+(?:\.\d+)?)\s*/\s*10',           # 7/10
        r'(\d+(?:\.\d+)?)\s+out\s+of\s+10',    # 7 out of 10
        r'pain\s+(?:level\s+)?(\d+(?:\.\d+)?)', # pain 7 or pain level 7
        r'level\s+(\d+(?:\.\d+)?)',             # level 7
        r'^(\d+(?:\.\d+)?)\s*/\s*10',           # starts with 7/10
    ]
    
    for pattern in patterns:
        match = re.search(pattern, message_lower)
        if match:
            result.value = min(float(match.group(1)), 10.0)
            break
    
    # Extract location
    locations = {
        'neck': ['neck', 'cervical'],
        'low back': ['low back', 'lower back', 'lumbar'],
        'upper back': ['upper back', 'thoracic'],
        'headache': ['headache', 'head'],
        'shoulder': ['shoulder'],
        'arm': ['arm'],
        'leg': ['leg'],
        'knee': ['knee'],
        'hip': ['hip'],
    }
    
    for loc, keywords in locations.items():
        if any(kw in message_lower for kw in keywords):
            result.location = loc
            break
    
    # Extract quality
    qualities = {
        'burning': ['burning', 'burn'],
        'sharp': ['sharp', 'stabbing'],
        'dull': ['dull', 'aching', 'ache'],
        'throbbing': ['throbbing', 'pulsing'],
        'shooting': ['shooting', 'radiating'],
        'tingling': ['tingling', 'pins and needles'],
        'numbness': ['numb', 'numbness'],
    }
    
    for qual, keywords in qualities.items():
        if any(kw in message_lower for kw in keywords):
            result.quality = qual
            break
    
    # Extract functional notes
    functional_patterns = [
        r"can't\s+(\w+)",
        r"unable\s+to\s+(\w+)",
        r"hard\s+to\s+(\w+)",
        r"trouble\s+(\w+ing)",
    ]
    
    functional_notes = []
    for pattern in functional_patterns:
        matches = re.findall(pattern, message_lower)
        functional_notes.extend(matches)
    
    if functional_notes:
        result.functional_notes = ", ".join(functional_notes)
    
    return result


# ============================================================================
# FULL FLOW EXAMPLE
# ============================================================================

def process_sms_pain_report(
    db: Session,
    party_id: UUID,
    raw_message: str,
    sender_phone: str,
    received_at: datetime,
    related_fact_id: Optional[UUID] = None,
    attention_event_id: Optional[UUID] = None
) -> Tuple[PainState, PerspectiveNote, AttestedEntry, AttestedEntry]:
    """
    Process an SMS pain report through the full phenomenological evidence pipeline.
    
    Returns: (pain_state, perspective_note, pain_attestation, note_attestation)
    """
    # 1. Parse the SMS
    parsed = parse_pain_sms(raw_message)
    
    # 2. Get or create the party's PersonaToken
    persona_token = get_or_create_persona_for_party(db, party_id)
    
    # 3. Create the PerspectiveNote (captures the raw voice)
    note = PerspectiveNote(
        party_id=party_id,
        fact_id=related_fact_id,
        attention_event_id=attention_event_id,
        title=None,
        body=f"[SMS {received_at.strftime('%Y-%m-%d %H:%M')}] {raw_message}",
        valence=Valence.PAIN if (parsed.value and parsed.value >= 5) else None,
        meaning_tags=["pain_report", "sms"]
    )
    db.add(note)
    db.flush()
    
    # 4. Create the PainState (structured data)
    pain_state = PainState(
        party_id=party_id,
        fact_id=related_fact_id,
        attention_event_id=attention_event_id,
        value=parsed.value or 5.0,  # Default to moderate if not parsed
        scale_type="0-10",
        location=parsed.location,
        quality=parsed.quality,
        functional_impact={
            "notes": parsed.functional_notes
        } if parsed.functional_notes else None,
        source="sms",
        recorded_at=received_at
    )
    db.add(pain_state)
    db.flush()
    
    # 5. Attest both to the chain
    attestation_service = AttestationService(db)
    
    note_attestation = attestation_service.attest_perspective_note(
        note=note,
        persona_token_id=persona_token.id
    )
    
    pain_attestation = attestation_service.attest_pain_state(
        pain_state=pain_state,
        persona_token_id=persona_token.id
    )
    
    db.commit()
    
    return pain_state, note, pain_attestation, note_attestation


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

def example_usage():
    """
    Demonstrates the full flow from SMS to attested record.
    
    In production, this would be called from your Twilio webhook handler.
    """
    
    # Simulated database session (in production, use your actual session)
    # db = SessionLocal()
    
    example_messages = [
        "Pain 7/10, can't sleep, neck burning",
        "low back pain 6 out of 10, hard to sit",
        "headache 8/10 throbbing",
        "my neck hurts, sharp pain, maybe 5/10",
    ]
    
    print("=" * 60)
    print("SMS Pain Report Parsing Examples")
    print("=" * 60)
    
    for msg in example_messages:
        parsed = parse_pain_sms(msg)
        print(f"\nRaw: {msg}")
        print(f"  Value: {parsed.value}")
        print(f"  Location: {parsed.location}")
        print(f"  Quality: {parsed.quality}")
        print(f"  Functional: {parsed.functional_notes}")
    
    print("\n" + "=" * 60)
    print("Attestation Chain Example")
    print("=" * 60)
    
    # In production, this would create real database entries
    print("""
    When "Pain 7/10, can't sleep, neck burning" is processed:
    
    1. PerspectiveNote created:
       - body: "[SMS 2024-03-16 14:30] Pain 7/10, can't sleep, neck burning"
       - valence: PAIN
       - meaning_tags: ["pain_report", "sms"]
    
    2. PainState created:
       - value: 7.0
       - location: "neck"
       - quality: "burning"
       - functional_impact: {"notes": "sleep"}
       - source: "sms"
    
    3. AttestedEntry #1 (PerspectiveNote):
       - sequence_number: N
       - payload_hash: SHA256(canonical_json)
       - prev_hash: <hash of entry N-1>
       - entry_hash: SHA256(prev_hash + payload_hash + metadata)
    
    4. AttestedEntry #2 (PainState):
       - sequence_number: N+1
       - payload_hash: SHA256(canonical_json)
       - prev_hash: <hash of entry N>
       - entry_hash: SHA256(prev_hash + payload_hash + metadata)
    
    The plaintiff now has a tamper-evident, temporally-ordered record
    that can be verified at any time:
    
    "This is what the plaintiff said, when they said it, and here's
    the unbroken cryptographic chain proving nothing was altered."
    """)


if __name__ == "__main__":
    example_usage()
