"""
Temporal, Spatial, and Statistical Context Layer

This module adds the "time, space, and stats" that make the phenomenological
record legible to a jury.

Key distinctions:
- event_time: when the experience happened (subjective/reported)
- recorded_at: when the system recorded it
- verified_at: when chain verification was last run

Plus spatial/contextual metadata that enables queries like:
- "Pain at work vs at home"
- "Symptoms before vs after surgery"
- "% of days with pain ≥7/10 in 6 months post-injury"
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID, uuid4
from enum import Enum
from collections import defaultdict

from sqlalchemy import (
    Column, String, Text, Boolean, Integer, Float,
    DateTime, ForeignKey, JSON, and_, or_, func as sqlfunc
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column, Session
from sqlalchemy.sql import func

from models import Base, AttestedEntry, PainState, PerspectiveNote


# ============================================================================
# ENUMS
# ============================================================================

class LocationType(str, Enum):
    """Coarse location categories (no street addresses)."""
    HOME = "home"
    WORK = "work"
    HOSPITAL = "hospital"
    CLINIC = "clinic"
    PHARMACY = "pharmacy"
    PHYSICAL_THERAPY = "physical_therapy"
    OUTDOORS = "outdoors"
    VEHICLE = "vehicle"
    OTHER = "other"


class PostureType(str, Enum):
    """Body position at time of report."""
    LYING = "lying"
    SITTING = "sitting"
    STANDING = "standing"
    WALKING = "walking"
    EXERCISING = "exercising"
    OTHER = "other"


class ExertionLevel(str, Enum):
    """Activity level at time of report."""
    REST = "rest"
    LIGHT = "light"
    MODERATE = "moderate"
    VIGOROUS = "vigorous"


class CasePhase(str, Enum):
    """Temporal phase in the case lifecycle."""
    PRE_INJURY = "pre_injury"
    ACUTE = "acute"           # 0-6 weeks
    SUBACUTE = "subacute"     # 6 weeks - 3 months
    CHRONIC = "chronic"       # 3+ months
    POST_TREATMENT = "post_treatment"
    PLATEAU = "plateau"       # Maximum medical improvement


# ============================================================================
# CONTEXT SNAPSHOT MODEL
# ============================================================================

class ContextSnapshot(Base):
    """
    Captures the phenomenological context at the moment of an attestation.
    
    This is the "where, how, and what else" that gives meaning to pain
    and symptom reports. Enables powerful queries for court:
    - "Show all reports made at work"
    - "Compare pain levels lying down vs standing"
    - "Trajectory over the acute phase"
    """
    __tablename__ = "context_snapshots"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Link to attestation entry
    attested_entry_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("attested_entries.id"),
        unique=True,
        nullable=False
    )
    
    # ========================================================================
    # TEMPORAL SEMANTICS
    # ========================================================================
    
    # When the experience/event OCCURRED (subjective/reported)
    event_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # When the system RECORDED it (objective)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    
    # When chain verification was last run on this entry
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Case phase at time of report
    case_phase: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    
    # Days since injury (computed, for easy querying)
    days_since_injury: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # ========================================================================
    # SPATIAL / LOCATION (PHI-safe, coarse only)
    # ========================================================================
    
    location_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    location_city: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    location_state: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    timezone_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    
    # ========================================================================
    # PHENOMENOLOGICAL CONTEXT
    # ========================================================================
    
    posture: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    exertion_level: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    
    # Environmental factors
    environment_tags: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    # e.g., ["noisy", "bright", "cold", "stressful"]
    
    # Activity at time of report
    activity_description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # ========================================================================
    # MEDICAL CONTEXT
    # ========================================================================
    
    # Recent treatments (PHI-light)
    recent_treatment_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    hours_since_treatment: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Medication context (generic, no specific drug names in this field)
    medication_context: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    # e.g., "before_medication", "2h_post_dose", "medication_wearing_off"
    
    # ========================================================================
    # EXTENSIBLE CONTEXT
    # ========================================================================
    
    raw_context_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ============================================================================
# CASE TIMELINE MODEL
# ============================================================================

class CaseTimeline(Base):
    """
    Key dates in the case for computing phases and relative timing.
    
    This enables automatic computation of:
    - days_since_injury
    - case_phase
    - pre/post treatment comparisons
    """
    __tablename__ = "case_timelines"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    
    # Key dates
    injury_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    # Treatment milestones
    first_treatment_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    surgery_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Case milestones
    mmi_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)  # Maximum Medical Improvement
    litigation_start_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Phase boundaries (customizable per case)
    acute_end_days: Mapped[int] = mapped_column(Integer, default=42)      # 6 weeks
    subacute_end_days: Mapped[int] = mapped_column(Integer, default=90)   # 3 months
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    def compute_phase(self, event_date: datetime) -> CasePhase:
        """Determine the case phase for a given date."""
        if event_date < self.injury_date:
            return CasePhase.PRE_INJURY
        
        days_since = (event_date - self.injury_date).days
        
        if self.mmi_date and event_date >= self.mmi_date:
            return CasePhase.PLATEAU
        
        if days_since <= self.acute_end_days:
            return CasePhase.ACUTE
        elif days_since <= self.subacute_end_days:
            return CasePhase.SUBACUTE
        else:
            return CasePhase.CHRONIC
    
    def compute_days_since_injury(self, event_date: datetime) -> int:
        """Compute days since injury (negative if pre-injury)."""
        return (event_date - self.injury_date).days


# ============================================================================
# STATISTICS SERVICE
# ============================================================================

class PhenomenologyStatsService:
    """
    Computes statistics over the phenomenological record for court presentation.
    
    Produces data suitable for:
    - Pain timeline charts
    - Phase-based comparisons
    - Location/activity correlations
    - Summary statistics for settlement/trial
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_pain_timeline(
        self,
        persona_token_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Get pain readings over time for timeline visualization.
        
        Returns list of:
        {
            "recorded_at": <datetime>,
            "event_time": <datetime or null>,
            "value": <float>,
            "location": <str>,
            "quality": <str>,
            "case_phase": <str or null>,
            "context": {...}
        }
        """
        from models import PainState, Party, PersonaToken
        
        # Get party_id from persona_token
        persona = self.db.query(PersonaToken).filter(
            PersonaToken.id == persona_token_id
        ).first()
        
        if not persona:
            return []
        
        query = self.db.query(PainState).filter(
            PainState.party_id == persona.party_id
        ).order_by(PainState.recorded_at.asc())
        
        if start_date:
            query = query.filter(PainState.recorded_at >= start_date)
        if end_date:
            query = query.filter(PainState.recorded_at <= end_date)
        
        results = []
        for pain in query.all():
            # Try to get context
            context = None
            if pain.id:
                # Look up attestation and context
                entry = self.db.query(AttestedEntry).filter(
                    AttestedEntry.domain_table == "PainState",
                    AttestedEntry.domain_id == pain.id
                ).first()
                
                if entry:
                    ctx = self.db.query(ContextSnapshot).filter(
                        ContextSnapshot.attested_entry_id == entry.id
                    ).first()
                    if ctx:
                        context = {
                            "location_type": ctx.location_type,
                            "posture": ctx.posture,
                            "case_phase": ctx.case_phase,
                            "days_since_injury": ctx.days_since_injury
                        }
            
            results.append({
                "recorded_at": pain.recorded_at.isoformat() if pain.recorded_at else None,
                "value": pain.value,
                "location": pain.location,
                "quality": pain.quality,
                "functional_impact": pain.functional_impact,
                "context": context
            })
        
        return results
    
    def compute_phase_statistics(
        self,
        persona_token_id: UUID,
        case_id: UUID
    ) -> Dict[str, Dict[str, Any]]:
        """
        Compute statistics by case phase.
        
        Returns:
        {
            "acute": {
                "count": <int>,
                "mean_pain": <float>,
                "max_pain": <float>,
                "pain_days_pct": <float>,
                "high_pain_days_pct": <float>  # days with pain >= 7
            },
            "subacute": {...},
            "chronic": {...}
        }
        """
        # Get timeline for phase computation
        timeline = self.db.query(CaseTimeline).filter(
            CaseTimeline.case_id == case_id
        ).first()
        
        if not timeline:
            return {}
        
        # Get persona's party_id
        persona = self.db.query(PersonaToken).filter(
            PersonaToken.id == persona_token_id
        ).first()
        
        if not persona:
            return {}
        
        # Get all pain states
        pain_states = self.db.query(PainState).filter(
            PainState.party_id == persona.party_id
        ).all()
        
        # Bucket by phase
        phase_data = defaultdict(list)
        for pain in pain_states:
            if pain.recorded_at:
                phase = timeline.compute_phase(pain.recorded_at)
                phase_data[phase.value].append(pain.value)
        
        # Compute stats per phase
        results = {}
        for phase, values in phase_data.items():
            if values:
                results[phase] = {
                    "count": len(values),
                    "mean_pain": sum(values) / len(values),
                    "max_pain": max(values),
                    "min_pain": min(values),
                    "high_pain_count": len([v for v in values if v >= 7]),
                    "high_pain_pct": len([v for v in values if v >= 7]) / len(values) * 100
                }
        
        return results
    
    def compute_location_comparison(
        self,
        persona_token_id: UUID
    ) -> Dict[str, Dict[str, Any]]:
        """
        Compare pain levels by location type (home vs work vs hospital).
        
        Useful for demonstrating:
        - Work-related exacerbation
        - Treatment effects
        - Environmental factors
        """
        # Get all pain attestations with context
        entries = self.db.query(AttestedEntry, ContextSnapshot).join(
            ContextSnapshot,
            ContextSnapshot.attested_entry_id == AttestedEntry.id
        ).filter(
            AttestedEntry.persona_token_id == persona_token_id,
            AttestedEntry.domain_table == "PainState"
        ).all()
        
        location_data = defaultdict(list)
        
        for entry, context in entries:
            if context.location_type:
                # Get the actual pain value
                pain = self.db.query(PainState).filter(
                    PainState.id == entry.domain_id
                ).first()
                if pain:
                    location_data[context.location_type].append(pain.value)
        
        results = {}
        for location, values in location_data.items():
            if values:
                results[location] = {
                    "count": len(values),
                    "mean_pain": sum(values) / len(values),
                    "max_pain": max(values),
                    "min_pain": min(values)
                }
        
        return results
    
    def generate_court_summary(
        self,
        persona_token_id: UUID,
        case_id: UUID
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive summary suitable for court presentation.
        
        This is the data that feeds settlement demand letters,
        mediation briefs, and trial exhibits.
        """
        timeline_data = self.get_pain_timeline(persona_token_id)
        phase_stats = self.compute_phase_statistics(persona_token_id, case_id)
        location_stats = self.compute_location_comparison(persona_token_id)
        
        # Compute overall statistics
        all_pain_values = [d["value"] for d in timeline_data if d["value"] is not None]
        
        total_days_tracked = 0
        if timeline_data:
            first_date = timeline_data[0]["recorded_at"]
            last_date = timeline_data[-1]["recorded_at"]
            if first_date and last_date:
                first = datetime.fromisoformat(first_date)
                last = datetime.fromisoformat(last_date)
                total_days_tracked = (last - first).days + 1
        
        return {
            "summary_generated_at": datetime.now(timezone.utc).isoformat(),
            "persona_token_id": str(persona_token_id),
            "case_id": str(case_id),
            
            "overall_statistics": {
                "total_reports": len(timeline_data),
                "total_days_tracked": total_days_tracked,
                "mean_pain_level": sum(all_pain_values) / len(all_pain_values) if all_pain_values else None,
                "max_pain_level": max(all_pain_values) if all_pain_values else None,
                "reports_at_or_above_7": len([v for v in all_pain_values if v >= 7]),
                "pct_reports_at_or_above_7": (
                    len([v for v in all_pain_values if v >= 7]) / len(all_pain_values) * 100
                    if all_pain_values else None
                )
            },
            
            "phase_statistics": phase_stats,
            "location_statistics": location_stats,
            
            "timeline_data_points": len(timeline_data),
            
            # For visualization
            "chart_data": {
                "pain_over_time": [
                    {"x": d["recorded_at"], "y": d["value"]}
                    for d in timeline_data
                    if d["recorded_at"] and d["value"] is not None
                ]
            }
        }


# ============================================================================
# CONTEXT ENRICHMENT SERVICE
# ============================================================================

class ContextEnrichmentService:
    """
    Automatically enriches attestation entries with context.
    
    Called after attestation to add:
    - Temporal semantics (phase, days since injury)
    - Location inference (from timezone, IP, etc.)
    - Activity inference (from time of day, recent entries)
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def enrich_entry(
        self,
        entry: AttestedEntry,
        case_id: UUID,
        event_time: Optional[datetime] = None,
        location_type: Optional[str] = None,
        posture: Optional[str] = None,
        exertion_level: Optional[str] = None,
        environment_tags: Optional[List[str]] = None,
        activity_description: Optional[str] = None,
        raw_context: Optional[dict] = None
    ) -> ContextSnapshot:
        """
        Create a ContextSnapshot for an attestation entry.
        """
        # Get case timeline for phase computation
        timeline = self.db.query(CaseTimeline).filter(
            CaseTimeline.case_id == case_id
        ).first()
        
        # Compute temporal fields
        recorded_at = entry.created_at or datetime.now(timezone.utc)
        reference_time = event_time or recorded_at
        
        case_phase = None
        days_since_injury = None
        
        if timeline:
            case_phase = timeline.compute_phase(reference_time).value
            days_since_injury = timeline.compute_days_since_injury(reference_time)
        
        snapshot = ContextSnapshot(
            attested_entry_id=entry.id,
            event_time=event_time,
            recorded_at=recorded_at,
            case_phase=case_phase,
            days_since_injury=days_since_injury,
            location_type=location_type,
            posture=posture,
            exertion_level=exertion_level,
            environment_tags=environment_tags,
            activity_description=activity_description,
            raw_context_json=raw_context
        )
        
        self.db.add(snapshot)
        return snapshot
