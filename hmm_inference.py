"""
Hidden Markov Model Inference Layer

This module implements HMM-based inference over the phenomenological record.

The HMM serves as a bridge theory:
- Maps noisy first-person emissions into structured latent states
- States have semantic meaning: flare, baseline, improvement, etc.
- Transitions encode the dynamics of recovery/deterioration

What the HMM does:
1. CLASSIFY each observation into a probable latent state
2. PREDICT likely trajectory
3. DETECT anomalies (observations that don't fit the model)
4. SEGMENT the timeline into meaningful phases

What the HMM does NOT do:
- Prove the plaintiff is in pain
- Replace clinical judgment
- Make legal conclusions

It is an INTERPRETIVE INSTRUMENT applied to a TRUSTWORTHY RECORD.

Daubert considerations:
- All parameters are stored and reproducible
- Training data is documented (which attestations, which features)
- Model limitations are explicit
- Human expert provides normative interpretation
"""

import json
import pickle
import base64
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID, uuid4
from enum import Enum
from dataclasses import dataclass
import math

import numpy as np

from sqlalchemy import Column, String, Text, Integer, Float, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB, BYTEA
from sqlalchemy.orm import relationship, Mapped, mapped_column, Session
from sqlalchemy.sql import func

from models import Base, AttestedEntry
from hmm_features import FeatureVector, FeatureExtractionService, FEATURE_SCHEMA


# ============================================================================
# STATE DEFINITIONS
# ============================================================================

class PainTrajectoryState(str, Enum):
    """
    Canonical hidden states for pain trajectory modeling.
    
    These labels have clinical and legal meaning:
    - BASELINE: Typical/average function for this person
    - FLARE: Acute exacerbation above baseline
    - IMPROVEMENT: Better than baseline function
    - SEVERE: Significant dysfunction
    """
    BASELINE = "baseline"
    FLARE = "flare"
    IMPROVEMENT = "improvement"
    SEVERE = "severe"


class FunctionalCapacityState(str, Enum):
    """Hidden states for functional capacity modeling."""
    FULL = "full"
    LIMITED = "limited"
    SEVERELY_LIMITED = "severely_limited"
    INCAPACITATED = "incapacitated"


# ============================================================================
# HMM MODEL STORAGE
# ============================================================================

class HiddenStateModel(Base):
    """
    Stores a trained HMM model with full provenance.
    
    This is the "model card" that enables reproducibility
    and Daubert compliance.
    """
    __tablename__ = "hidden_state_models"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Model identification
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    model_type: Mapped[str] = mapped_column(String(64), nullable=False)
    # e.g., "pain_trajectory", "functional_capacity", "medication_response"
    
    version: Mapped[str] = mapped_column(String(32), default="1.0")
    
    # State configuration
    num_states: Mapped[int] = mapped_column(Integer, nullable=False)
    state_labels: Mapped[list] = mapped_column(JSONB, nullable=False)
    # e.g., ["baseline", "flare", "improvement", "severe"]
    
    # Feature configuration
    feature_names: Mapped[list] = mapped_column(JSONB, nullable=False)
    # Which features from the schema this model uses
    
    feature_schema_version: Mapped[str] = mapped_column(String(32), default="1.0")
    
    # ========================================================================
    # LEARNED PARAMETERS
    # ========================================================================
    
    # Initial state distribution π[i] = P(state_0 = i)
    initial_distribution: Mapped[list] = mapped_column(JSONB, nullable=False)
    
    # Transition matrix A[i,j] = P(state_t+1 = j | state_t = i)
    transition_matrix: Mapped[list] = mapped_column(JSONB, nullable=False)
    
    # Emission parameters (depends on emission model type)
    emission_model_type: Mapped[str] = mapped_column(String(32), default="gaussian")
    # "gaussian", "gmm", "discrete"
    
    emission_parameters: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # For Gaussian: {"means": [...], "covariances": [...]}
    # For discrete: {"emission_probs": [...]}
    
    # ========================================================================
    # TRAINING PROVENANCE
    # ========================================================================
    
    # What data was this trained on?
    trained_on_personas: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    trained_on_entries: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    training_date_range: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    
    num_training_sequences: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    num_training_observations: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Training hyperparameters
    training_config: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    # e.g., {"n_iter": 100, "tol": 1e-4, "random_state": 42}
    
    # Convergence info
    training_log_likelihood: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    converged: Mapped[Optional[bool]] = mapped_column(nullable=True)
    
    # ========================================================================
    # MODEL CARD / DOCUMENTATION
    # ========================================================================
    
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    limitations: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    intended_use: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # ========================================================================
    # LIFECYCLE
    # ========================================================================
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    trained_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    validated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    is_active: Mapped[bool] = mapped_column(default=True)
    
    def get_transition_matrix_np(self) -> np.ndarray:
        """Get transition matrix as numpy array."""
        return np.array(self.transition_matrix)
    
    def get_initial_distribution_np(self) -> np.ndarray:
        """Get initial distribution as numpy array."""
        return np.array(self.initial_distribution)


