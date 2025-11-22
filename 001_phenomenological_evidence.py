"""
Phenomenological Evidence Schema Migration

This migration creates the tables for:
- Party & PersonaToken (legal actors and their cryptographic identity)
- Fact & EvidenceItem & FactEvidenceLink (evidentiary graph)
- PerspectiveNote & PainState (lived experience data)
- Duty & Breach & CausalLink (legal structure)
- AttestedEntry (cryptographic attestation chain)

Revision ID: 001_phenomenological_evidence
Revises: <your previous migration>
Create Date: 2024-03-16
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '001_phenomenological_evidence'
down_revision = None  # Update this to your latest migration
branch_labels = None
depends_on = None


def upgrade():
    # ========================================================================
    # PARTY & PERSONA
    # ========================================================================
    
    op.create_table(
        'parties',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('legal_name', sa.String(255), nullable=False),
        sa.Column('role', sa.String(32), nullable=False),  # PartyRole enum
        sa.Column('observer_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('case_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )
    op.create_index('ix_parties_case_id', 'parties', ['case_id'])
    op.create_index('ix_parties_role', 'parties', ['role'])
    
    op.create_table(
        'persona_tokens',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('party_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('parties.id'), nullable=False),
        sa.Column('nft_id', sa.String(255), nullable=True),
        sa.Column('contract_address', sa.String(255), nullable=True),
        sa.Column('chain_id', sa.Integer, nullable=True),
        sa.Column('metadata_uri', sa.String(512), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_persona_tokens_party_id', 'persona_tokens', ['party_id'], unique=True)
    
    # ========================================================================
    # FACTS & EVIDENCE
    # ========================================================================
    
    op.create_table(
        'facts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('party_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('parties.id'), nullable=True),
        sa.Column('case_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('category', sa.String(32), nullable=False),  # FactCategory enum
        sa.Column('statement', sa.Text, nullable=False),
        sa.Column('is_objective', sa.Boolean, default=True),
        sa.Column('created_by_party_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('parties.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )
    op.create_index('ix_facts_case_id', 'facts', ['case_id'])
    op.create_index('ix_facts_category', 'facts', ['category'])
    op.create_index('ix_facts_occurred_at', 'facts', ['occurred_at'])
    
    op.create_table(
        'evidence_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('case_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('source_type', sa.String(32), nullable=False),  # EvidenceSourceType enum
        sa.Column('uri', sa.String(1024), nullable=False),
        sa.Column('content_hash', sa.String(128), nullable=False),
        sa.Column('hash_algorithm', sa.String(32), default='sha256'),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('original_filename', sa.String(255), nullable=True),
        sa.Column('mime_type', sa.String(128), nullable=True),
        sa.Column('file_size_bytes', sa.Integer, nullable=True),
        sa.Column('document_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_evidence_items_case_id', 'evidence_items', ['case_id'])
    op.create_index('ix_evidence_items_content_hash', 'evidence_items', ['content_hash'])
    
    op.create_table(
        'fact_evidence_links',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('fact_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('facts.id'), nullable=False),
        sa.Column('evidence_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('evidence_items.id'), nullable=False),
        sa.Column('role', sa.String(32), nullable=False, default='supports'),  # LinkRole enum
        sa.Column('confidence', sa.Float, nullable=True),
        sa.Column('assessed_by', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_fact_evidence_links_fact_id', 'fact_evidence_links', ['fact_id'])
    op.create_index('ix_fact_evidence_links_evidence_id', 'fact_evidence_links', ['evidence_id'])
    
    # ========================================================================
    # PERSPECTIVE: PAIN & NARRATIVE
    # ========================================================================
    
    op.create_table(
        'perspective_notes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('party_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('parties.id'), nullable=False),
        sa.Column('fact_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('facts.id'), nullable=True),
        sa.Column('attention_event_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('title', sa.String(255), nullable=True),
        sa.Column('body', sa.Text, nullable=False),
        sa.Column('valence', sa.String(32), nullable=True),  # Valence enum
        sa.Column('meaning_tags', postgresql.JSON, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )
    op.create_index('ix_perspective_notes_party_id', 'perspective_notes', ['party_id'])
    op.create_index('ix_perspective_notes_fact_id', 'perspective_notes', ['fact_id'])
    op.create_index('ix_perspective_notes_created_at', 'perspective_notes', ['created_at'])
    
    op.create_table(
        'pain_states',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('party_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('parties.id'), nullable=False),
        sa.Column('fact_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('facts.id'), nullable=True),
        sa.Column('attention_event_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('scale_type', sa.String(32), default='0-10'),
        sa.Column('value', sa.Float, nullable=False),
        sa.Column('location', sa.String(128), nullable=True),
        sa.Column('quality', sa.String(128), nullable=True),
        sa.Column('functional_impact', postgresql.JSON, nullable=True),
        sa.Column('source', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_pain_states_party_id', 'pain_states', ['party_id'])
    op.create_index('ix_pain_states_recorded_at', 'pain_states', ['recorded_at'])
    
    # ========================================================================
    # LEGAL STRUCTURE
    # ========================================================================
    
    op.create_table(
        'duties',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('party_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('parties.id'), nullable=False),
        sa.Column('case_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('description', sa.Text, nullable=False),
        sa.Column('legal_basis', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_duties_case_id', 'duties', ['case_id'])
    
    op.create_table(
        'breaches',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('duty_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('duties.id'), nullable=False),
        sa.Column('fact_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('facts.id'), nullable=True),
        sa.Column('description', sa.Text, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_breaches_duty_id', 'breaches', ['duty_id'])
    
    op.create_table(
        'causal_links',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('breach_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('breaches.id'), nullable=False),
        sa.Column('harm_fact_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('facts.id'), nullable=False),
        sa.Column('theory', sa.String(32), nullable=False, default='but_for'),  # CausationTheory enum
        sa.Column('strength', sa.Float, nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_causal_links_breach_id', 'causal_links', ['breach_id'])
    op.create_index('ix_causal_links_harm_fact_id', 'causal_links', ['harm_fact_id'])
    
    # ========================================================================
    # ATTESTATION LEDGER
    # ========================================================================
    
    op.create_table(
        'attested_entries',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('persona_token_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('persona_tokens.id'), nullable=False),
        sa.Column('domain_table', sa.String(64), nullable=False),
        sa.Column('domain_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('payload_hash', sa.String(128), nullable=False),
        sa.Column('prev_hash', sa.String(128), nullable=True),
        sa.Column('entry_hash', sa.String(128), nullable=False),
        sa.Column('sequence_number', sa.Integer, nullable=False),
        sa.Column('signature', sa.Text, nullable=True),
        sa.Column('signer_key_id', sa.String(255), nullable=True),
        sa.Column('chain_anchor_tx', sa.String(255), nullable=True),
        sa.Column('chain_anchor_block', sa.Integer, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_attested_entries_persona_token_id', 'attested_entries', ['persona_token_id'])
    op.create_index('ix_attested_entries_sequence', 'attested_entries', ['persona_token_id', 'sequence_number'], unique=True)
    op.create_index('ix_attested_entries_domain', 'attested_entries', ['domain_table', 'domain_id'])
    op.create_index('ix_attested_entries_entry_hash', 'attested_entries', ['entry_hash'])


def downgrade():
    op.drop_table('attested_entries')
    op.drop_table('causal_links')
    op.drop_table('breaches')
    op.drop_table('duties')
    op.drop_table('pain_states')
    op.drop_table('perspective_notes')
    op.drop_table('fact_evidence_links')
    op.drop_table('evidence_items')
    op.drop_table('facts')
    op.drop_table('persona_tokens')
    op.drop_table('parties')
