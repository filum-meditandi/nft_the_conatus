"""
Canonical JSON Specification for Attestation Hashing

This module defines the EXACT rules for serializing domain objects to JSON
for cryptographic hashing. Any change to these rules would break hash
verification for all existing entries.

RULES (immutable once in production):
1. Keys are sorted alphabetically
2. Separators are (',', ':') with no whitespace
3. None values are serialized as JSON null
4. Absent/missing fields are NOT included (vs null which IS included)
5. Datetimes are ISO 8601 with timezone, truncated to seconds
   Format: YYYY-MM-DDTHH:MM:SS+HH:MM (no milliseconds)
6. UUIDs are lowercase hyphenated strings
7. Floats use standard Python repr (no trailing zeros forced)
8. Lists preserve order
9. Nested dicts follow same rules recursively
10. Encoding is UTF-8

VERSIONING:
- Current version: 1
- The version is NOT included in the hash itself
- If rules change, we increment version and store it in AttestedEntry
- Old entries remain verifiable under their original version rules
"""

import json
from datetime import datetime, date
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID


CANONICAL_VERSION = 1


class CanonicalJSONEncoder(json.JSONEncoder):
    """
    JSON encoder that produces deterministic, canonical output.
    
    This encoder ensures identical objects always produce identical JSON,
    which is essential for reproducible hashing.
    """
    
    def default(self, obj: Any) -> Any:
        if isinstance(obj, UUID):
            # Rule 6: UUIDs as lowercase hyphenated strings
            return str(obj).lower()
        
        if isinstance(obj, datetime):
            # Rule 5: ISO 8601 with timezone, truncated to seconds
            if obj.tzinfo is None:
                raise ValueError(
                    f"Datetime must be timezone-aware for canonical serialization: {obj}"
                )
            # Truncate to seconds (remove microseconds)
            truncated = obj.replace(microsecond=0)
            return truncated.isoformat()
        
        if isinstance(obj, date):
            # Dates as ISO format
            return obj.isoformat()
        
        if isinstance(obj, Decimal):
            # Decimals as floats
            return float(obj)
        
        if isinstance(obj, bytes):
            # Bytes as hex string
            return obj.hex()
        
        if isinstance(obj, set):
            # Sets as sorted lists for determinism
            return sorted(list(obj), key=str)
        
        return super().default(obj)


def to_canonical_json(obj: dict) -> str:
    """
    Serialize a dictionary to canonical JSON for hashing.
    
    This function MUST produce identical output for identical input,
    regardless of dict key insertion order or Python version.
    
    Args:
        obj: Dictionary to serialize (must not contain non-serializable types)
    
    Returns:
        Canonical JSON string suitable for hashing
    
    Example:
        >>> to_canonical_json({"b": 2, "a": 1})
        '{"a":1,"b":2}'
    """
    return json.dumps(
        obj,
        cls=CanonicalJSONEncoder,
        sort_keys=True,           # Rule 1: alphabetical keys
        separators=(',', ':'),    # Rule 2: no whitespace
        ensure_ascii=False        # Allow UTF-8 directly
    )


def build_perspective_note_payload(
    id: UUID,
    party_id: UUID,
    fact_id: Optional[UUID],
    attention_event_id: Optional[UUID],
    title: Optional[str],
    body: str,
    valence: Optional[str],
    meaning_tags: Optional[list],
    created_at: datetime
) -> dict:
    """
    Build the canonical payload dict for a PerspectiveNote.
    
    Rule 3: None values become JSON null
    Rule 4: We explicitly include all fields (even if None) for consistency
    """
    return {
        "id": id,
        "party_id": party_id,
        "fact_id": fact_id,                         # May be None → null
        "attention_event_id": attention_event_id,   # May be None → null
        "title": title,                             # May be None → null
        "body": body,
        "valence": valence,                         # May be None → null
        "meaning_tags": meaning_tags,               # May be None → null
        "created_at": created_at
    }


def build_pain_state_payload(
    id: UUID,
    party_id: UUID,
    fact_id: Optional[UUID],
    attention_event_id: Optional[UUID],
    recorded_at: datetime,
    scale_type: str,
    value: float,
    location: Optional[str],
    quality: Optional[str],
    functional_impact: Optional[dict],
    source: Optional[str]
) -> dict:
    """
    Build the canonical payload dict for a PainState.
    """
    return {
        "id": id,
        "party_id": party_id,
        "fact_id": fact_id,
        "attention_event_id": attention_event_id,
        "recorded_at": recorded_at,
        "scale_type": scale_type,
        "value": value,
        "location": location,
        "quality": quality,
        "functional_impact": functional_impact,
        "source": source
    }


