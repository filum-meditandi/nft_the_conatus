"""
System Integration Layer

This module provides the unified entry points that ensure all components
of the phenomenological evidence system work together correctly.

Integration points:
1. Capture → Chain → HMM → Context (full pipeline)
2. Phone registry → Persona lookup → Case context
3. NFT payload → Signing → Verification
4. Feature extraction → HMM inference → Statistics

This is the "glue" that makes the system coherent.
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID
from dataclasses import dataclass

from sqlalchemy.orm import Session

# Core models
from models import (
    Party, PersonaToken, PainState, PerspectiveNote,
    AttestedEntry, Fact, PartyRole
)

# PHI separation
from phi_separation import (
    SubjectiveNote, EncryptionKey, EncryptionService,
    NormalizationService, build_subjective_note_payload
)

# Signing
from signing_infrastructure import SigningService, SigningKey

# Attestation
from attestation_service import AttestationService, get_or_create_persona_for_party

# Context
from context_layer import (
    ContextSnapshot, CaseTimeline, ContextEnrichmentService,
    PhenomenologyStatsService
)

# HMM
from hmm_features import FeatureVector, FeatureExtractionService, FEATURE_SCHEMA
from hmm_inference import (
    HiddenStateModel, StateInference, HMMInferenceEngine,
    TrajectoryAnalysisService, create_default_pain_trajectory_model
)

# Phone registry
from phone_registry import PhoneRegistry, PhoneRegistryService

# NFT
from nft_payload import NFTPayloadBuilder, NFTPayload

# Canonical JSON
from canonical_json import to_canonical_json, compute_payload_hash


# ============================================================================
# INTEGRATED CAPTURE RESULT
# ============================================================================

@dataclass
class IntegratedCaptureResult:
    """
    Complete result from the integrated capture pipeline.
    
    Includes all artifacts created across all subsystems.
    """
    # Core records
    subjective_note_id: UUID
    pain_state_id: Optional[UUID]
    attested_entry_id: UUID
    
    # Context
    context_snapshot_id: UUID
    case_phase: Optional[str]
    days_since_injury: Optional[int]
    
    # Chain
    sequence_number: int
    entry_hash: str
    payload_hash: str
    signature: Optional[str]
    signer_key_id: Optional[str]
    
    # HMM inference (if model available)
    feature_vector_id: Optional[UUID]
    inferred_state: Optional[str]
    state_confidence: Optional[float]
    is_anomaly: bool
    
    # Verification
    chain_verified: bool


# ============================================================================
# INTEGRATED PHENOMENOLOGY SERVICE
# ============================================================================

class IntegratedPhenomenologyService:
    """
    The unified service that orchestrates all subsystems.
    
    This is the single entry point for capturing phenomenological data.
    It ensures:
    1. PHI is properly encrypted
    2. Chain is properly extended with signatures
    3. Context is enriched
    4. HMM inference is triggered
    5. All links between components are established
    """
    
    def __init__(
        self,
        db: Session,
        encryption_service: Optional[EncryptionService] = None,
        signing_service: Optional[SigningService] = None,
        default_hmm_model_id: Optional[UUID] = None
    ):
        self.db = db
        
        # Initialize all subsystems
        self.encryption = encryption_service or EncryptionService()
        self.signing = signing_service or SigningService()
        self.normalization = NormalizationService()
        self.attestation = AttestationService(db)
        self.context_enrichment = ContextEnrichmentService(db)
        self.feature_extraction = FeatureExtractionService(db)
        self.stats = PhenomenologyStatsService(db)
        self.phone_registry = PhoneRegistryService(db)
        self.nft_builder = NFTPayloadBuilder(db)
        
        self.default_hmm_model_id = default_hmm_model_id
    
    def capture(
        self,
        party_id: UUID,
        case_id: UUID,
        raw_text: str,
        pain_value: Optional[float] = None,
        pain_location: Optional[str] = None,
        pain_quality: Optional[str] = None,
        functional_impact: Optional[dict] = None,
        event_time: Optional[datetime] = None,
        location_type: Optional[str] = None,
        posture: Optional[str] = None,
        exertion_level: Optional[str] = None,
        environment_tags: Optional[List[str]] = None,
        activity_description: Optional[str] = None,
        source: str = "api",
        fact_id: Optional[UUID] = None,
        run_hmm_inference: bool = True
    ) -> IntegratedCaptureResult:
        """
        Capture a phenomenological observation through the full integrated pipeline.
        
        This is THE method to use for recording any phenomenological data.
        """
        recorded_at = datetime.now(timezone.utc)
        
        # ================================================================
        # 1. GET/CREATE PERSONA
        # ================================================================
        persona_token = get_or_create_persona_for_party(self.db, party_id)
        
        # ================================================================
        # 2. ENCRYPT RAW TEXT → SUBJECTIVE NOTE
        # ================================================================
        encryption_key = self._get_or_create_encryption_key(persona_token.id)
        ciphertext, plaintext_hash = self.encryption.encrypt_note(raw_text)
        
        normalized = self.normalization.normalize(raw_text)
        
        subjective_note = SubjectiveNote(
            persona_token_id=persona_token.id,
            ciphertext=ciphertext,
            encryption_key_id=encryption_key.id,
            plaintext_hash=plaintext_hash,
            note_type=normalized["note_type"],
            normalized_summary=normalized["normalized_summary"],
            symptom_tags=normalized["symptom_tags"],
            severity_level=normalized["severity_level"] or (int(pain_value) if pain_value else None),
            event_time=event_time,
            recorded_at=recorded_at
        )
        self.db.add(subjective_note)
        self.db.flush()
        
        # ================================================================
        # 3. CREATE PAIN STATE (if pain data provided)
        # ================================================================
        pain_state = None
        if pain_value is not None:
            pain_state = PainState(
                party_id=party_id,
                fact_id=fact_id,
                value=pain_value,
                location=pain_location,
                quality=pain_quality,
                functional_impact=functional_impact,
                source=source,
                recorded_at=recorded_at
            )
            self.db.add(pain_state)
            self.db.flush()
        
        # ================================================================
        # 4. BUILD CANONICAL PAYLOAD (PHI-LIGHT)
        # ================================================================
        payload = build_subjective_note_payload(subjective_note)
        
        if pain_state:
            payload["pain_state"] = {
                "id": str(pain_state.id),
                "value": pain_state.value,
                "location": pain_state.location,
                "quality": pain_state.quality
            }
        
        canonical_json = to_canonical_json(payload)
        payload_hash = compute_payload_hash(payload)
        
        # ================================================================
        # 5. EXTEND CHAIN WITH SIGNATURE
        # ================================================================
        latest_entry = self.attestation.get_latest_entry_locked(persona_token.id)
        prev_hash = latest_entry.entry_hash if latest_entry else None
        sequence_number = (latest_entry.sequence_number + 1) if latest_entry else 1
        
        entry_hash = AttestedEntry.compute_entry_hash(
            prev_hash=prev_hash,
            payload_hash=payload_hash,
            persona_token_id=persona_token.id,
            sequence_number=sequence_number,
            created_at=recorded_at
        )
        
        signature, signer_key_id = self.signing.sign_entry(
            persona_token_id=persona_token.id,
            sequence_number=sequence_number,
            previous_hash=prev_hash,
            payload_hash=payload_hash,
            timestamp=recorded_at
        )
        
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
            created_at=recorded_at
        )
        self.db.add(entry)
        self.db.flush()
        
        # ================================================================
        # 6. ENRICH WITH CONTEXT
        # ================================================================
        context = self.context_enrichment.enrich_entry(
            entry=entry,
            case_id=case_id,
            event_time=event_time,
            location_type=location_type,
            posture=posture,
            exertion_level=exertion_level,
            environment_tags=environment_tags,
            activity_description=activity_description,
            raw_context={
                "source": source,
                "fact_id": str(fact_id) if fact_id else None
            }
        )
        self.db.flush()
        
        # ================================================================
        # 7. EXTRACT FEATURES AND RUN HMM INFERENCE
        # ================================================================
        feature_vector = None
        inferred_state = None
        state_confidence = None
        is_anomaly = False
        
        if run_hmm_inference and self.default_hmm_model_id:
            # Extract features
            feature_vector = self.feature_extraction.extract_for_entry(
                entry=entry,
                context=context,
                pain_state=pain_state,
                sequence_index=sequence_number - 1
            )
            self.db.add(feature_vector)
            self.db.flush()
            
            # Run inference
            model = self.db.query(HiddenStateModel).filter(
                HiddenStateModel.id == self.default_hmm_model_id
            ).first()
            
            if model:
                engine = HMMInferenceEngine(model)
                
                # Get recent feature vectors for context
                recent_vectors = self.db.query(FeatureVector).filter(
                    FeatureVector.persona_token_id == persona_token.id
                ).order_by(FeatureVector.sequence_index.desc()).limit(10).all()
                
                recent_vectors = list(reversed(recent_vectors))
                
                if recent_vectors:
                    inferences = engine.infer_sequence(recent_vectors)
                    
                    if inferences:
                        latest_inference = inferences[-1]
                        inferred_state = latest_inference["most_likely_state"]
                        state_confidence = latest_inference["confidence"]
                        is_anomaly = latest_inference["is_anomaly"]
                        
                        # Save inference
                        state_inf = StateInference(
                            attested_entry_id=entry.id,
                            feature_vector_id=feature_vector.id,
                            model_id=model.id,
                            most_likely_state=inferred_state,
                            most_likely_state_index=latest_inference["most_likely_state_index"],
                            state_probabilities=latest_inference["state_probabilities"],
                            confidence=state_confidence,
                            emission_likelihood=latest_inference["emission_likelihood"],
                            log_likelihood=latest_inference["log_likelihood"],
                            is_anomaly=is_anomaly,
                            anomaly_score=latest_inference["anomaly_score"],
                            sequence_index=latest_inference["sequence_index"]
                        )
                        self.db.add(state_inf)
        
        # ================================================================
        # 8. VERIFY CHAIN
        # ================================================================
        chain_verified, _, _ = self.attestation.verify_chain(
            persona_token_id=persona_token.id,
            from_sequence=max(1, sequence_number - 5),
            to_sequence=sequence_number
        )
        
        # ================================================================
        # 9. COMMIT AND RETURN
        # ================================================================
        self.db.commit()
        
        return IntegratedCaptureResult(
            subjective_note_id=subjective_note.id,
            pain_state_id=pain_state.id if pain_state else None,
            attested_entry_id=entry.id,
            context_snapshot_id=context.id,
            case_phase=context.case_phase,
            days_since_injury=context.days_since_injury,
            sequence_number=sequence_number,
            entry_hash=entry_hash,
            payload_hash=payload_hash,
            signature=signature,
            signer_key_id=signer_key_id,
            feature_vector_id=feature_vector.id if feature_vector else None,
            inferred_state=inferred_state,
            state_confidence=state_confidence,
            is_anomaly=is_anomaly,
            chain_verified=chain_verified
        )
    
    def _get_or_create_encryption_key(self, persona_token_id: UUID) -> EncryptionKey:
        """Get or create an encryption key for the persona."""
        existing = self.db.query(EncryptionKey).filter(
            EncryptionKey.persona_token_id == persona_token_id,
            EncryptionKey.is_active == True
        ).first()
        
        if existing:
            return existing
        
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
    
    def capture_from_sms(
        self,
        phone_number: str,
        raw_text: str,
        received_at: datetime,
        parsed_pain_value: Optional[float] = None,
        parsed_location: Optional[str] = None,
        parsed_quality: Optional[str] = None
    ) -> Optional[IntegratedCaptureResult]:
        """
        Capture from an SMS message.
        
        Looks up the phone number to find the associated case context,
        then routes through the main capture pipeline.
        """
        # Look up phone registration
        context = self.phone_registry.get_context(phone_number)
        
        if not context:
            return None
        
        # Update last message timestamp
        self.phone_registry.update_last_message(phone_number)
        
        # Route to main capture
        return self.capture(
            party_id=context["party_id"],
            case_id=context["case_id"],
            raw_text=f"[SMS {received_at.isoformat()}] {raw_text}",
            pain_value=parsed_pain_value,
            pain_location=parsed_location,
            pain_quality=parsed_quality,
            event_time=received_at,
            source="sms"
        )
    
    def generate_export(
        self,
        persona_token_id: UUID,
        case_id: UUID,
        export_purpose: str = "client_handoff",
        include_trajectory: bool = True
    ) -> NFTPayload:
        """
        Generate a complete export package (NFT payload).
        
        This creates the portable proof that can be handed to the client.
        """
        model_id = self.default_hmm_model_id if include_trajectory else None
        
        return self.nft_builder.build_payload(
            persona_token_id=persona_token_id,
            case_id=case_id,
            model_id=model_id,
            export_purpose=export_purpose
        )
    
    def setup_case(
        self,
        legal_name: str,
        case_id: UUID,
        phone_number: Optional[str] = None,
        injury_date: Optional[datetime] = None
    ) -> Tuple[Party, PersonaToken, Optional[PhoneRegistry], Optional[CaseTimeline]]:
        """
        Set up a new case with all necessary infrastructure.
        
        Creates:
        - Party record
        - PersonaToken
        - Phone registration (if phone provided)
        - Case timeline (if injury date provided)
        - Default HMM model association
        """
        # Create party
        party = Party(
            legal_name=legal_name,
            role=PartyRole.PLAINTIFF,
            case_id=case_id
        )
        self.db.add(party)
        self.db.flush()
        
        # Create persona token
        persona_token = PersonaToken(party_id=party.id)
        self.db.add(persona_token)
        self.db.flush()
        
        # Register phone if provided
        phone_reg = None
        if phone_number:
            phone_reg = self.phone_registry.register(
                phone=phone_number,
                party_id=party.id,
                persona_token_id=persona_token.id,
                case_id=case_id
            )
        
        # Create timeline if injury date provided
        timeline = None
        if injury_date:
            timeline = CaseTimeline(
                case_id=case_id,
                injury_date=injury_date
            )
            self.db.add(timeline)
        
        self.db.commit()
        
        return party, persona_token, phone_reg, timeline
    
    def ensure_default_model(self) -> HiddenStateModel:
        """
        Ensure a default HMM model exists and return it.
        
        Creates the default pain trajectory model if none exists.
        """
        if self.default_hmm_model_id:
            model = self.db.query(HiddenStateModel).filter(
                HiddenStateModel.id == self.default_hmm_model_id
            ).first()
            if model:
                return model
        
        # Check for any active model
        existing = self.db.query(HiddenStateModel).filter(
            HiddenStateModel.is_active == True,
            HiddenStateModel.model_type == "pain_trajectory"
        ).first()
        
        if existing:
            self.default_hmm_model_id = existing.id
            return existing
        
        # Create default model
        model = create_default_pain_trajectory_model()
        self.db.add(model)
        self.db.commit()
        
        self.default_hmm_model_id = model.id
        return model


# ============================================================================
# FACTORY FUNCTION
# ============================================================================

def create_integrated_service(db: Session) -> IntegratedPhenomenologyService:
    """
    Factory function to create a properly configured IntegratedPhenomenologyService.
    
    This is the recommended way to instantiate the service.
    """
    service = IntegratedPhenomenologyService(db)
    
    # Ensure default model exists
    model = service.ensure_default_model()
    
    return service
