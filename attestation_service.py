"""
Attestation Service

Handles the cryptographic chaining of perspective data into the attested ledger.
Every new PerspectiveNote or PainState gets:
1. Canonical JSON serialization
2. Payload hash computation
3. Chain hash computation (linking to previous entry)
4. AttestedEntry creation

This guarantees tamper-evident, temporally-ordered records of the plaintiff's perspective.
"""

from datetime import datetime, timezone
from typing import Optional, Union, Tuple
from uuid import UUID

from sqlalchemy import select, func, text
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from models import (
    AttestedEntry,
    PersonaToken,
    PerspectiveNote,
    PainState,
    Party
)


class ChainForkError(Exception):
    """Raised when a chain fork is detected during attestation."""
    pass


class AttestationService:
    """
    Service for creating and verifying attested entries in the phenomenological ledger.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_latest_entry(
        self, 
        persona_token_id: UUID,
        for_update: bool = False
    ) -> Optional[AttestedEntry]:
        """
        Get the most recent attested entry for a persona.
        
        Args:
            persona_token_id: The persona's token ID
            for_update: If True, acquires a row-level lock (SELECT ... FOR UPDATE)
                       to prevent race conditions during chain extension.
        """
        stmt = (
            select(AttestedEntry)
            .where(AttestedEntry.persona_token_id == persona_token_id)
            .order_by(AttestedEntry.sequence_number.desc())
            .limit(1)
        )
        
        if for_update:
            stmt = stmt.with_for_update()
        
        return self.db.execute(stmt).scalar_one_or_none()
    
    def get_latest_entry_locked(self, persona_token_id: UUID) -> Optional[AttestedEntry]:
        """
        Get latest entry with row-level lock for safe chain extension.
        
        Uses SELECT ... FOR UPDATE to prevent concurrent attestations
        from creating chain forks.
        """
        return self.get_latest_entry(persona_token_id, for_update=True)
    
    def get_next_sequence_number(self, persona_token_id: UUID) -> int:
        """Get the next sequence number for a persona's chain."""
        latest = self.get_latest_entry(persona_token_id)
        return (latest.sequence_number + 1) if latest else 1
    
    def attest_perspective_note(
        self,
        note: PerspectiveNote,
        persona_token_id: UUID,
        signature: Optional[str] = None,
        signer_key_id: Optional[str] = None
    ) -> AttestedEntry:
        """
        Create an attested entry for a PerspectiveNote.
        
        This:
        1. Serializes the note to canonical JSON
        2. Computes the payload hash
        3. Chains it to the previous entry
        4. Creates the AttestedEntry record
        """
        return self._create_attested_entry(
            domain_table="PerspectiveNote",
            domain_id=note.id,
            canonical_json=note.to_canonical_json(),
            persona_token_id=persona_token_id,
            signature=signature,
            signer_key_id=signer_key_id
        )
    
    def attest_pain_state(
        self,
        pain_state: PainState,
        persona_token_id: UUID,
        signature: Optional[str] = None,
        signer_key_id: Optional[str] = None
    ) -> AttestedEntry:
        """
        Create an attested entry for a PainState.
        """
        return self._create_attested_entry(
            domain_table="PainState",
            domain_id=pain_state.id,
            canonical_json=pain_state.to_canonical_json(),
            persona_token_id=persona_token_id,
            signature=signature,
            signer_key_id=signer_key_id
        )
    
    def _create_attested_entry(
        self,
        domain_table: str,
        domain_id: UUID,
        canonical_json: str,
        persona_token_id: UUID,
        signature: Optional[str] = None,
        signer_key_id: Optional[str] = None,
        max_retries: int = 3
    ) -> AttestedEntry:
        """
        Internal method to create a chained attested entry.
        
        Uses SELECT ... FOR UPDATE to prevent race conditions.
        The unique constraint on (persona_token_id, sequence_number) provides
        a second layer of protection against chain forks.
        
        Args:
            max_retries: Number of times to retry on IntegrityError (concurrent insert)
        """
        for attempt in range(max_retries):
            try:
                # Lock the latest entry to prevent concurrent extensions
                latest_entry = self.get_latest_entry_locked(persona_token_id)
                prev_hash = latest_entry.entry_hash if latest_entry else None
                sequence_number = (latest_entry.sequence_number + 1) if latest_entry else 1
                
                # Compute hashes
                payload_hash = AttestedEntry.compute_payload_hash(canonical_json)
                created_at = datetime.now(timezone.utc)
                entry_hash = AttestedEntry.compute_entry_hash(
                    prev_hash=prev_hash,
                    payload_hash=payload_hash,
                    persona_token_id=persona_token_id,
                    sequence_number=sequence_number,
                    created_at=created_at
                )
                
                # Create entry
                entry = AttestedEntry(
                    persona_token_id=persona_token_id,
                    domain_table=domain_table,
                    domain_id=domain_id,
                    payload_hash=payload_hash,
                    prev_hash=prev_hash,
                    entry_hash=entry_hash,
                    sequence_number=sequence_number,
                    signature=signature,
                    signer_key_id=signer_key_id,
                    created_at=created_at
                )
                
                self.db.add(entry)
                self.db.flush()  # Triggers the unique constraint check
                
                return entry
                
            except IntegrityError as e:
                # Unique constraint violation - concurrent attestation happened
                self.db.rollback()
                
                if attempt < max_retries - 1:
                    # Retry with fresh chain state
                    continue
                else:
                    raise ChainForkError(
                        f"Failed to extend chain after {max_retries} attempts. "
                        f"Concurrent attestations may be causing contention. "
                        f"persona_token_id={persona_token_id}"
                    ) from e
    
    def verify_chain(
        self,
        persona_token_id: UUID,
        from_sequence: int = 1,
        to_sequence: Optional[int] = None,
        recompute_payload_hashes: bool = False
    ) -> Tuple[bool, Optional[int], Optional[str]]:
        """
        Verify the integrity of a persona's attestation chain.
        
        Two levels of verification:
        1. Chain integrity: each entry's prev_hash matches the previous entry_hash
        2. Payload integrity (if recompute_payload_hashes=True): refetch the domain
           objects and verify their canonical JSON still hashes to payload_hash
        
        Args:
            persona_token_id: The persona to verify
            from_sequence: Start verification from this sequence number
            to_sequence: End at this sequence (or verify to end)
            recompute_payload_hashes: If True, also verify payloads haven't changed
        
        Returns:
            (is_valid, first_broken_sequence, error_message)
        """
        stmt = (
            select(AttestedEntry)
            .where(AttestedEntry.persona_token_id == persona_token_id)
            .where(AttestedEntry.sequence_number >= from_sequence)
        )
        if to_sequence:
            stmt = stmt.where(AttestedEntry.sequence_number <= to_sequence)
        stmt = stmt.order_by(AttestedEntry.sequence_number.asc())
        
        entries = list(self.db.execute(stmt).scalars())
        
        if not entries:
            return (True, None, None)
        
        prev_entry = None
        
        # If starting from > 1, we need to fetch the previous entry
        if from_sequence > 1:
            prev_stmt = (
                select(AttestedEntry)
                .where(AttestedEntry.persona_token_id == persona_token_id)
                .where(AttestedEntry.sequence_number == from_sequence - 1)
            )
            prev_entry = self.db.execute(prev_stmt).scalar_one_or_none()
        
        for entry in entries:
            # Verify chain linkage
            if not entry.verify_chain_integrity(prev_entry):
                expected_prev = prev_entry.entry_hash if prev_entry else None
                return (
                    False,
                    entry.sequence_number,
                    f"Chain broken at sequence {entry.sequence_number}. "
                    f"Expected prev_hash={expected_prev}, got {entry.prev_hash}"
                )
            
            # Optionally verify payload hasn't changed
            if recompute_payload_hashes:
                payload_valid, payload_error = self._verify_payload(entry)
                if not payload_valid:
                    return (
                        False,
                        entry.sequence_number,
                        f"Payload mismatch at sequence {entry.sequence_number}: {payload_error}"
                    )
            
            prev_entry = entry
        
        return (True, None, None)
    
    def _verify_payload(self, entry: AttestedEntry) -> Tuple[bool, Optional[str]]:
        """
        Verify that a domain object's current state matches its attested hash.
        
        This catches cases where someone modified the domain object directly
        in the database without going through the attestation system.
        """
        domain_table = entry.domain_table
        domain_id = entry.domain_id
        
        if domain_table == "PerspectiveNote":
            obj = self.db.query(PerspectiveNote).filter(PerspectiveNote.id == domain_id).first()
            if not obj:
                return (False, f"PerspectiveNote {domain_id} not found")
            current_hash = AttestedEntry.compute_payload_hash(obj.to_canonical_json())
            
        elif domain_table == "PainState":
            obj = self.db.query(PainState).filter(PainState.id == domain_id).first()
            if not obj:
                return (False, f"PainState {domain_id} not found")
            current_hash = AttestedEntry.compute_payload_hash(obj.to_canonical_json())
            
        else:
            # Unknown domain table - can't verify payload
            return (True, None)
        
        if current_hash != entry.payload_hash:
            return (
                False,
                f"Expected hash {entry.payload_hash[:16]}..., "
                f"got {current_hash[:16]}... - object may have been modified"
            )
        
        return (True, None)
    
    def generate_verification_report(
        self,
        persona_token_id: UUID,
        include_payload_verification: bool = True
    ) -> dict:
        """
        Generate a comprehensive verification report for court/audit use.
        
        Returns a detailed report including:
        - Chain summary
        - Verification result
        - List of all entries with their hashes
        - Any anomalies detected
        """
        summary = self.get_chain_summary(persona_token_id)
        
        is_valid, broken_at, error = self.verify_chain(
            persona_token_id=persona_token_id,
            recompute_payload_hashes=include_payload_verification
        )
        
        # Get all entries for the detailed listing
        stmt = (
            select(AttestedEntry)
            .where(AttestedEntry.persona_token_id == persona_token_id)
            .order_by(AttestedEntry.sequence_number.asc())
        )
        entries = list(self.db.execute(stmt).scalars())
        
        entry_details = []
        for e in entries:
            entry_details.append({
                "sequence": e.sequence_number,
                "domain_table": e.domain_table,
                "domain_id": str(e.domain_id),
                "payload_hash": e.payload_hash,
                "prev_hash": e.prev_hash,
                "entry_hash": e.entry_hash,
                "created_at": e.created_at.isoformat(),
                "has_signature": e.signature is not None
            })
        
        return {
            "persona_token_id": str(persona_token_id),
            "verification_timestamp": datetime.now(timezone.utc).isoformat(),
            "chain_summary": summary,
            "verification_result": {
                "is_valid": is_valid,
                "broken_at_sequence": broken_at,
                "error_message": error
            },
            "entries": entry_details,
            "entry_count": len(entries),
            "payload_verification_included": include_payload_verification
        }
    
    def get_chain_summary(self, persona_token_id: UUID) -> dict:
        """
        Get a summary of the attestation chain for a persona.
        """
        count_stmt = (
            select(func.count(AttestedEntry.id))
            .where(AttestedEntry.persona_token_id == persona_token_id)
        )
        count = self.db.execute(count_stmt).scalar()
        
        latest = self.get_latest_entry(persona_token_id)
        
        first_stmt = (
            select(AttestedEntry)
            .where(AttestedEntry.persona_token_id == persona_token_id)
            .order_by(AttestedEntry.sequence_number.asc())
            .limit(1)
        )
        first = self.db.execute(first_stmt).scalar_one_or_none()
        
        # Count by domain table
        domain_counts_stmt = (
            select(AttestedEntry.domain_table, func.count(AttestedEntry.id))
            .where(AttestedEntry.persona_token_id == persona_token_id)
            .group_by(AttestedEntry.domain_table)
        )
        domain_counts = dict(self.db.execute(domain_counts_stmt).all())
        
        return {
            "persona_token_id": str(persona_token_id),
            "total_entries": count,
            "first_entry": {
                "sequence": first.sequence_number if first else None,
                "created_at": first.created_at.isoformat() if first else None,
                "entry_hash": first.entry_hash if first else None
            } if first else None,
            "latest_entry": {
                "sequence": latest.sequence_number if latest else None,
                "created_at": latest.created_at.isoformat() if latest else None,
                "entry_hash": latest.entry_hash if latest else None
            } if latest else None,
            "entries_by_type": domain_counts
        }


def get_or_create_persona_for_party(
    db: Session,
    party_id: UUID
) -> PersonaToken:
    """
    Get or create a PersonaToken for a party.
    This is the cryptographic anchor for their existential record.
    """
    stmt = select(PersonaToken).where(PersonaToken.party_id == party_id)
    existing = db.execute(stmt).scalar_one_or_none()
    
    if existing:
        return existing
    
    token = PersonaToken(party_id=party_id)
    db.add(token)
    db.flush()  # Get the ID without committing
    
    return token
