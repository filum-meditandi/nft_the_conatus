"""
HMM Feature Schema and Extraction Layer

This module defines the feature space for Hidden Markov Model inference
over the phenomenological record.

Design principles:
1. TRACEABLE - every feature vector ties back to an attested_entry_id
2. REPRODUCIBLE - deterministic extraction from canonical payloads
3. SEMANTICALLY GROUNDED - maps to clinician/jury-understandable concepts
4. PHI-SAFE - derived from normalized projections, not raw PHI

The feature vector is a projection of lived experience into a space
where statistical inference becomes possible, while preserving the
evidential chain back to the original attestations.

Feature categories:
- Pain/symptom intensity (continuous)
- Pain characteristics (categorical)
- Temporal features (cyclical, relative)
- Functional impact (ordinal)
- Context/environment (categorical)
- Trajectory features (derived from sequence)
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID, uuid4
from enum import Enum
from dataclasses import dataclass, field
import math
import json

from sqlalchemy import (
    Column, String, Text, Integer, Float, Boolean,
    DateTime, ForeignKey, JSON
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB, ARRAY
from sqlalchemy.orm import relationship, Mapped, mapped_column, Session
from sqlalchemy.sql import func

from models import Base, AttestedEntry, PainState, PerspectiveNote
from context_layer import ContextSnapshot, CaseTimeline


# ============================================================================
# FEATURE SCHEMA DEFINITION
# ============================================================================

class FeatureType(str, Enum):
    """Types of features for documentation and validation."""
    CONTINUOUS = "continuous"      # Real-valued (pain score, hours)
    ORDINAL = "ordinal"           # Ordered categories (none/mild/moderate/severe)
    CATEGORICAL = "categorical"    # Unordered categories (location, quality)
    BINARY = "binary"             # Yes/no features
    CYCLICAL = "cyclical"         # Time-of-day, day-of-week (encoded as sin/cos)
    DERIVED = "derived"           # Computed from other features or sequence


@dataclass
class FeatureDefinition:
    """
    Schema definition for a single feature.
    
    This is the "model card" for each feature - documents what it means,
    how it's extracted, and its valid range.
    """
    name: str
    feature_type: FeatureType
    description: str
    
    # Extraction source
    source_field: str  # Which field in the attestation/context it comes from
    extraction_method: str  # How to extract (direct, map, compute, etc.)
    
    # Validation
    valid_range: Optional[Tuple[float, float]] = None  # For continuous
    valid_values: Optional[List[str]] = None  # For categorical
    
    # Missing value handling
    missing_strategy: str = "impute_median"  # impute_median, impute_mode, mask, error
    default_value: Optional[Any] = None
    
    # For cyclical features
    period: Optional[float] = None  # e.g., 24.0 for hours, 7.0 for days


# The canonical feature schema - this is the contract between
# the phenomenological record and the HMM inference layer
FEATURE_SCHEMA: List[FeatureDefinition] = [
    
    # ========================================================================
    # PAIN INTENSITY FEATURES
    # ========================================================================
    
    FeatureDefinition(
        name="pain_score",
        feature_type=FeatureType.CONTINUOUS,
        description="Self-reported pain intensity on 0-10 scale",
        source_field="PainState.value",
        extraction_method="direct",
        valid_range=(0.0, 10.0),
        missing_strategy="mask",
        default_value=None
    ),
    
    FeatureDefinition(
        name="pain_score_normalized",
        feature_type=FeatureType.CONTINUOUS,
        description="Pain score normalized to [0,1] range",
        source_field="PainState.value",
        extraction_method="normalize_0_10",
        valid_range=(0.0, 1.0),
        missing_strategy="impute_median",
        default_value=0.5
    ),
    
    FeatureDefinition(
        name="severity_level",
        feature_type=FeatureType.ORDINAL,
        description="Coarse severity from normalized note (1-10)",
        source_field="SubjectiveNote.severity_level",
        extraction_method="direct",
        valid_range=(1, 10),
        missing_strategy="impute_median",
        default_value=5
    ),
    
    # ========================================================================
    # PAIN CHARACTERISTIC FEATURES (CATEGORICAL)
    # ========================================================================
    
    FeatureDefinition(
        name="pain_location",
        feature_type=FeatureType.CATEGORICAL,
        description="Primary body region of pain",
        source_field="PainState.location",
        extraction_method="map_to_category",
        valid_values=[
            "cervical", "thoracic", "lumbar", "head", 
            "upper_extremity", "lower_extremity", "diffuse", "other"
        ],
        missing_strategy="impute_mode",
        default_value="other"
    ),
    
    FeatureDefinition(
        name="pain_quality",
        feature_type=FeatureType.CATEGORICAL,
        description="Character of pain sensation",
        source_field="PainState.quality",
        extraction_method="map_to_category",
        valid_values=[
            "sharp", "dull", "burning", "throbbing", 
            "shooting", "aching", "tingling", "other"
        ],
        missing_strategy="impute_mode",
        default_value="other"
    ),
    
    # ========================================================================
    # FUNCTIONAL IMPACT FEATURES
    # ========================================================================
    
    FeatureDefinition(
        name="sleep_impact",
        feature_type=FeatureType.ORDINAL,
        description="Impact on sleep quality (0=none, 10=severe)",
        source_field="PainState.functional_impact.sleep",
        extraction_method="extract_nested",
        valid_range=(0, 10),
        missing_strategy="impute_median",
        default_value=5
    ),
    
    FeatureDefinition(
        name="work_impact",
        feature_type=FeatureType.ORDINAL,
        description="Impact on work capacity (0=none, 10=severe)",
        source_field="PainState.functional_impact.work",
        extraction_method="extract_nested",
        valid_range=(0, 10),
        missing_strategy="impute_median",
        default_value=5
    ),
    
    FeatureDefinition(
        name="adl_impact",
        feature_type=FeatureType.ORDINAL,
        description="Impact on activities of daily living (0=none, 10=severe)",
        source_field="PainState.functional_impact.adls",
        extraction_method="extract_nested",
        valid_range=(0, 10),
        missing_strategy="impute_median",
        default_value=5
    ),
    
    FeatureDefinition(
        name="has_sleep_complaint",
        feature_type=FeatureType.BINARY,
        description="Whether sleep disruption was mentioned",
        source_field="SubjectiveNote.symptom_tags",
        extraction_method="check_tag_presence",
        valid_values=["sleep_disruption"],
        missing_strategy="impute_mode",
        default_value=0
    ),
    
    # ========================================================================
    # TEMPORAL FEATURES (CYCLICAL)
    # ========================================================================
    
    FeatureDefinition(
        name="hour_of_day_sin",
        feature_type=FeatureType.CYCLICAL,
        description="Sine component of hour (captures daily rhythm)",
        source_field="ContextSnapshot.recorded_at",
        extraction_method="cyclical_hour_sin",
        valid_range=(-1.0, 1.0),
        period=24.0,
        missing_strategy="impute_median",
        default_value=0.0
    ),
    
    FeatureDefinition(
        name="hour_of_day_cos",
        feature_type=FeatureType.CYCLICAL,
        description="Cosine component of hour (captures daily rhythm)",
        source_field="ContextSnapshot.recorded_at",
        extraction_method="cyclical_hour_cos",
        valid_range=(-1.0, 1.0),
        period=24.0,
        missing_strategy="impute_median",
        default_value=1.0
    ),
    
    FeatureDefinition(
        name="day_of_week_sin",
        feature_type=FeatureType.CYCLICAL,
        description="Sine component of day of week (captures weekly rhythm)",
        source_field="ContextSnapshot.recorded_at",
        extraction_method="cyclical_dow_sin",
        valid_range=(-1.0, 1.0),
        period=7.0,
        missing_strategy="impute_median",
        default_value=0.0
    ),
    
    FeatureDefinition(
        name="day_of_week_cos",
        feature_type=FeatureType.CYCLICAL,
        description="Cosine component of day of week (captures weekly rhythm)",
        source_field="ContextSnapshot.recorded_at",
        extraction_method="cyclical_dow_cos",
        valid_range=(-1.0, 1.0),
        period=7.0,
        missing_strategy="impute_median",
        default_value=1.0
    ),
    
    FeatureDefinition(
        name="days_since_injury",
        feature_type=FeatureType.CONTINUOUS,
        description="Days elapsed since injury date",
        source_field="ContextSnapshot.days_since_injury",
        extraction_method="direct",
        valid_range=(0, 3650),  # Up to 10 years
        missing_strategy="error",
        default_value=None
    ),
    
    FeatureDefinition(
        name="is_weekend",
        feature_type=FeatureType.BINARY,
        description="Whether report was on Saturday or Sunday",
        source_field="ContextSnapshot.recorded_at",
        extraction_method="compute_is_weekend",
        missing_strategy="impute_mode",
        default_value=0
    ),
    
    # ========================================================================
    # CONTEXT FEATURES
    # ========================================================================
    
    FeatureDefinition(
        name="location_type",
        feature_type=FeatureType.CATEGORICAL,
        description="Where the report was made",
        source_field="ContextSnapshot.location_type",
        extraction_method="direct",
        valid_values=["home", "work", "hospital", "clinic", "pt", "vehicle", "other"],
        missing_strategy="impute_mode",
        default_value="home"
    ),
    
    FeatureDefinition(
        name="posture",
        feature_type=FeatureType.CATEGORICAL,
        description="Body position at time of report",
        source_field="ContextSnapshot.posture",
        extraction_method="direct",
        valid_values=["lying", "sitting", "standing", "walking", "exercising", "other"],
        missing_strategy="impute_mode",
        default_value="other"
    ),
    
    FeatureDefinition(
        name="exertion_level",
        feature_type=FeatureType.ORDINAL,
        description="Activity level (0=rest, 3=vigorous)",
        source_field="ContextSnapshot.exertion_level",
        extraction_method="map_exertion_to_ordinal",
        valid_range=(0, 3),
        missing_strategy="impute_median",
        default_value=1
    ),
    
    FeatureDefinition(
        name="case_phase",
        feature_type=FeatureType.CATEGORICAL,
        description="Phase in case timeline",
        source_field="ContextSnapshot.case_phase",
        extraction_method="direct",
        valid_values=["pre_injury", "acute", "subacute", "chronic", "plateau"],
        missing_strategy="impute_mode",
        default_value="chronic"
    ),
    
    # ========================================================================
    # DERIVED / SEQUENCE FEATURES
    # ========================================================================
    
    FeatureDefinition(
        name="pain_delta",
        feature_type=FeatureType.DERIVED,
        description="Change in pain score from previous observation",
        source_field="computed",
        extraction_method="compute_delta_from_previous",
        valid_range=(-10.0, 10.0),
        missing_strategy="impute_median",
        default_value=0.0
    ),
    
    FeatureDefinition(
        name="hours_since_last_report",
        feature_type=FeatureType.DERIVED,
        description="Hours elapsed since previous observation",
        source_field="computed",
        extraction_method="compute_hours_since_previous",
        valid_range=(0, 720),  # Up to 30 days
        missing_strategy="impute_median",
        default_value=24.0
    ),
    
    FeatureDefinition(
        name="report_frequency_7d",
        feature_type=FeatureType.DERIVED,
        description="Number of reports in the past 7 days",
        source_field="computed",
        extraction_method="compute_rolling_count",
        valid_range=(0, 100),
        missing_strategy="impute_median",
        default_value=3.0
    ),
]


# ============================================================================
# FEATURE VECTOR MODEL
# ============================================================================

class FeatureVector(Base):
    """
    Extracted feature vector for a single attestation.
    
    This is the bridge between the phenomenological record and
    statistical inference. Every vector is traceable back to its
    source attestation.
    """
    __tablename__ = "feature_vectors"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Traceability - which attestation this came from
    attested_entry_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("attested_entries.id"),
        unique=True,
        nullable=False,
        index=True
    )
    
    # The persona this belongs to (denormalized for query efficiency)
    persona_token_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        index=True,
        nullable=False
    )
    
    # Schema version (for reproducibility)
    schema_version: Mapped[str] = mapped_column(String(32), default="1.0")
    
    # The actual feature values (as JSON for flexibility)
    # Keys match FeatureDefinition.name
    features: Mapped[dict] = mapped_column(JSONB, nullable=False)
    
    # Which features are missing/masked
    missing_mask: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    
    # Extraction metadata
    extracted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now()
    )
    extraction_duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Sequence position (for HMM)
    sequence_index: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Temporal ordering
    observation_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True
    )

    def to_array(self, feature_names: Optional[List[str]] = None) -> List[float]:
        """
        Convert to numeric array for HMM input.
        
        Args:
            feature_names: Specific features to include (in order).
                          If None, uses all features in schema order.
        
        Returns:
            List of float values (categorical features must be pre-encoded)
        """
        if feature_names is None:
            feature_names = [f.name for f in FEATURE_SCHEMA]
        
        return [self.features.get(name, 0.0) for name in feature_names]


# ============================================================================
# FEATURE EXTRACTION SERVICE
# ============================================================================

class FeatureExtractionService:
    """
    Extracts feature vectors from attestation entries.
    
    This service transforms the phenomenological record into
    a form suitable for HMM inference while maintaining full
    traceability back to the source attestations.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.schema = {f.name: f for f in FEATURE_SCHEMA}
    
    def extract_for_entry(
        self,
        entry: AttestedEntry,
        context: Optional[ContextSnapshot] = None,
        pain_state: Optional[PainState] = None,
        previous_vector: Optional[FeatureVector] = None,
        sequence_index: int = 0
    ) -> FeatureVector:
        """
        Extract a feature vector for a single attestation entry.
        """
        import time
        start_time = time.time()
        
        features = {}
        missing_mask = {}
        
        # Get associated data if not provided
        if context is None:
            context = self.db.query(ContextSnapshot).filter(
                ContextSnapshot.attested_entry_id == entry.id
            ).first()
        
        if pain_state is None and entry.domain_table == "PainState":
            pain_state = self.db.query(PainState).filter(
                PainState.id == entry.domain_id
            ).first()
        
        # Extract each feature
        for feature_def in FEATURE_SCHEMA:
            value, is_missing = self._extract_single_feature(
                feature_def, entry, context, pain_state, previous_vector
            )
            features[feature_def.name] = value
            if is_missing:
                missing_mask[feature_def.name] = True
        
        extraction_time = int((time.time() - start_time) * 1000)
        
        # Determine observation time
        observation_time = entry.created_at
        if context and context.event_time:
            observation_time = context.event_time
        
        vector = FeatureVector(
            attested_entry_id=entry.id,
            persona_token_id=entry.persona_token_id,
            schema_version="1.0",
            features=features,
            missing_mask=missing_mask if missing_mask else None,
            extraction_duration_ms=extraction_time,
            sequence_index=sequence_index,
            observation_time=observation_time
        )
        
        return vector
    
    def _extract_single_feature(
        self,
        feature_def: FeatureDefinition,
        entry: AttestedEntry,
        context: Optional[ContextSnapshot],
        pain_state: Optional[PainState],
        previous_vector: Optional[FeatureVector]
    ) -> Tuple[Any, bool]:
        """
        Extract a single feature value.
        
        Returns: (value, is_missing)
        """
        method = feature_def.extraction_method
        is_missing = False
        value = None
        
        try:
            if method == "direct":
                value = self._extract_direct(feature_def, context, pain_state)
            elif method == "normalize_0_10":
                raw = self._extract_direct(feature_def, context, pain_state)
                value = raw / 10.0 if raw is not None else None
            elif method == "map_to_category":
                value = self._map_to_category(feature_def, context, pain_state)
            elif method == "extract_nested":
                value = self._extract_nested(feature_def, pain_state)
            elif method == "check_tag_presence":
                value = self._check_tag_presence(feature_def, entry)
            elif method.startswith("cyclical_"):
                value = self._extract_cyclical(feature_def, context)
            elif method == "compute_is_weekend":
                value = self._compute_is_weekend(context)
            elif method == "map_exertion_to_ordinal":
                value = self._map_exertion(context)
            elif method == "compute_delta_from_previous":
                value = self._compute_delta(pain_state, previous_vector)
            elif method == "compute_hours_since_previous":
                value = self._compute_hours_since(entry, previous_vector)
            else:
                value = feature_def.default_value
                is_missing = True
        except Exception:
            value = None
        
        # Handle missing values
        if value is None:
            is_missing = True
            if feature_def.missing_strategy == "error":
                raise ValueError(f"Missing required feature: {feature_def.name}")
            value = feature_def.default_value
        
        return value, is_missing
    
    def _extract_direct(
        self, 
        feature_def: FeatureDefinition,
        context: Optional[ContextSnapshot],
        pain_state: Optional[PainState]
    ) -> Any:
        """Extract value directly from source field."""
        source = feature_def.source_field
        
        if source.startswith("PainState.") and pain_state:
            field_name = source.split(".")[1]
            return getattr(pain_state, field_name, None)
        elif source.startswith("ContextSnapshot.") and context:
            field_name = source.split(".")[1]
            return getattr(context, field_name, None)
        
        return None
    
    def _map_to_category(
        self,
        feature_def: FeatureDefinition,
        context: Optional[ContextSnapshot],
        pain_state: Optional[PainState]
    ) -> str:
        """Map raw value to valid category."""
        raw = self._extract_direct(feature_def, context, pain_state)
        
        if raw is None:
            return feature_def.default_value
        
        raw_lower = str(raw).lower()
        
        # Try exact match first
        if raw_lower in feature_def.valid_values:
            return raw_lower
        
        # Try fuzzy matching for pain location
        if feature_def.name == "pain_location":
            location_map = {
                "neck": "cervical",
                "c-spine": "cervical",
                "upper back": "thoracic",
                "mid back": "thoracic",
                "low back": "lumbar",
                "lower back": "lumbar",
                "l-spine": "lumbar",
                "head": "head",
                "headache": "head",
                "arm": "upper_extremity",
                "shoulder": "upper_extremity",
                "hand": "upper_extremity",
                "leg": "lower_extremity",
                "hip": "lower_extremity",
                "knee": "lower_extremity",
                "foot": "lower_extremity",
            }
            for key, value in location_map.items():
                if key in raw_lower:
                    return value
        
        return feature_def.default_value
    
    def _extract_nested(
        self,
        feature_def: FeatureDefinition,
        pain_state: Optional[PainState]
    ) -> Any:
        """Extract from nested JSON field."""
        if not pain_state or not pain_state.functional_impact:
            return None
        
        # Parse the nested path
        parts = feature_def.source_field.split(".")
        if len(parts) >= 3:
            key = parts[2]  # e.g., "sleep" from "PainState.functional_impact.sleep"
            return pain_state.functional_impact.get(key)
        
        return None
    
    def _check_tag_presence(
        self,
        feature_def: FeatureDefinition,
        entry: AttestedEntry
    ) -> int:
        """Check if a tag is present in symptom tags."""
        # Would need to look up the SubjectiveNote
        # For now, return default
        return 0
    
    def _extract_cyclical(
        self,
        feature_def: FeatureDefinition,
        context: Optional[ContextSnapshot]
    ) -> float:
        """Extract cyclical time feature using sin/cos encoding."""
        if not context or not context.recorded_at:
            return feature_def.default_value
        
        dt = context.recorded_at
        method = feature_def.extraction_method
        
        if "hour" in method:
            value = dt.hour + dt.minute / 60.0
            period = 24.0
        elif "dow" in method:
            value = dt.weekday()
            period = 7.0
        else:
            return feature_def.default_value
        
        angle = 2 * math.pi * value / period
        
        if method.endswith("_sin"):
            return math.sin(angle)
        else:
            return math.cos(angle)
    
    def _compute_is_weekend(self, context: Optional[ContextSnapshot]) -> int:
        """Check if observation was on weekend."""
        if not context or not context.recorded_at:
            return 0
        return 1 if context.recorded_at.weekday() >= 5 else 0
    
    def _map_exertion(self, context: Optional[ContextSnapshot]) -> int:
        """Map exertion level to ordinal."""
        if not context or not context.exertion_level:
            return 1
        
        mapping = {
            "rest": 0,
            "light": 1,
            "moderate": 2,
            "vigorous": 3
        }
        return mapping.get(context.exertion_level.lower(), 1)
    
    def _compute_delta(
        self,
        pain_state: Optional[PainState],
        previous_vector: Optional[FeatureVector]
    ) -> float:
        """Compute change in pain from previous observation."""
        if not pain_state or not previous_vector:
            return 0.0
        
        current = pain_state.value
        previous = previous_vector.features.get("pain_score", current)
        
        return current - previous
    
    def _compute_hours_since(
        self,
        entry: AttestedEntry,
        previous_vector: Optional[FeatureVector]
    ) -> float:
        """Compute hours since previous observation."""
        if not previous_vector:
            return 24.0  # Default to 1 day
        
        delta = entry.created_at - previous_vector.observation_time
        return delta.total_seconds() / 3600.0
    
    def extract_sequence(
        self,
        persona_token_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[FeatureVector]:
        """
        Extract feature vectors for a sequence of attestations.
        
        Returns vectors in temporal order, with sequence indices
        and derived features computed relative to previous observations.
        """
        # Get all attestation entries for this persona
        query = self.db.query(AttestedEntry).filter(
            AttestedEntry.persona_token_id == persona_token_id
        ).order_by(AttestedEntry.sequence_number.asc())
        
        if start_date:
            query = query.filter(AttestedEntry.created_at >= start_date)
        if end_date:
            query = query.filter(AttestedEntry.created_at <= end_date)
        
        entries = query.all()
        
        vectors = []
        previous_vector = None
        
        for idx, entry in enumerate(entries):
            vector = self.extract_for_entry(
                entry=entry,
                previous_vector=previous_vector,
                sequence_index=idx
            )
            vectors.append(vector)
            previous_vector = vector
        
        return vectors
    
    def save_vectors(self, vectors: List[FeatureVector]) -> None:
        """Persist extracted feature vectors to database."""
        for v in vectors:
            self.db.add(v)
        self.db.commit()


# ============================================================================
# FEATURE SCHEMA DOCUMENTATION
# ============================================================================

def generate_feature_schema_documentation() -> str:
    """
    Generate human-readable documentation of the feature schema.
    
    This is part of the "model card" for Daubert compliance.
    """
    doc = """
# Phenomenological Feature Schema v1.0

## Overview

This document defines the features extracted from phenomenological attestations
for use in Hidden Markov Model inference. Each feature is:

1. **Traceable** - tied to a specific attestation entry
2. **Reproducible** - deterministically extracted
3. **Semantically grounded** - maps to clinical/legal concepts
4. **PHI-safe** - derived from normalized projections

## Feature Definitions

"""
    for feat in FEATURE_SCHEMA:
        doc += f"""
### {feat.name}

- **Type**: {feat.feature_type.value}
- **Description**: {feat.description}
- **Source**: `{feat.source_field}`
- **Extraction**: {feat.extraction_method}
"""
        if feat.valid_range:
            doc += f"- **Valid Range**: {feat.valid_range}\n"
        if feat.valid_values:
            doc += f"- **Valid Values**: {feat.valid_values}\n"
        doc += f"- **Missing Strategy**: {feat.missing_strategy}\n"
        doc += f"- **Default**: {feat.default_value}\n"
    
    return doc


if __name__ == "__main__":
    print(generate_feature_schema_documentation())
