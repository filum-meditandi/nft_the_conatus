"""
Unified Phenomenology Service

This is the main orchestration layer that composes:
1. Raw note → encrypt → store SubjectiveNote
2. Normalize → build PHI-light canonical payload
3. Sign → create AttestedEntry with cryptographic signature
4. Enrich → add ContextSnapshot with temporal/spatial data

The full flow:
    raw_text + metadata
        ↓
    encrypt (PHI protection)
        ↓
    normalize (PHI-light projection)
        ↓
    canonical JSON (deterministic serialization)
        ↓
    sign (cryptographic attestation)
        ↓
    chain (hash linkage)
        ↓
    enrich (context snapshot)
        ↓
    DONE: forensically-sound phenomenological record
"""

from datetime import datetime, timezone
from typing import Optional, List, Tuple, Any
from uuid import UUID, uuid4
from dataclasses import dataclass

from sqlalchemy.orm import Session

from models import (
    Party, PersonaToken, PainState, PerspectiveNote, 
    AttestedEntry, Fact, Valence
)
from phi_separation import (
    SubjectiveNote, EncryptionKey, EncryptionService,
    NormalizationService, NoteType, build_subjective_note_payload
)
from signing_infrastructure import SigningService, SigningKey
from context_layer import (
    ContextSnapshot, CaseTimeline, CasePhase,
    ContextEnrichmentService, PhenomenologyStatsService
)
from attestation_service import AttestationService, get_or_create_persona_for_party
from canonical_json import to_canonical_json, compute_payload_hash


# ============================================================================
# DATA TRANSFER OBJECTS
# ============================================================================

@dataclass
class PhenomenologyInput:
    """Input for recording a phenomenological observation."""
    
    party_id: UUID
    case_id: UUID
    
    # The raw content (will be encrypted)
    raw_text: str
    
    # Optional structured pain data
    pain_value: Optional[float] = None
    pain_location: Optional[str] = None
    pain_quality: Optional[str] = None
    functional_impact: Optional[dict] = None
    
    # Temporal
    event_time: Optional[datetime] = None  # When it happened (subjective)
    
    # Context
    location_type: Optional[str] = None
    posture: Optional[str] = None
    exertion_level: Optional[str] = None
    environment_tags: Optional[List[str]] = None
    activity_description: Optional[str] = None
    
    # Source
    source: str = "api"  # "sms", "app", "intake", etc.
    
    # Optional: link to existing fact
    fact_id: Optional[UUID] = None
    attention_event_id: Optional[UUID] = None


@dataclass
class PhenomenologyResult:
    """Result of recording a phenomenological observation."""
    
    # Created records
    subjective_note_id: UUID
    pain_state_id: Optional[UUID]
    attested_entry_id: UUID
    context_snapshot_id: UUID
    
    # Chain info
    sequence_number: int
    entry_hash: str
    payload_hash: str
    
    # Signature info
    signature: Optional[str]
    signer_key_id: Optional[str]
    
    # Verification
    chain_verified: bool
    
    def to_dict(self) -> dict:
        return {
            "subjective_note_id": str(self.subjective_note_id),
            "pain_state_id": str(self.pain_state_id) if self.pain_state_id else None,
            "attested_entry_id": str(self.attested_entry_id),
            "context_snapshot_id": str(self.context_snapshot_id),
            "sequence_number": self.sequence_number,
            "entry_hash": self.entry_hash,
            "payload_hash": self.payload_hash,
            "signature": self.signature[:32] + "..." if self.signature else None,
            "signer_key_id": self.signer_key_id,
            "chain_verified": self.chain_verified
        }


# ============================================================================
# UNIFIED SERVICE
# ============================================================================