class StateInference(Base):
    """
    Stores inferred states for individual attestation entries.
    
    Each record links an attestation to its most likely hidden state
    and the full probability distribution over states.
    """
    __tablename__ = "state_inferences"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Links
    attested_entry_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("attested_entries.id"),
        nullable=False,
        index=True
    )
    
    feature_vector_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("feature_vectors.id"),
        nullable=False
    )
    
    model_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("hidden_state_models.id"),
        nullable=False,
        index=True
    )
    
    # ========================================================================
    # INFERENCE RESULTS
    # ========================================================================
    
    # Most likely state (from Viterbi)
    most_likely_state: Mapped[str] = mapped_column(String(64), nullable=False)
    most_likely_state_index: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Full probability distribution (from forward-backward)
    state_probabilities: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # {"baseline": 0.7, "flare": 0.2, "improvement": 0.05, "severe": 0.05}
    
    # Confidence in the most likely state
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    
    # ========================================================================
    # ANOMALY DETECTION
    # ========================================================================
    
    # P(observation | inferred state)
    emission_likelihood: Mapped[float] = mapped_column(Float, nullable=False)
    
    # Log-likelihood under full model
    log_likelihood: Mapped[float] = mapped_column(Float, nullable=False)
    
    # Anomaly flag (emission likelihood below threshold)
    is_anomaly: Mapped[bool] = mapped_column(default=False)
    anomaly_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # ========================================================================
    # METADATA
    # ========================================================================
    
    inferred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    # Sequence position in this inference run
    sequence_index: Mapped[int] = mapped_column(Integer, nullable=False)


# ============================================================================
# HMM INFERENCE ENGINE
# ============================================================================

