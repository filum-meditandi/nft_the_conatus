"""
Comprehensive Phenomenological Evidence Schema Migration

This migration creates ALL tables for the complete system:
- Core models (Party, Fact, Evidence, Pain, Perspective)
- PHI separation (SubjectiveNote, EncryptionKey)
- Signing infrastructure (SigningKey)
- Context layer (ContextSnapshot, CaseTimeline)
- HMM layer (FeatureVector, HiddenStateModel, StateInference)
- Attestation (AttestedEntry, PersonaToken)

Revision ID: 002_complete_schema
Revises: 001_phenomenological_evidence
Create Date: 2024-03-16
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '002_complete_schema'
down_revision = '001_phenomenological_evidence'
branch_labels = None
depends_on = None


def upgrade():
    # ========================================================================
    # ENCRYPTION KEYS (for PHI separation)
    # ========================================================================
    
    op.create_table(
        'encryption_keys',
        sa.Column('id', sa.String(128), primary_key=True),
        sa.Column('wrapped_key', sa.LargeBinary, nullable=False),
        sa.Column('algorithm', sa.String(32), default='AES-256-GCM'),
        sa.Column('key_type', sa.String(32), default='data_encryption_key'),
        sa.Column('persona_token_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('persona_tokens.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('rotated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean, default=True),
    )
    op.create_index('ix_encryption_keys_persona', 'encryption_keys', ['persona_token_id'])
    
    # ========================================================================
    # SUBJECTIVE NOTES (encrypted PHI)
    # ========================================================================
    
    op.create_table(
        'subjective_notes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('persona_token_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('persona_tokens.id'), nullable=False),
        sa.Column('ciphertext', sa.LargeBinary, nullable=False),
        sa.Column('encryption_key_id', sa.String(128),
                  sa.ForeignKey('encryption_keys.id'), nullable=False),
        sa.Column('iv', sa.LargeBinary, nullable=True),
        sa.Column('note_type', sa.String(32), default='general'),
        sa.Column('normalized_summary', sa.Text, nullable=True),
        sa.Column('symptom_tags', postgresql.JSONB, nullable=True),
        sa.Column('severity_level', sa.Integer, nullable=True),
        sa.Column('plaintext_hash', sa.String(64), nullable=False),
        sa.Column('event_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('last_decrypted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('decryption_count', sa.Integer, default=0),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_subjective_notes_persona', 'subjective_notes', ['persona_token_id'])
    op.create_index('ix_subjective_notes_recorded', 'subjective_notes', ['recorded_at'])
    
    # ========================================================================
    # SIGNING KEYS
    # ========================================================================
    
    op.create_table(
        'signing_keys',
        sa.Column('id', sa.String(128), primary_key=True),
        sa.Column('persona_token_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('persona_tokens.id'), nullable=True),
        sa.Column('public_key_pem', sa.Text, nullable=False),
        sa.Column('public_key_jwk', postgresql.JSONB, nullable=True),
        sa.Column('algorithm', sa.String(32), nullable=False),
        sa.Column('purpose', sa.String(32), default='attestation'),
        sa.Column('is_server_managed', sa.Boolean, default=False),
        sa.Column('trust_level', sa.Integer, default=1),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('device_info', postgresql.JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('activated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revocation_reason', sa.Text, nullable=True),
    )
    op.create_index('ix_signing_keys_persona', 'signing_keys', ['persona_token_id'])
    
    # ========================================================================
    # CASE TIMELINES
    # ========================================================================
    
    op.create_table(
        'case_timelines',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('case_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('injury_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('first_treatment_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('surgery_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('mmi_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('litigation_start_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('acute_end_days', sa.Integer, default=42),
        sa.Column('subacute_end_days', sa.Integer, default=90),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_case_timelines_case', 'case_timelines', ['case_id'], unique=True)
    
    # ========================================================================
    # CONTEXT SNAPSHOTS
    # ========================================================================
    
    op.create_table(
        'context_snapshots',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('attested_entry_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('attested_entries.id'), nullable=False, unique=True),
        sa.Column('event_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('case_phase', sa.String(32), nullable=True),
        sa.Column('days_since_injury', sa.Integer, nullable=True),
        sa.Column('location_type', sa.String(32), nullable=True),
        sa.Column('location_city', sa.String(128), nullable=True),
        sa.Column('location_state', sa.String(64), nullable=True),
        sa.Column('timezone_name', sa.String(64), nullable=True),
        sa.Column('posture', sa.String(32), nullable=True),
        sa.Column('exertion_level', sa.String(32), nullable=True),
        sa.Column('environment_tags', postgresql.JSONB, nullable=True),
        sa.Column('activity_description', sa.String(255), nullable=True),
        sa.Column('recent_treatment_type', sa.String(64), nullable=True),
        sa.Column('hours_since_treatment', sa.Float, nullable=True),
        sa.Column('medication_context', sa.String(128), nullable=True),
        sa.Column('raw_context_json', postgresql.JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_context_snapshots_entry', 'context_snapshots', ['attested_entry_id'])
    
    # ========================================================================
    # HIDDEN STATE MODELS (HMM)
    # ========================================================================
    
    op.create_table(
        'hidden_state_models',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('model_type', sa.String(64), nullable=False),
        sa.Column('version', sa.String(32), default='1.0'),
        sa.Column('num_states', sa.Integer, nullable=False),
        sa.Column('state_labels', postgresql.JSONB, nullable=False),
        sa.Column('feature_names', postgresql.JSONB, nullable=False),
        sa.Column('feature_schema_version', sa.String(32), default='1.0'),
        sa.Column('initial_distribution', postgresql.JSONB, nullable=False),
        sa.Column('transition_matrix', postgresql.JSONB, nullable=False),
        sa.Column('emission_model_type', sa.String(32), default='gaussian'),
        sa.Column('emission_parameters', postgresql.JSONB, nullable=False),
        sa.Column('trained_on_personas', postgresql.JSONB, nullable=True),
        sa.Column('trained_on_entries', postgresql.JSONB, nullable=True),
        sa.Column('training_date_range', postgresql.JSONB, nullable=True),
        sa.Column('num_training_sequences', sa.Integer, nullable=True),
        sa.Column('num_training_observations', sa.Integer, nullable=True),
        sa.Column('training_config', postgresql.JSONB, nullable=True),
        sa.Column('training_log_likelihood', sa.Float, nullable=True),
        sa.Column('converged', sa.Boolean, nullable=True),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('limitations', sa.Text, nullable=True),
        sa.Column('intended_use', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('trained_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('validated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean, default=True),
    )
    op.create_index('ix_hidden_state_models_type', 'hidden_state_models', ['model_type'])
    
    # ========================================================================
    # FEATURE VECTORS
    # ========================================================================
    
    op.create_table(
        'feature_vectors',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('attested_entry_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('attested_entries.id'), nullable=False, unique=True),
        sa.Column('persona_token_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('schema_version', sa.String(32), default='1.0'),
        sa.Column('features', postgresql.JSONB, nullable=False),
        sa.Column('missing_mask', postgresql.JSONB, nullable=True),
        sa.Column('extracted_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('extraction_duration_ms', sa.Integer, nullable=True),
        sa.Column('sequence_index', sa.Integer, nullable=False),
        sa.Column('observation_time', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_feature_vectors_entry', 'feature_vectors', ['attested_entry_id'])
    op.create_index('ix_feature_vectors_persona', 'feature_vectors', ['persona_token_id'])
    op.create_index('ix_feature_vectors_time', 'feature_vectors', ['observation_time'])
    
    # ========================================================================
    # STATE INFERENCES
    # ========================================================================
    
    op.create_table(
        'state_inferences',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('attested_entry_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('attested_entries.id'), nullable=False),
        sa.Column('feature_vector_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('feature_vectors.id'), nullable=False),
        sa.Column('model_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('hidden_state_models.id'), nullable=False),
        sa.Column('most_likely_state', sa.String(64), nullable=False),
        sa.Column('most_likely_state_index', sa.Integer, nullable=False),
        sa.Column('state_probabilities', postgresql.JSONB, nullable=False),
        sa.Column('confidence', sa.Float, nullable=False),
        sa.Column('emission_likelihood', sa.Float, nullable=False),
        sa.Column('log_likelihood', sa.Float, nullable=False),
        sa.Column('is_anomaly', sa.Boolean, default=False),
        sa.Column('anomaly_score', sa.Float, nullable=True),
        sa.Column('inferred_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('sequence_index', sa.Integer, nullable=False),
    )
    op.create_index('ix_state_inferences_entry', 'state_inferences', ['attested_entry_id'])
    op.create_index('ix_state_inferences_model', 'state_inferences', ['model_id'])
    
    # ========================================================================
    # PHONE REGISTRY (for Twilio lookups)
    # ========================================================================
    
    op.create_table(
        'phone_registry',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('phone_number', sa.String(32), nullable=False, unique=True),
        sa.Column('party_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('parties.id'), nullable=False),
        sa.Column('persona_token_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('persona_tokens.id'), nullable=False),
        sa.Column('case_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('registered_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('last_message_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_phone_registry_phone', 'phone_registry', ['phone_number'], unique=True)
    op.create_index('ix_phone_registry_party', 'phone_registry', ['party_id'])
    
    # ========================================================================
    # ADD MISSING COLUMNS TO EXISTING TABLES
    # ========================================================================
    
    # Add subjective_note_id to attested_entries for PHI-separated attestations
    op.add_column(
        'attested_entries',
        sa.Column('subjective_note_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('subjective_notes.id'), nullable=True)
    )


def downgrade():
    # Remove new column from attested_entries
    op.drop_column('attested_entries', 'subjective_note_id')
    
    # Drop tables in reverse dependency order
    op.drop_table('phone_registry')
    op.drop_table('state_inferences')
    op.drop_table('feature_vectors')
    op.drop_table('hidden_state_models')
    op.drop_table('context_snapshots')
    op.drop_table('case_timelines')
    op.drop_table('signing_keys')
    op.drop_table('subjective_notes')
    op.drop_table('encryption_keys')