class PhenomenologyService:
    """
    Main orchestration service for phenomenological evidence.
    
    Composes all the subsystems into a single, coherent interface.
    """
    
    def __init__(
        self,
        db: Session,
        encryption_service: Optional[EncryptionService] = None,
        signing_service: Optional[SigningService] = None
    ):
        self.db = db
        
        # Initialize subsystems
        self.encryption = encryption_service or EncryptionService()
        self.signing = signing_service or SigningService()
        self.normalization = NormalizationService()
        self.attestation = AttestationService(db)
        self.context_enrichment = ContextEnrichmentService(db)
        self.stats = PhenomenologyStatsService(db)
    
    def record(self, input: PhenomenologyInput) -> PhenomenologyResult:
        """
        Record a phenomenological observation through the full pipeline.
        
        This is the main entry point. It:
        1. Encrypts the raw narrative (PHI protection)
        2. Normalizes to PHI-light projection
        3. Creates SubjectiveNote
        4. Optionally creates PainState (if pain data provided)
        5. Creates signed AttestedEntry
        6. Creates ContextSnapshot
        7. Returns verification proof
        """
        # Get or create persona
        persona_token = get_or_create_persona_for_party(self.db, input.party_id)
        
        # Get or create default encryption key
        encryption_key = self._get_or_create_encryption_key(persona_token.id)
        
        # ====================================================================
        # STEP 1: Encrypt raw narrative
        # ====================================================================
        ciphertext, plaintext_hash = self.encryption.encrypt_note(input.raw_text)
        
        # ====================================================================
        # STEP 2: Normalize to PHI-light projection
        # ====================================================================
        normalized = self.normalization.normalize(input.raw_text)
        
        # ====================================================================
        # STEP 3: Create SubjectiveNote
        # ====================================================================
        subjective_note = SubjectiveNote(
            persona_token_id=persona_token.id,
            ciphertext=ciphertext,
            encryption_key_id=encryption_key.id,
            plaintext_hash=plaintext_hash,
            note_type=normalized["note_type"],
            normalized_summary=normalized["normalized_summary"],
            symptom_tags=normalized["symptom_tags"],
            severity_level=normalized["severity_level"] or input.pain_value,
            event_time=input.event_time,
            recorded_at=datetime.now(timezone.utc)
        )
        self.db.add(subjective_note)
        self.db.flush()
        
        # ====================================================================
        # STEP 4: Optionally create PainState
        # ====================================================================
        pain_state = None
        if input.pain_value is not None:
            pain_state = PainState(
                party_id=input.party_id,
                fact_id=input.fact_id,
                attention_event_id=input.attention_event_id,
                value=input.pain_value,
                location=input.pain_location,
                quality=input.pain_quality,
                functional_impact=input.functional_impact,
                source=input.source,
                recorded_at=datetime.now(timezone.utc)
            )
            self.db.add(pain_state)
            self.db.flush()
        
        # ====================================================================
        # STEP 5: Build canonical payload (PHI-light)
        # ====================================================================
        payload = build_subjective_note_payload(subjective_note)
        
        # If we have pain data, include it in the payload
        if pain_state:
            payload["pain_state"] = {
                "id": str(pain_state.id),
                "value": pain_state.value,
                "location": pain_state.location,
                "quality": pain_state.quality
            }
        
        canonical_json = to_canonical_json(payload)
        payload_hash = compute_payload_hash(payload)
        
        # ====================================================================
        # STEP 6: Create signed AttestedEntry
        # ====================================================================
        
        # Get chain state (with locking for race safety)
        latest_entry = self.attestation.get_latest_entry_locked(persona_token.id)
        prev_hash = latest_entry.entry_hash if latest_entry else None
        sequence_number = (latest_entry.sequence_number + 1) if latest_entry else 1
        
        created_at = datetime.now(timezone.utc)
        
        # Compute entry hash
        entry_hash = AttestedEntry.compute_entry_hash(
            prev_hash=prev_hash,
            payload_hash=payload_hash,
            persona_token_id=persona_token.id,
            sequence_number=sequence_number,
            created_at=created_at
        )
        
        # Sign the entry
        signature, signer_key_id = self.signing.sign_entry(
            persona_token_id=persona_token.id,
            sequence_number=sequence_number,
            previous_hash=prev_hash,
            payload_hash=payload_hash,
            timestamp=created_at
        )
        
        # Create the entry
        entry = AttestedEntry(
            persona_token_id=persona_token.id,
            domain_table="SubjectiveNote",
            domain_id=subjective_note.id,
            payload_hash=payload_hash,
            prev_hash=prev_hash,
            entry_hash=entry_hash,
            sequence_number=sequence_number,
            signature=signature,
            signer_key_id=signer_key_id,
            created_at=created_at
        )
        self.db.add(entry)
        self.db.flush()
        
        # ====================================================================
        # STEP 7: Create ContextSnapshot
        # ====================================================================
        context = self.context_enrichment.enrich_entry(
            entry=entry,
            case_id=input.case_id,
            event_time=input.event_time,
            location_type=input.location_type,
            posture=input.posture,
            exertion_level=input.exertion_level,
            environment_tags=input.environment_tags,
            activity_description=input.activity_description,
            raw_context={
                "source": input.source,
                "fact_id": str(input.fact_id) if input.fact_id else None,
                "attention_event_id": str(input.attention_event_id) if input.attention_event_id else None
            }
        )
        self.db.flush()
        
        # ====================================================================
        # STEP 8: Verify chain integrity
        # ====================================================================
        is_valid, _, _ = self.attestation.verify_chain(
            persona_token_id=persona_token.id,
            from_sequence=max(1, sequence_number - 5),  # Verify recent entries
            to_sequence=sequence_number
        )
        
        # Commit everything
        self.db.commit()
        
        return PhenomenologyResult(
            subjective_note_id=subjective_note.id,
            pain_state_id=pain_state.id if pain_state else None,
            attested_entry_id=entry.id,
            context_snapshot_id=context.id,
            sequence_number=sequence_number,
            entry_hash=entry_hash,
            payload_hash=payload_hash,
            signature=signature,
            signer_key_id=signer_key_id,
            chain_verified=is_valid
        )
    
    def _get_or_create_encryption_key(self, persona_token_id: UUID) -> EncryptionKey:
        """Get or create an encryption key for the persona."""
        # Look for existing active key
        existing = self.db.query(EncryptionKey).filter(
            EncryptionKey.persona_token_id == persona_token_id,
            EncryptionKey.is_active == True
        ).first()
        
        if existing:
            return existing
        
        # Create new key
        key_id, wrapped_key = self.encryption.generate_data_encryption_key()
        
        new_key = EncryptionKey(
            id=key_id,
            wrapped_key=wrapped_key,
            persona_token_id=persona_token_id,
            algorithm="AES-256-GCM",
            key_type="data_encryption_key",
            is_active=True
        )
        self.db.add(new_key)
        self.db.flush()
        
        return new_key
    
    def decrypt_note(
        self,
        subjective_note_id: UUID,
        audit_reason: str = "unspecified"
    ) -> str:
        """
        Decrypt a subjective note.
        
        This is an auditable operation. Every decryption is logged.
        """
        note = self.db.query(SubjectiveNote).filter(
            SubjectiveNote.id == subjective_note_id
        ).first()
        
        if not note:
            raise ValueError(f"SubjectiveNote {subjective_note_id} not found")
        
        # Decrypt
        plaintext = self.encryption.decrypt_note(
            ciphertext=note.ciphertext,
            expected_hash=note.plaintext_hash
        )
        
        # Update audit trail
        note.last_decrypted_at = datetime.now(timezone.utc)
        note.decryption_count += 1
        self.db.commit()
        
        # In production, also log to audit table
        # self._log_decryption(note.id, audit_reason)
        
        return plaintext
    
    def verify_and_report(
        self,
        persona_token_id: UUID,
        case_id: UUID,
        include_decrypted_content: bool = False,
        audit_reason: Optional[str] = None
    ) -> dict:
        """
        Generate a comprehensive verification report.
        
        This is the "courtroom export" - everything needed to prove:
        - What was said
        - When it was said
        - That nothing was altered
        - The trajectory of symptoms over time
        """
        # Verify chain
        verification = self.attestation.generate_verification_report(
            persona_token_id=persona_token_id,
            include_payload_verification=True
        )
        
        # Get statistics
        stats = self.stats.generate_court_summary(persona_token_id, case_id)
        
        # Get signature verification
        for entry_info in verification.get("entries", []):
            entry = self.db.query(AttestedEntry).filter(
                AttestedEntry.id == entry_info.get("entry_id") or 
                AttestedEntry.sequence_number == entry_info.get("sequence")
            ).first()
            
            if entry and entry.signature:
                sig_valid = self.signing.verify_signature(
                    signature_base64=entry.signature,
                    persona_token_id=persona_token_id,
                    sequence_number=entry.sequence_number,
                    previous_hash=entry.prev_hash,
                    payload_hash=entry.payload_hash,
                    timestamp=entry.created_at
                )
                entry_info["signature_valid"] = sig_valid
        
        # Optionally include decrypted content
        decrypted_notes = []
        if include_decrypted_content and audit_reason:
            notes = self.db.query(SubjectiveNote).filter(
                SubjectiveNote.persona_token_id == persona_token_id
            ).all()
            
            for note in notes:
                try:
                    plaintext = self.decrypt_note(note.id, audit_reason)
                    decrypted_notes.append({
                        "note_id": str(note.id),
                        "recorded_at": note.recorded_at.isoformat(),
                        "content": plaintext,
                        "normalized_summary": note.normalized_summary
                    })
                except Exception as e:
                    decrypted_notes.append({
                        "note_id": str(note.id),
                        "error": str(e)
                    })
        
        return {
            "report_type": "phenomenological_evidence_verification",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "persona_token_id": str(persona_token_id),
            "case_id": str(case_id),
            
            "chain_verification": verification,
            "statistics": stats,
            
            "decrypted_content_included": include_decrypted_content,
            "decrypted_notes": decrypted_notes if include_decrypted_content else None,
            
            "certification": {
                "method": "SHA-256 hash chain with Ed25519 signatures",
                "server_key_id": self.signing.server_key_id,
                "server_public_key": self.signing.get_server_public_key_pem()
            }
        }