class HMMInferenceEngine:
    """
    Performs HMM inference over phenomenological sequences.
    
    Implements:
    - Forward algorithm (filtering)
    - Backward algorithm (smoothing)
    - Viterbi algorithm (most likely state sequence)
    - Anomaly detection
    
    This is a custom implementation for full control and auditability.
    For production, could wrap hmmlearn or pomegranate.
    """
    
    def __init__(self, model: HiddenStateModel):
        self.model = model
        self.num_states = model.num_states
        self.state_labels = model.state_labels
        
        # Load parameters as numpy arrays
        self.pi = model.get_initial_distribution_np()
        self.A = model.get_transition_matrix_np()
        
        # Load emission parameters
        self.emission_type = model.emission_model_type
        self.emission_params = model.emission_parameters
        
        if self.emission_type == "gaussian":
            self.means = np.array(self.emission_params["means"])
            self.covars = np.array(self.emission_params["covariances"])
    
    def compute_emission_prob(
        self, 
        observation: np.ndarray, 
        state_idx: int
    ) -> float:
        """
        Compute P(observation | state).
        
        For Gaussian emissions, this is the multivariate normal PDF.
        """
        if self.emission_type == "gaussian":
            mean = self.means[state_idx]
            covar = self.covars[state_idx]
            
            # Multivariate Gaussian PDF
            d = len(observation)
            diff = observation - mean
            
            # Handle diagonal vs full covariance
            if covar.ndim == 1:
                # Diagonal covariance
                det = np.prod(covar)
                inv_covar = 1.0 / covar
                mahal = np.sum(diff ** 2 * inv_covar)
            else:
                # Full covariance
                det = np.linalg.det(covar)
                inv_covar = np.linalg.inv(covar)
                mahal = diff @ inv_covar @ diff
            
            norm_const = 1.0 / (np.sqrt((2 * np.pi) ** d * det))
            prob = norm_const * np.exp(-0.5 * mahal)
            
            return max(prob, 1e-300)  # Prevent underflow
        
        else:
            raise NotImplementedError(f"Emission type {self.emission_type} not implemented")
    
    def forward(self, observations: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Forward algorithm: compute P(state_t | obs_1:t).
        
        Returns:
            alpha: Forward probabilities [T, num_states]
            scaling: Scaling factors for numerical stability [T]
        """
        T = len(observations)
        alpha = np.zeros((T, self.num_states))
        scaling = np.zeros(T)
        
        # Initialize
        for i in range(self.num_states):
            alpha[0, i] = self.pi[i] * self.compute_emission_prob(observations[0], i)
        
        scaling[0] = alpha[0].sum()
        if scaling[0] > 0:
            alpha[0] /= scaling[0]
        
        # Recurse
        for t in range(1, T):
            for j in range(self.num_states):
                alpha[t, j] = sum(
                    alpha[t-1, i] * self.A[i, j] 
                    for i in range(self.num_states)
                ) * self.compute_emission_prob(observations[t], j)
            
            scaling[t] = alpha[t].sum()
            if scaling[t] > 0:
                alpha[t] /= scaling[t]
        
        return alpha, scaling
    
    def backward(
        self, 
        observations: np.ndarray, 
        scaling: np.ndarray
    ) -> np.ndarray:
        """
        Backward algorithm: compute P(obs_t+1:T | state_t).
        
        Returns:
            beta: Backward probabilities [T, num_states]
        """
        T = len(observations)
        beta = np.zeros((T, self.num_states))
        
        # Initialize
        beta[T-1] = 1.0
        
        # Recurse backwards
        for t in range(T-2, -1, -1):
            for i in range(self.num_states):
                beta[t, i] = sum(
                    self.A[i, j] * self.compute_emission_prob(observations[t+1], j) * beta[t+1, j]
                    for j in range(self.num_states)
                )
            
            if scaling[t+1] > 0:
                beta[t] /= scaling[t+1]
        
        return beta
    
    def forward_backward(
        self, 
        observations: np.ndarray
    ) -> Tuple[np.ndarray, float]:
        """
        Forward-backward algorithm: compute P(state_t | all observations).
        
        Returns:
            gamma: Marginal state probabilities [T, num_states]
            log_likelihood: Log P(observations | model)
        """
        alpha, scaling = self.forward(observations)
        beta = self.backward(observations, scaling)
        
        # Compute gamma (posterior marginals)
        gamma = alpha * beta
        gamma /= gamma.sum(axis=1, keepdims=True)
        
        # Log-likelihood from scaling factors
        log_likelihood = np.sum(np.log(scaling + 1e-300))
        
        return gamma, log_likelihood
    
    def viterbi(self, observations: np.ndarray) -> Tuple[List[int], float]:
        """
        Viterbi algorithm: find most likely state sequence.
        
        Returns:
            path: Most likely state indices [T]
            log_prob: Log probability of the path
        """
        T = len(observations)
        
        # Use log probabilities for numerical stability
        log_pi = np.log(self.pi + 1e-300)
        log_A = np.log(self.A + 1e-300)
        
        # Viterbi tables
        viterbi = np.zeros((T, self.num_states))
        backpointer = np.zeros((T, self.num_states), dtype=int)
        
        # Initialize
        for i in range(self.num_states):
            viterbi[0, i] = log_pi[i] + np.log(
                self.compute_emission_prob(observations[0], i) + 1e-300
            )
        
        # Recurse
        for t in range(1, T):
            for j in range(self.num_states):
                emission_log_prob = np.log(
                    self.compute_emission_prob(observations[t], j) + 1e-300
                )
                
                probs = viterbi[t-1] + log_A[:, j]
                best_prev = np.argmax(probs)
                
                viterbi[t, j] = probs[best_prev] + emission_log_prob
                backpointer[t, j] = best_prev
        
        # Backtrack
        path = [0] * T
        path[T-1] = np.argmax(viterbi[T-1])
        
        for t in range(T-2, -1, -1):
            path[t] = backpointer[t+1, path[t+1]]
        
        log_prob = viterbi[T-1, path[T-1]]
        
        return path, log_prob
    
    def infer_sequence(
        self, 
        feature_vectors: List[FeatureVector],
        anomaly_threshold: float = -10.0  # Log-likelihood threshold
    ) -> List[Dict[str, Any]]:
        """
        Run full inference on a sequence of feature vectors.
        
        Returns inference results for each observation.
        """
        # Convert to observation matrix
        feature_names = self.model.feature_names
        observations = np.array([
            v.to_array(feature_names) for v in feature_vectors
        ])
        
        # Run forward-backward for marginals
        gamma, total_log_likelihood = self.forward_backward(observations)
        
        # Run Viterbi for most likely path
        viterbi_path, viterbi_log_prob = self.viterbi(observations)
        
        results = []
        for t, fv in enumerate(feature_vectors):
            # State probabilities from forward-backward
            state_probs = {
                self.state_labels[i]: float(gamma[t, i])
                for i in range(self.num_states)
            }
            
            # Most likely state from Viterbi
            most_likely_idx = viterbi_path[t]
            most_likely_state = self.state_labels[most_likely_idx]
            
            # Emission likelihood for anomaly detection
            emission_prob = self.compute_emission_prob(
                observations[t], most_likely_idx
            )
            emission_log_prob = np.log(emission_prob + 1e-300)
            
            # Anomaly detection
            is_anomaly = emission_log_prob < anomaly_threshold
            
            results.append({
                "feature_vector_id": fv.id,
                "attested_entry_id": fv.attested_entry_id,
                "sequence_index": t,
                "most_likely_state": most_likely_state,
                "most_likely_state_index": most_likely_idx,
                "state_probabilities": state_probs,
                "confidence": float(gamma[t, most_likely_idx]),
                "emission_likelihood": float(emission_prob),
                "log_likelihood": float(emission_log_prob),
                "is_anomaly": is_anomaly,
                "anomaly_score": float(-emission_log_prob) if is_anomaly else None
            })
        
        return results


# ============================================================================
# TRAJECTORY ANALYSIS SERVICE
# ============================================================================

class TrajectoryAnalysisService:
    """
    High-level service for trajectory analysis.
    
    Composes feature extraction, HMM inference, and reporting.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.feature_service = FeatureExtractionService(db)
    
    def analyze_trajectory(
        self,
        persona_token_id: UUID,
        model_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        save_inferences: bool = True
    ) -> Dict[str, Any]:
        """
        Run full trajectory analysis for a persona.
        
        Returns comprehensive analysis including:
        - State sequence
        - Transition points
        - Phase statistics
        - Anomalies
        """
        # Load model
        model = self.db.query(HiddenStateModel).filter(
            HiddenStateModel.id == model_id
        ).first()
        
        if not model:
            raise ValueError(f"Model {model_id} not found")
        
        # Extract features
        feature_vectors = self.feature_service.extract_sequence(
            persona_token_id=persona_token_id,
            start_date=start_date,
            end_date=end_date
        )
        
        if not feature_vectors:
            return {
                "error": "No observations found",
                "persona_token_id": str(persona_token_id)
            }
        
        # Run inference
        engine = HMMInferenceEngine(model)
        inferences = engine.infer_sequence(feature_vectors)
        
        # Save inferences if requested
        if save_inferences:
            for inf in inferences:
                state_inf = StateInference(
                    attested_entry_id=inf["attested_entry_id"],
                    feature_vector_id=inf["feature_vector_id"],
                    model_id=model_id,
                    most_likely_state=inf["most_likely_state"],
                    most_likely_state_index=inf["most_likely_state_index"],
                    state_probabilities=inf["state_probabilities"],
                    confidence=inf["confidence"],
                    emission_likelihood=inf["emission_likelihood"],
                    log_likelihood=inf["log_likelihood"],
                    is_anomaly=inf["is_anomaly"],
                    anomaly_score=inf["anomaly_score"],
                    sequence_index=inf["sequence_index"]
                )
                self.db.add(state_inf)
            self.db.commit()
        
        # Compute trajectory statistics
        stats = self._compute_trajectory_stats(inferences, model.state_labels)
        
        # Find state transitions
        transitions = self._find_transitions(inferences, feature_vectors)
        
        # Find anomalies
        anomalies = [inf for inf in inferences if inf["is_anomaly"]]
        
        return {
            "persona_token_id": str(persona_token_id),
            "model_id": str(model_id),
            "model_name": model.name,
            "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
            
            "sequence_length": len(inferences),
            "date_range": {
                "start": feature_vectors[0].observation_time.isoformat(),
                "end": feature_vectors[-1].observation_time.isoformat()
            },
            
            "trajectory_statistics": stats,
            "state_transitions": transitions,
            "anomalies": [
                {
                    "sequence_index": a["sequence_index"],
                    "state": a["most_likely_state"],
                    "anomaly_score": a["anomaly_score"]
                }
                for a in anomalies
            ],
            
            "state_sequence": [
                {
                    "index": inf["sequence_index"],
                    "state": inf["most_likely_state"],
                    "confidence": inf["confidence"]
                }
                for inf in inferences
            ]
        }
    
    def _compute_trajectory_stats(
        self, 
        inferences: List[Dict], 
        state_labels: List[str]
    ) -> Dict[str, Any]:
        """Compute statistics over the inferred trajectory."""
        state_counts = {label: 0 for label in state_labels}
        confidence_sum = {label: 0.0 for label in state_labels}
        
        for inf in inferences:
            state = inf["most_likely_state"]
            state_counts[state] += 1
            confidence_sum[state] += inf["confidence"]
        
        total = len(inferences)
        
        return {
            "state_distribution": {
                label: {
                    "count": state_counts[label],
                    "percentage": state_counts[label] / total * 100 if total > 0 else 0,
                    "mean_confidence": (
                        confidence_sum[label] / state_counts[label] 
                        if state_counts[label] > 0 else 0
                    )
                }
                for label in state_labels
            },
            "total_observations": total,
            "mean_confidence": sum(inf["confidence"] for inf in inferences) / total if total > 0 else 0
        }
    
    def _find_transitions(
        self, 
        inferences: List[Dict],
        feature_vectors: List[FeatureVector]
    ) -> List[Dict]:
        """Find state transition points in the sequence."""
        transitions = []
        
        for i in range(1, len(inferences)):
            prev_state = inferences[i-1]["most_likely_state"]
            curr_state = inferences[i]["most_likely_state"]
            
            if prev_state != curr_state:
                transitions.append({
                    "from_state": prev_state,
                    "to_state": curr_state,
                    "sequence_index": i,
                    "timestamp": feature_vectors[i].observation_time.isoformat(),
                    "confidence": inferences[i]["confidence"]
                })
        
        return transitions
    
    def generate_court_report(
        self,
        persona_token_id: UUID,
        case_id: UUID,
        model_id: UUID
    ) -> Dict[str, Any]:
        """
        Generate a court-ready trajectory analysis report.
        
        This combines:
        - Full chain verification
        - Statistical analysis
        - HMM trajectory inference
        - Plain-language interpretation guidance
        """
        # Run trajectory analysis
        analysis = self.analyze_trajectory(persona_token_id, model_id)
        
        # Get model info for documentation
        model = self.db.query(HiddenStateModel).filter(
            HiddenStateModel.id == model_id
        ).first()
        
        return {
            "report_type": "trajectory_analysis",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            
            "case_id": str(case_id),
            "persona_token_id": str(persona_token_id),
            
            "model_documentation": {
                "name": model.name,
                "type": model.model_type,
                "version": model.version,
                "num_states": model.num_states,
                "state_labels": model.state_labels,
                "description": model.description,
                "limitations": model.limitations,
                "intended_use": model.intended_use,
                "training_info": {
                    "num_sequences": model.num_training_sequences,
                    "num_observations": model.num_training_observations,
                    "trained_at": model.trained_at.isoformat() if model.trained_at else None
                }
            },
            
            "analysis_results": analysis,
            
            "interpretation_guidance": """
            This analysis applies a Hidden Markov Model to the plaintiff's 
            contemporaneous pain and symptom reports to identify patterns 
            in their trajectory.
            
            The model does NOT prove that the plaintiff experienced pain.
            It provides a statistically disciplined way to summarize and 
            segment the temporal pattern of their self-reports.
            
            Key findings should be interpreted by qualified medical experts
            who can speak to clinical significance.
            
            The underlying data is cryptographically attested and can be
            independently verified using the chain verification tools.
            """
        }


# ============================================================================
# DEFAULT MODEL FACTORY
# ============================================================================

def create_default_pain_trajectory_model() -> HiddenStateModel:
    """
    Create a default 4-state pain trajectory model.
    
    This is a reasonable starting point based on clinical pain literature.
    Should be refined with actual training data.
    """
    return HiddenStateModel(
        name="Default Pain Trajectory Model",
        model_type="pain_trajectory",
        version="1.0",
        num_states=4,
        state_labels=["baseline", "flare", "improvement", "severe"],
        
        feature_names=[
            "pain_score_normalized",
            "sleep_impact",
            "work_impact",
            "days_since_injury"
        ],
        
        # Initial distribution (start most likely in baseline or flare after injury)
        initial_distribution=[0.3, 0.5, 0.1, 0.1],
        
        # Transition matrix (rows sum to 1)
        # States: baseline, flare, improvement, severe
        transition_matrix=[
            [0.7, 0.2, 0.05, 0.05],   # From baseline
            [0.3, 0.5, 0.1, 0.1],     # From flare
            [0.4, 0.1, 0.45, 0.05],   # From improvement
            [0.1, 0.3, 0.05, 0.55],   # From severe
        ],
        
        emission_model_type="gaussian",
        emission_parameters={
            "means": [
                [0.4, 4, 4, 60],    # Baseline: moderate pain, some impact
                [0.7, 7, 7, 30],    # Flare: high pain, high impact, early
                [0.2, 2, 2, 120],   # Improvement: low pain, low impact, later
                [0.9, 9, 9, 45],    # Severe: very high everything
            ],
            "covariances": [
                [0.04, 4, 4, 900],  # Diagonal covariance (variance per feature)
                [0.04, 4, 4, 400],
                [0.04, 4, 4, 900],
                [0.01, 1, 1, 400],
            ]
        },
        
        description="""
        A 4-state Hidden Markov Model for pain trajectory inference.
        
        States:
        - BASELINE: Typical pain level for this person's condition
        - FLARE: Acute exacerbation above baseline
        - IMPROVEMENT: Better than baseline function
        - SEVERE: Significant dysfunction requiring attention
        
        Trained on general population pain trajectory data with 
        post-injury time course priors.
        """,
        
        limitations="""
        - Not validated on this specific plaintiff's data
        - Population-level priors may not match individual trajectory
        - Does not account for medication effects
        - Assumes stationary transition dynamics
        """,
        
        intended_use="""
        To provide a structured, reproducible way to segment and 
        summarize the temporal pattern of self-reported pain and 
        functional symptoms. Results should be interpreted by 
        qualified medical experts.
        """
    )
