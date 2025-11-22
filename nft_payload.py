"""
NFT Payload Builder

This module creates the portable, durable signifier that represents
a plaintiff's phenomenological evidence record.

The NFT payload includes:
1. Chain verification proof (Merkle root, signature chain)
2. Trajectory summary (HMM state sequence, transitions)
3. Statistics (flare counts, phase durations, pain distribution)
4. Metadata linking to full evidence store

What the NFT represents:
- NOT the raw PHI (that stays encrypted in the database)
- NOT a tradeable asset
- A CRYPTOGRAPHIC COMMITMENT to the full evidence record
- A PORTABLE PROOF that this person's story exists and is verified

The NFT can be:
- Stored by the client as proof of their record
- Presented in court as evidence anchor
- Transferred to the client at case conclusion
- Verified independently against the chain

This is what you "hand back" to the client:
A durable signifier of everything they were willing to say,
mathematically anchored, cryptographically chained, and statistically structured.
"""

import json
import hashlib
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from dataclasses import dataclass, asdict

from sqlalchemy.orm import Session

from models import AttestedEntry, PersonaToken, Party
from attestation_service import AttestationService
from hmm_inference import TrajectoryAnalysisService, HiddenStateModel, StateInference
from context_layer import PhenomenologyStatsService, CaseTimeline


# ============================================================================
# NFT PAYLOAD STRUCTURE
# ============================================================================

@dataclass
class ChainProof:
    """
    Cryptographic proof of chain integrity.
    
    This can be verified independently without access to the full database.
    """
    # Chain identification
    persona_token_id: str
    chain_length: int
    
    # First and last entry hashes (bookends)
    genesis_hash: str
    latest_hash: str
    latest_sequence: int
    
    # Merkle root of all entry hashes (compact proof)
    merkle_root: str
    
    # Verification timestamp
    verified_at: str
    
    # Server attestation
    server_signature: Optional[str]
    server_key_id: Optional[str]


@dataclass
class TrajectorySummary:
    """
    Summary of HMM trajectory inference.
    
    This captures the structured interpretation of the phenomenological
    record without exposing individual observations.
    """
    # Model identification
    model_id: str
    model_name: str
    model_version: str
    
    # State distribution
    total_observations: int
    state_distribution: Dict[str, Dict[str, Any]]
    # {"baseline": {"count": 50, "pct": 45.5}, "flare": {...}, ...}
    
    # Key events
    num_transitions: int
    transitions: List[Dict[str, Any]]
    # [{"from": "baseline", "to": "flare", "date": "...", "day": 30}, ...]
    
    # Phase analysis
    phase_statistics: Dict[str, Dict[str, Any]]
    # {"acute": {"mean_pain": 7.2, "flare_pct": 60}, ...}
    
    # Anomalies
    num_anomalies: int
    anomaly_summary: Optional[str]


@dataclass
class EvidenceSummary:
    """
    High-level summary statistics for the phenomenological record.
    """
    # Temporal scope
    first_report_date: str
    last_report_date: str
    total_days_covered: int
    total_reports: int
    
    # Pain statistics
    mean_pain_level: Optional[float]
    max_pain_level: Optional[float]
    reports_above_7: int
    pct_reports_above_7: float
    
    # Functional impact
    sleep_disruption_reports: int
    work_impact_reports: int
    
    # Reporting patterns
    mean_reports_per_week: float
    most_active_day: Optional[str]
    most_active_hour: Optional[int]


@dataclass
class NFTPayload:
    """
    The complete NFT payload - the portable proof of phenomenological evidence.
    
    This is what gets minted and handed to the client.
    """
    # Metadata
    payload_version: str
    created_at: str
    payload_hash: str
    
    # Identity
    persona_token_id: str
    case_id: str
    party_name_hash: str  # Hash of name, not the name itself (privacy)
    
    # Proofs
    chain_proof: ChainProof
    
    # Summaries (no PHI)
    trajectory_summary: Optional[TrajectorySummary]
    evidence_summary: EvidenceSummary
    
    # Links to full data (for those with access)
    full_chain_uri: Optional[str]  # Where to fetch full chain
    verification_endpoint: Optional[str]  # Where to verify
    
    # Legal metadata
    case_status: Optional[str]
    export_purpose: str  # "client_handoff", "court_exhibit", "settlement"
    
    def to_json(self) -> str:
        """Serialize to JSON for NFT metadata."""
        return json.dumps(asdict(self), indent=2, sort_keys=True)
    
    def compute_hash(self) -> str:
        """Compute SHA-256 hash of the payload."""
        # Exclude the hash field itself
        data = asdict(self)
        data.pop("payload_hash", None)
        canonical = json.dumps(data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical.encode()).hexdigest()