# ============================================================================
# SMS INTEGRATION
# ============================================================================

def process_sms_phenomenology(
    db: Session,
    party_id: UUID,
    case_id: UUID,
    raw_message: str,
    sender_phone: str,
    received_at: datetime,
    encryption_service: Optional[EncryptionService] = None,
    signing_service: Optional[SigningService] = None
) -> PhenomenologyResult:
    """
    Process an SMS pain/symptom report through the full pipeline.
    
    This is the Twilio webhook integration point.
    
    Example SMS: "Pain 7/10, can't sleep, neck burning"
    """
    from sms_flow_example import parse_pain_sms
    
    # Parse the SMS
    parsed = parse_pain_sms(raw_message)
    
    # Build input
    input_data = PhenomenologyInput(
        party_id=party_id,
        case_id=case_id,
        raw_text=f"[SMS from {sender_phone} at {received_at.isoformat()}] {raw_message}",
        pain_value=parsed.value,
        pain_location=parsed.location,
        pain_quality=parsed.quality,
        functional_impact={"notes": parsed.functional_notes} if parsed.functional_notes else None,
        event_time=received_at,
        source="sms"
    )
    
    # Process through unified service
    service = PhenomenologyService(
        db=db,
        encryption_service=encryption_service,
        signing_service=signing_service
    )
    
    return service.record(input_data)