def build_fact_payload(
    id: UUID,
    party_id: Optional[UUID],
    case_id: Optional[UUID],
    occurred_at: Optional[datetime],
    category: str,
    statement: str,
    is_objective: bool,
    created_by_party_id: Optional[UUID],
    created_at: datetime
) -> dict:
    """
    Build the canonical payload dict for a Fact.
    """
    return {
        "id": id,
        "party_id": party_id,
        "case_id": case_id,
        "occurred_at": occurred_at,
        "category": category,
        "statement": statement,
        "is_objective": is_objective,
        "created_by_party_id": created_by_party_id,
        "created_at": created_at
    }


# ============================================================================
# VERIFICATION UTILITIES
# ============================================================================

def verify_canonical_json_determinism():
    """
    Self-test to verify canonical JSON produces deterministic output.
    
    Run this on startup or in CI to catch any environment-specific issues.
    """
    from datetime import timezone as tz
    
    test_cases = [
        # Basic dict ordering
        ({"z": 1, "a": 2}, '{"a":2,"z":1}'),
        
        # Nested dict ordering
        ({"b": {"y": 1, "x": 2}, "a": 3}, '{"a":3,"b":{"x":2,"y":1}}'),
        
        # None handling
        ({"a": None, "b": 1}, '{"a":null,"b":1}'),
        
        # UUID handling
        (
            {"id": UUID("12345678-1234-5678-1234-567812345678")},
            '{"id":"12345678-1234-5678-1234-567812345678"}'
        ),
        
        # Datetime handling (must have timezone)
        (
            {"ts": datetime(2024, 3, 16, 14, 30, 0, tzinfo=tz.utc)},
            '{"ts":"2024-03-16T14:30:00+00:00"}'
        ),
        
        # Float handling
        ({"v": 7.5}, '{"v":7.5}'),
        
        # List ordering preserved
        ({"items": [3, 1, 2]}, '{"items":[3,1,2]}'),
    ]
    
    for input_dict, expected_json in test_cases:
        result = to_canonical_json(input_dict)
        assert result == expected_json, f"Expected {expected_json}, got {result}"
    
    return True


# ============================================================================
# HASH COMPUTATION
# ============================================================================

import hashlib


def compute_payload_hash(payload: dict) -> str:
    """
    Compute SHA-256 hash of a canonical payload.
    
    Returns lowercase hex string (64 characters).
    """
    canonical = to_canonical_json(payload)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def compute_entry_hash(
    prev_hash: Optional[str],
    payload_hash: str,
    persona_token_id: UUID,
    sequence_number: int,
    created_at: datetime
) -> str:
    """
    Compute the chain entry hash.
    
    Formula:
        entry_hash = SHA256(prev_hash || payload_hash || persona_token_id || sequence || timestamp)
    
    Where || is string concatenation with | delimiter.
    
    For the first entry (genesis), prev_hash is the literal string "GENESIS".
    """
    components = [
        prev_hash if prev_hash else "GENESIS",
        payload_hash,
        str(persona_token_id).lower(),
        str(sequence_number),
        created_at.replace(microsecond=0).isoformat()
    ]
    combined = "|".join(components)
    return hashlib.sha256(combined.encode('utf-8')).hexdigest()


if __name__ == "__main__":
    # Run self-test
    verify_canonical_json_determinism()
    print("✓ Canonical JSON determinism verified")
    
    # Example usage
    from datetime import timezone as tz
    
    payload = build_pain_state_payload(
        id=UUID("12345678-1234-5678-1234-567812345678"),
        party_id=UUID("abcdefab-abcd-abcd-abcd-abcdefabcdef"),
        fact_id=None,
        attention_event_id=None,
        recorded_at=datetime(2024, 3, 16, 14, 30, 0, tzinfo=tz.utc),
        scale_type="0-10",
        value=7.0,
        location="neck",
        quality="burning",
        functional_impact={"sleep": 3},
        source="sms"
    )
    
    canonical = to_canonical_json(payload)
    hash_value = compute_payload_hash(payload)
    
    print(f"\nCanonical JSON:\n{canonical}")
    print(f"\nPayload hash: {hash_value}")
