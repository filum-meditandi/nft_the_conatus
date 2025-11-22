"""
Phenomenological Evidence Models

This module implements the "perspective-authentic, evidence-anchored" architecture
for plaintiff-centered case documentation. It treats lived experience as first-class
structured data while cryptographically chaining every assertion to evidence.

Core principle: We don't claim metaphysical truth. We guarantee:
- WHO made or approved the statement (persona/key)
- WHEN it was recorded (timestamp)  
- EXACTLY what they said (payload hash)
- HOW it connects to evidence, duties, and harm
"""

import hashlib
import json
from datetime import datetime
from enum import Enum
from typing import Optional, List
from uuid import UUID, uuid4

from sqlalchemy import (
    Column, String, Text, Boolean, Integer, Float, 
    DateTime, ForeignKey, Enum as SQLEnum, JSON
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


# ============================================================================
# ENUMS
# ============================================================================

class PartyRole(str, Enum):
    PLAINTIFF = "plaintiff"
    DEFENDANT = "defendant"
    WITNESS = "witness"
    PROVIDER = "provider"  # medical provider
    INSURER = "insurer"
    EXPERT = "expert"


class FactCategory(str, Enum):
    ACCIDENT = "accident"
    SYMPTOM = "symptom"
    TREATMENT = "treatment"
    DIAGNOSIS = "diagnosis"
    WORK_IMPACT = "work_impact"
    DAILY_LIVING = "daily_living"
    EMOTIONAL = "emotional"
    FINANCIAL = "financial"


class EvidenceSourceType(str, Enum):
    MEDICAL_RECORD = "medical_record"
    PHOTO = "photo"
    VIDEO = "video"
    LAB_RESULT = "lab_result"
    POLICE_REPORT = "police_report"
    INSURANCE_DOC = "insurance_doc"
    BILLING = "billing"
    SENSOR_LOG = "sensor_log"  # glucose meter, fitness tracker, etc.
    SMS_LOG = "sms_log"
    DEPOSITION = "deposition"
    CORRESPONDENCE = "correspondence"


class LinkRole(str, Enum):
    SUPPORTS = "supports"
    REFUTES = "refutes"
    CONTEXT = "context"
    QUANTIFIES = "quantifies"


class Valence(str, Enum):
    PAIN = "pain"
    FEAR = "fear"
    GRIEF = "grief"
    ANGER = "anger"
    HOPE = "hope"
    RELIEF = "relief"
    NEUTRAL = "neutral"


class CausationTheory(str, Enum):
    BUT_FOR = "but_for"
    SUBSTANTIAL_FACTOR = "substantial_factor"
    PROXIMATE = "proximate"
    FORESEEABILITY = "foreseeability"


# ============================================================================
# PARTY & PERSONA
# ============================================================================

class Party(Base):
    """
    Any actor in the case: plaintiff, defendant, provider, insurer, etc.
    Links to Observer when it's "our" client in the intentionality ledger.
    """
    __tablename__ = "parties"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    legal_name = Column(String(255), nullable=False)
    role = Column(SQLEnum(PartyRole), nullable=False)
    
    # Link to intentionality ledger (when this party is our client)
    observer_id = Column(PGUUID(as_uuid=True), nullable=True)
    
    # Case association
    case_id = Column(PGUUID(as_uuid=True), ForeignKey("cases.id"), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    persona_token = relationship("PersonaToken", back_populates="party", uselist=False)
    facts = relationship("Fact", back_populates="party")
    perspective_notes = relationship("PerspectiveNote", back_populates="party")
    pain_states = relationship("PainState", back_populates="party")


class PersonaToken(Base):
    """
    The NFT that personifies one party's lived perspective.
    This is the cryptographic anchor for the plaintiff's existential record.
    """
    __tablename__ = "persona_tokens"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    party_id = Column(PGUUID(as_uuid=True), ForeignKey("parties.id"), nullable=False)
    
    # On-chain identity
    nft_id = Column(String(255), nullable=True)  # Chain-specific token ID
    contract_address = Column(String(255), nullable=True)
    chain_id = Column(Integer, nullable=True)
    
    # Metadata
    metadata_uri = Column(String(512), nullable=True)  # IPFS or similar
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    party = relationship("Party", back_populates="persona_token")
    attested_entries = relationship("AttestedEntry", back_populates="persona_token")


# ============================================================================
# FACTS & EVIDENCE
# ============================================================================

class Fact(Base):
    """
    A structured proposition about the world.
    
    Examples:
    - "On 2024-03-16 at 14:20, plaintiff was rear-ended at 30 mph."
    - "Plaintiff experienced onset of headaches within 1 hour of impact."
    - "MRI on 2024-03-20 showed disc herniation at C5-6."
    """
    __tablename__ = "facts"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Whose story this fact belongs to (or null if neutral/stipulated)
    party_id = Column(PGUUID(as_uuid=True), ForeignKey("parties.id"), nullable=True)
    
    # Case association
    case_id = Column(PGUUID(as_uuid=True), ForeignKey("cases.id"), nullable=True)
    
    # Temporal anchor
    occurred_at = Column(DateTime(timezone=True), nullable=True)
    
    # Classification
    category = Column(SQLEnum(FactCategory), nullable=False)
    
    # The canonical statement
    statement = Column(Text, nullable=False)
    
    # Objective (from documents) vs subjective (from narrative)
    is_objective = Column(Boolean, default=True)
    
    # Attribution
    created_by_party_id = Column(PGUUID(as_uuid=True), ForeignKey("parties.id"), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    party = relationship("Party", back_populates="facts", foreign_keys=[party_id])
    evidence_links = relationship("FactEvidenceLink", back_populates="fact")
    perspective_notes = relationship("PerspectiveNote", back_populates="fact")
    pain_states = relationship("PainState", back_populates="fact")
    causal_links = relationship("CausalLink", back_populates="harm_fact")


class EvidenceItem(Base):
    """
    A specific evidentiary artifact: PDF, photo, sensor log, etc.
    """
    __tablename__ = "evidence_items"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Case association
    case_id = Column(PGUUID(as_uuid=True), ForeignKey("cases.id"), nullable=True)
    
    # Classification
    source_type = Column(SQLEnum(EvidenceSourceType), nullable=False)
    
    # Storage
    uri = Column(String(1024), nullable=False)  # S3, IPFS, local path
    
    # Integrity
    content_hash = Column(String(128), nullable=False)  # SHA-256 or similar
    hash_algorithm = Column(String(32), default="sha256")
    
    # Metadata
    description = Column(Text, nullable=True)
    original_filename = Column(String(255), nullable=True)
    mime_type = Column(String(128), nullable=True)
    file_size_bytes = Column(Integer, nullable=True)
    
    # Temporal
    document_date = Column(DateTime(timezone=True), nullable=True)  # Date of the document itself
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    fact_links = relationship("FactEvidenceLink", back_populates="evidence")


class FactEvidenceLink(Base):
    """
    Relationship between a Fact and an EvidenceItem.
    This is your evidentiary graph - every node hashed, every edge auditable.
    """
    __tablename__ = "fact_evidence_links"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    fact_id = Column(PGUUID(as_uuid=True), ForeignKey("facts.id"), nullable=False)
    evidence_id = Column(PGUUID(as_uuid=True), ForeignKey("evidence_items.id"), nullable=False)
    
    # Nature of the relationship
    role = Column(SQLEnum(LinkRole), nullable=False, default=LinkRole.SUPPORTS)
    
    # Confidence rating (attorney or algorithmic assessment)
    confidence = Column(Float, nullable=True)  # 0.0 - 1.0
    
    # Attribution
    assessed_by = Column(String(255), nullable=True)  # Who made this link
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    fact = relationship("Fact", back_populates="evidence_links")
    evidence = relationship("EvidenceItem", back_populates="fact_links")


# ============================================================================
# PERSPECTIVE: PAIN, SUFFERING, PURPOSE
# ============================================================================

class PerspectiveNote(Base):
    """
    Narrative perspective: meaning, purpose, emotional weight.
    
    This is where the plaintiff's voice lives - their experience of facts,
    not just the facts themselves.
    """
    __tablename__ = "perspective_notes"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Whose perspective
    party_id = Column(PGUUID(as_uuid=True), ForeignKey("parties.id"), nullable=False)
    
    # What it's about
    fact_id = Column(PGUUID(as_uuid=True), ForeignKey("facts.id"), nullable=True)
    
    # Link to intentionality ledger (which lived moment this came from)
    attention_event_id = Column(PGUUID(as_uuid=True), nullable=True)
    
    # Content
    title = Column(String(255), nullable=True)
    body = Column(Text, nullable=False)
    
    # Emotional classification
    valence = Column(SQLEnum(Valence), nullable=True)
    
    # Semantic tags for meaning/purpose analysis
    meaning_tags = Column(JSON, nullable=True)  # ['loss_of_identity', 'financial_stress']
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    party = relationship("Party", back_populates="perspective_notes")
    fact = relationship("Fact", back_populates="perspective_notes")

    def to_canonical_json(self) -> str:
        """
        Generate deterministic JSON for hashing.
        
        Uses the formal canonical JSON specification from canonical_json.py.
        See that module for the exact rules that ensure reproducibility.
        """
        from canonical_json import build_perspective_note_payload, to_canonical_json
        
        payload = build_perspective_note_payload(
            id=self.id,
            party_id=self.party_id,
            fact_id=self.fact_id,
            attention_event_id=self.attention_event_id,
            title=self.title,
            body=self.body,
            valence=self.valence.value if self.valence else None,
            meaning_tags=self.meaning_tags,
            created_at=self.created_at
        )
        return to_canonical_json(payload)


class PainState(Base):
    """
    Structured intensity measurement: pain, symptoms, functional impact.
    
    When your client texts "Pain 7/10, can't sleep, neck burning" - 
    this is where that structured data lives.
    """
    __tablename__ = "pain_states"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Whose pain
    party_id = Column(PGUUID(as_uuid=True), ForeignKey("parties.id"), nullable=False)
    
    # What it's related to
    fact_id = Column(PGUUID(as_uuid=True), ForeignKey("facts.id"), nullable=True)
    
    # Link to intentionality ledger
    attention_event_id = Column(PGUUID(as_uuid=True), nullable=True)
    
    # When recorded
    recorded_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    
    # Pain scale
    scale_type = Column(String(32), default="0-10")  # '0-10', 'VAS', 'Wong-Baker'
    value = Column(Float, nullable=False)  # 0-10 or similar
    
    # Location and quality
    location = Column(String(128), nullable=True)  # 'neck', 'low back', 'headache'
    quality = Column(String(128), nullable=True)  # 'sharp', 'dull', 'throbbing', 'burning'
    
    # Functional impact (structured)
    functional_impact = Column(JSON, nullable=True)  # {"sleep": 3, "work": 5, "adls": 4}
    
    # Source of this reading
    source = Column(String(64), nullable=True)  # 'sms', 'app', 'intake', 'deposition'
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    party = relationship("Party", back_populates="pain_states")
    fact = relationship("Fact", back_populates="pain_states")

    def to_canonical_json(self) -> str:
        """
        Generate deterministic JSON for hashing.
        
        Uses the formal canonical JSON specification from canonical_json.py.
        See that module for the exact rules that ensure reproducibility.
        """
        from canonical_json import build_pain_state_payload, to_canonical_json
        
        payload = build_pain_state_payload(
            id=self.id,
            party_id=self.party_id,
            fact_id=self.fact_id,
            attention_event_id=self.attention_event_id,
            recorded_at=self.recorded_at,
            scale_type=self.scale_type,
            value=self.value,
            location=self.location,
            quality=self.quality,
            functional_impact=self.functional_impact,
            source=self.source
        )
        return to_canonical_json(payload)


# ============================================================================
# LEGAL STRUCTURE: DUTY, BREACH, CAUSATION
# ============================================================================

class Duty(Base):
    """
    The legal obligation owed by a party.
    
    Examples:
    - "Exercise reasonable care while operating a motor vehicle"
    - "Maintain premises in a reasonably safe condition"
    - "Obtain informed consent before medical procedures"
    """
    __tablename__ = "duties"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Who owes the duty (usually defendant)
    party_id = Column(PGUUID(as_uuid=True), ForeignKey("parties.id"), nullable=False)
    
    # Case association
    case_id = Column(PGUUID(as_uuid=True), ForeignKey("cases.id"), nullable=True)
    
    # The duty itself
    description = Column(Text, nullable=False)
    
    # Legal basis
    legal_basis = Column(Text, nullable=True)  # Statute, case law, etc.
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    breaches = relationship("Breach", back_populates="duty")


class Breach(Base):
    """
    How the defendant failed their duty.
    Links to the factual manifestation of that failure.
    """
    __tablename__ = "breaches"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    duty_id = Column(PGUUID(as_uuid=True), ForeignKey("duties.id"), nullable=False)
    
    # The fact that manifests this breach
    fact_id = Column(PGUUID(as_uuid=True), ForeignKey("facts.id"), nullable=True)
    
    # Description
    description = Column(Text, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    duty = relationship("Duty", back_populates="breaches")
    causal_links = relationship("CausalLink", back_populates="breach")


class CausalLink(Base):
    """
    The edge from Breach to harm Facts.
    
    This makes the causal chain explicit:
    duty → breach → harm facts → perspectives/pain
    """
    __tablename__ = "causal_links"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    
    breach_id = Column(PGUUID(as_uuid=True), ForeignKey("breaches.id"), nullable=False)
    
    # The fact representing harm/damages
    harm_fact_id = Column(PGUUID(as_uuid=True), ForeignKey("facts.id"), nullable=False)
    
    # Causation theory
    theory = Column(SQLEnum(CausationTheory), nullable=False, default=CausationTheory.BUT_FOR)
    
    # Strength of the causal claim
    strength = Column(Float, nullable=True)  # 0.0 - 1.0
    
    # Notes on causation analysis
    notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    breach = relationship("Breach", back_populates="causal_links")
    harm_fact = relationship("Fact", back_populates="causal_links")


# ============================================================================
# CRYPTOGRAPHIC ATTESTATION LEDGER
# ============================================================================

class AttestedEntry(Base):
    """
    The cryptographic ledger that makes the existential record tamper-evident.
    
    Every important write passes through here. For each persona (plaintiff's NFT),
    these entries form a hash chain:
    
        entry_1 → entry_2 → entry_3 → ...
    
    Changing any underlying narrative or metric breaks the chain.
    You can periodically anchor entry_hash values on-chain as checkpoints.
    
    This guarantees:
    - WHO made the statement (persona_token_id)
    - WHEN it was recorded (created_at)  
    - EXACTLY what was stored (payload_hash)
    - CHAIN INTEGRITY (prev_hash → entry_hash)
    """
    __tablename__ = "attested_entries"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Which persona this belongs to
    persona_token_id = Column(PGUUID(as_uuid=True), ForeignKey("persona_tokens.id"), nullable=False)
    
    # What domain object this attests
    domain_table = Column(String(64), nullable=False)  # 'PerspectiveNote', 'PainState', 'Fact'
    domain_id = Column(PGUUID(as_uuid=True), nullable=False)
    
    # Hash of the canonical JSON representation of the domain object
    payload_hash = Column(String(128), nullable=False)
    
    # Chain integrity
    prev_hash = Column(String(128), nullable=True)  # Null for first entry
    entry_hash = Column(String(128), nullable=False)  # hash(prev_hash + payload_hash + metadata)
    
    # Sequence number for this persona's chain
    sequence_number = Column(Integer, nullable=False)
    
    # Optional signature
    signature = Column(Text, nullable=True)  # Digital signature of client/attorney key
    signer_key_id = Column(String(255), nullable=True)  # Which key signed
    
    # On-chain anchor (if checkpointed)
    chain_anchor_tx = Column(String(255), nullable=True)  # Transaction hash
    chain_anchor_block = Column(Integer, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    persona_token = relationship("PersonaToken", back_populates="attested_entries")

    @staticmethod
    def compute_payload_hash(canonical_json: str) -> str:
        """Compute SHA-256 hash of canonical JSON."""
        return hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()

    @staticmethod
    def compute_entry_hash(
        prev_hash: Optional[str],
        payload_hash: str,
        persona_token_id: UUID,
        sequence_number: int,
        created_at: datetime
    ) -> str:
        """
        Compute the chain entry hash.
        
        entry_hash = SHA256(prev_hash || payload_hash || persona_token_id || sequence || timestamp)
        """
        components = [
            prev_hash or "GENESIS",
            payload_hash,
            str(persona_token_id),
            str(sequence_number),
            created_at.isoformat()
        ]
        combined = "|".join(components)
        return hashlib.sha256(combined.encode('utf-8')).hexdigest()

    def verify_chain_integrity(self, prev_entry: Optional['AttestedEntry']) -> bool:
        """
        Verify this entry's hash is valid given the previous entry.
        """
        expected_prev_hash = prev_entry.entry_hash if prev_entry else None
        
        if self.prev_hash != expected_prev_hash:
            return False
        
        expected_entry_hash = self.compute_entry_hash(
            self.prev_hash,
            self.payload_hash,
            self.persona_token_id,
            self.sequence_number,
            self.created_at
        )
        
        return self.entry_hash == expected_entry_hash