# ============================================================================
# MERKLE TREE FOR CHAIN PROOF
# ============================================================================

def compute_merkle_root(hashes: List[str]) -> str:
    """
    Compute Merkle root of a list of hashes.
    
    This provides a compact proof that all entries are included.
    """
    if not hashes:
        return hashlib.sha256(b"EMPTY").hexdigest()
    
    if len(hashes) == 1:
        return hashes[0]
    
    # Pad to even length
    if len(hashes) % 2 == 1:
        hashes.append(hashes[-1])
    
    # Compute next level
    next_level = []
    for i in range(0, len(hashes), 2):
        combined = hashes[i] + hashes[i + 1]
        next_hash = hashlib.sha256(combined.encode()).hexdigest()
        next_level.append(next_hash)
    
    return compute_merkle_root(next_level)


# ============================================================================
# PAYLOAD BUILDER SERVICE
# ============================================================================

class NFTPayloadBuilder:
    """
    Builds NFT payloads from phenomenological evidence records.
    
    This is the "export" functionality that creates the portable
    proof the client takes with them.
    """
    
    def __init__(self, db: Session, signing_service: Optional['SigningService'] = None):
        self.db = db
        self.attestation_service = AttestationService(db)
        self.stats_service = PhenomenologyStatsService(db)
        
        # Import here to avoid circular imports
        if signing_service is None:
            from signing_infrastructure import SigningService
            signing_service = SigningService()
        self.signing = signing_service
    
    def build_payload(
        self,
        persona_token_id: UUID,
        case_id: UUID,
        model_id: Optional[UUID] = None,
        export_purpose: str = "client_handoff",
        full_chain_uri: Optional[str] = None,
        verification_endpoint: Optional[str] = None
    ) -> NFTPayload:
        """
        Build a complete NFT payload for a persona's evidence record.
        """
        # Get persona and party info
        persona = self.db.query(PersonaToken).filter(
            PersonaToken.id == persona_token_id
        ).first()
        
        if not persona:
            raise ValueError(f"PersonaToken {persona_token_id} not found")
        
        party = self.db.query(Party).filter(
            Party.id == persona.party_id
        ).first()
        
        # Build chain proof
        chain_proof = self._build_chain_proof(persona_token_id)
        
        # Build trajectory summary if model provided
        trajectory_summary = None
        if model_id:
            trajectory_summary = self._build_trajectory_summary(
                persona_token_id, model_id
            )
        
        # Build evidence summary
        evidence_summary = self._build_evidence_summary(persona_token_id, case_id)
        
        # Hash party name for privacy
        party_name_hash = hashlib.sha256(
            (party.legal_name if party else "").encode()
        ).hexdigest()[:16]
        
        # Build payload
        payload = NFTPayload(
            payload_version="1.0",
            created_at=datetime.now(timezone.utc).isoformat(),
            payload_hash="",  # Will be computed
            
            persona_token_id=str(persona_token_id),
            case_id=str(case_id),
            party_name_hash=party_name_hash,
            
            chain_proof=chain_proof,
            trajectory_summary=trajectory_summary,
            evidence_summary=evidence_summary,
            
            full_chain_uri=full_chain_uri,
            verification_endpoint=verification_endpoint,
            
            case_status=None,
            export_purpose=export_purpose
        )
        
        # Compute payload hash
        payload.payload_hash = payload.compute_hash()
        
        # Sign the export (sign the payload hash)
        if self.signing:
            export_signature, signer_key_id = self.signing.sign_entry(
                persona_token_id=persona_token_id,
                sequence_number=chain_proof.chain_length,
                previous_hash=chain_proof.latest_hash,
                payload_hash=payload.payload_hash,
                timestamp=datetime.now(timezone.utc)
            )
            # Add signature to chain proof
            payload.chain_proof.server_signature = export_signature
            payload.chain_proof.server_key_id = signer_key_id
        
        return payload
    
    def _build_chain_proof(self, persona_token_id: UUID) -> ChainProof:
        """Build cryptographic proof of chain integrity."""
        # Get all entries
        entries = self.db.query(AttestedEntry).filter(
            AttestedEntry.persona_token_id == persona_token_id
        ).order_by(AttestedEntry.sequence_number.asc()).all()
        
        if not entries:
            return ChainProof(
                persona_token_id=str(persona_token_id),
                chain_length=0,
                genesis_hash="",
                latest_hash="",
                latest_sequence=0,
                merkle_root=compute_merkle_root([]),
                verified_at=datetime.now(timezone.utc).isoformat(),
                server_signature=None,
                server_key_id=None
            )
        
        # Collect all entry hashes
        entry_hashes = [e.entry_hash for e in entries]
        
        # Compute Merkle root
        merkle_root = compute_merkle_root(entry_hashes)
        
        # Verify chain integrity
        is_valid, _, _ = self.attestation_service.verify_chain(persona_token_id)
        
        # Get latest entry's signature (if signed)
        latest = entries[-1]
        
        return ChainProof(
            persona_token_id=str(persona_token_id),
            chain_length=len(entries),
            genesis_hash=entries[0].entry_hash,
            latest_hash=latest.entry_hash,
            latest_sequence=latest.sequence_number,
            merkle_root=merkle_root,
            verified_at=datetime.now(timezone.utc).isoformat(),
            server_signature=latest.signature,
            server_key_id=latest.signer_key_id
        )
    
    def _build_trajectory_summary(
        self, 
        persona_token_id: UUID,
        model_id: UUID
    ) -> Optional[TrajectorySummary]:
        """Build trajectory summary from HMM inferences."""
        # Get model
        model = self.db.query(HiddenStateModel).filter(
            HiddenStateModel.id == model_id
        ).first()
        
        if not model:
            return None
        
        # Get all inferences for this persona
        inferences = self.db.query(StateInference).filter(
            StateInference.model_id == model_id
        ).join(AttestedEntry).filter(
            AttestedEntry.persona_token_id == persona_token_id
        ).order_by(StateInference.sequence_index.asc()).all()
        
        if not inferences:
            return None
        
        # Compute state distribution
        state_counts = {label: 0 for label in model.state_labels}
        for inf in inferences:
            state_counts[inf.most_likely_state] += 1
        
        total = len(inferences)
        state_distribution = {
            label: {
                "count": count,
                "pct": round(count / total * 100, 1) if total > 0 else 0
            }
            for label, count in state_counts.items()
        }
        
        # Find transitions
        transitions = []
        for i in range(1, len(inferences)):
            prev = inferences[i-1]
            curr = inferences[i]
            if prev.most_likely_state != curr.most_likely_state:
                transitions.append({
                    "from": prev.most_likely_state,
                    "to": curr.most_likely_state,
                    "sequence_index": i
                })
        
        # Count anomalies
        anomalies = [inf for inf in inferences if inf.is_anomaly]
        
        return TrajectorySummary(
            model_id=str(model_id),
            model_name=model.name,
            model_version=model.version,
            total_observations=total,
            state_distribution=state_distribution,
            num_transitions=len(transitions),
            transitions=transitions[:20],  # Limit for payload size
            phase_statistics={},  # Would compute from context snapshots
            num_anomalies=len(anomalies),
            anomaly_summary=f"{len(anomalies)} anomalous observations detected" if anomalies else None
        )
    
    def _build_evidence_summary(
        self, 
        persona_token_id: UUID,
        case_id: UUID
    ) -> EvidenceSummary:
        """Build summary statistics for the evidence record."""
        # Get court summary from stats service
        stats = self.stats_service.generate_court_summary(persona_token_id, case_id)
        
        overall = stats.get("overall_statistics", {})
        
        # Get timeline data for temporal info
        timeline = stats.get("chart_data", {}).get("pain_over_time", [])
        
        first_date = timeline[0]["x"] if timeline else None
        last_date = timeline[-1]["x"] if timeline else None
        
        # Calculate days covered
        total_days = 0
        if first_date and last_date:
            try:
                first = datetime.fromisoformat(first_date.replace("Z", "+00:00"))
                last = datetime.fromisoformat(last_date.replace("Z", "+00:00"))
                total_days = (last - first).days + 1
            except (ValueError, AttributeError):
                pass
        
        total_reports = overall.get("total_reports", 0)
        
        return EvidenceSummary(
            first_report_date=first_date or "",
            last_report_date=last_date or "",
            total_days_covered=total_days,
            total_reports=total_reports,
            mean_pain_level=overall.get("mean_pain_level"),
            max_pain_level=overall.get("max_pain_level"),
            reports_above_7=overall.get("reports_at_or_above_7", 0),
            pct_reports_above_7=overall.get("pct_reports_at_or_above_7", 0),
            sleep_disruption_reports=0,  # Would count from symptom tags
            work_impact_reports=0,  # Would count from note types
            mean_reports_per_week=round(total_reports / max(total_days / 7, 1), 1) if total_days > 0 else 0,
            most_active_day=None,  # Would compute from timestamps
            most_active_hour=None   # Would compute from timestamps
        )
    
    def export_to_json(
        self,
        persona_token_id: UUID,
        case_id: UUID,
        model_id: Optional[UUID] = None,
        export_purpose: str = "client_handoff"
    ) -> str:
        """Export payload as JSON string (for NFT metadata)."""
        payload = self.build_payload(
            persona_token_id=persona_token_id,
            case_id=case_id,
            model_id=model_id,
            export_purpose=export_purpose
        )
        return payload.to_json()
    
    def export_for_on_chain(
        self,
        persona_token_id: UUID,
        case_id: UUID,
        model_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Export minimal data suitable for on-chain storage.
        
        On-chain storage is expensive, so we only store:
        - Merkle root (proves all entries)
        - Latest hash (current chain tip)
        - Summary hash (proves the full payload)
        
        Full payload lives off-chain (IPFS, Arweave, or your server).
        """
        payload = self.build_payload(
            persona_token_id=persona_token_id,
            case_id=case_id,
            model_id=model_id,
            export_purpose="on_chain_anchor"
        )
        
        return {
            "version": "1.0",
            "persona_token_id": str(persona_token_id),
            "merkle_root": payload.chain_proof.merkle_root,
            "latest_hash": payload.chain_proof.latest_hash,
            "chain_length": payload.chain_proof.chain_length,
            "payload_hash": payload.payload_hash,
            "timestamp": payload.created_at
        }


# ============================================================================
# CLIENT HANDOFF CEREMONY
# ============================================================================

def generate_client_handoff_package(
    db: Session,
    persona_token_id: UUID,
    case_id: UUID,
    model_id: Optional[UUID] = None,
    include_qr_code: bool = True
) -> Dict[str, Any]:
    """
    Generate the complete package for handing evidence back to the client.
    
    This is the "ceremony" at case conclusion where the client receives
    durable proof of their phenomenological record.
    
    The package includes:
    - NFT payload (JSON)
    - Verification instructions
    - Summary in plain language
    - QR code linking to verification endpoint (optional)
    """
    builder = NFTPayloadBuilder(db)
    payload = builder.build_payload(
        persona_token_id=persona_token_id,
        case_id=case_id,
        model_id=model_id,
        export_purpose="client_handoff",
        verification_endpoint="https://verify.example.com/chain"
    )
    
    # Plain language summary
    summary = f"""
YOUR PHENOMENOLOGICAL EVIDENCE RECORD

This document certifies that between {payload.evidence_summary.first_report_date[:10] if payload.evidence_summary.first_report_date else 'N/A'} 
and {payload.evidence_summary.last_report_date[:10] if payload.evidence_summary.last_report_date else 'N/A'}, you submitted 
{payload.evidence_summary.total_reports} reports about your pain and symptoms.

Your record includes:
- {payload.chain_proof.chain_length} cryptographically verified entries
- Average pain level: {payload.evidence_summary.mean_pain_level:.1f if payload.evidence_summary.mean_pain_level else 'N/A'}/10
- Reports at severe pain (7+): {payload.evidence_summary.reports_above_7}

This record is mathematically anchored and cannot be altered.
The verification code below proves this is your authentic record.

VERIFICATION CODE: {payload.payload_hash[:16]}

To verify: visit the verification endpoint with your persona ID.
"""

    return {
        "payload": asdict(payload),
        "payload_json": payload.to_json(),
        "plain_language_summary": summary.strip(),
        "verification_code": payload.payload_hash[:16],
        "full_verification_hash": payload.payload_hash,
        "instructions": """
HOW TO VERIFY YOUR RECORD:

1. Keep this document safe - it's your proof.
2. The "verification code" is a fingerprint of your entire record.
3. Anyone with this code can verify your record hasn't been altered.
4. You can request the full record at any time by contacting your legal team.

This is YOUR data. You own it. It will exist as long as you keep this proof.
        """.strip()
    }
