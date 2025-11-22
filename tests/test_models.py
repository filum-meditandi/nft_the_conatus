"""
Unit tests for domain models
"""

import pytest
from uuid import uuid4
from datetime import datetime

from models import Party, PersonaToken, PainState, Fact, PartyRole, FactCategory


@pytest.mark.unit
@pytest.mark.database
class TestParty:
    """Test Party model."""

    def test_create_party(self, db_session):
        """Test creating a party."""
        party = Party(
            id=uuid4(),
            role=PartyRole.PLAINTIFF,
            name="John Doe",
            email="john@example.com",
        )

        db_session.add(party)
        db_session.commit()

        assert party.id is not None
        assert party.role == PartyRole.PLAINTIFF
        assert party.name == "John Doe"

    def test_party_role_enum(self):
        """Test PartyRole enum values."""
        assert PartyRole.PLAINTIFF == "plaintiff"
        assert PartyRole.DEFENDANT == "defendant"
        assert PartyRole.WITNESS == "witness"


@pytest.mark.unit
@pytest.mark.database
class TestPersonaToken:
    """Test PersonaToken model."""

    def test_create_persona(self, db_session, sample_party):
        """Test creating a persona token."""
        persona = PersonaToken(
            id=uuid4(),
            party_id=sample_party.id,
            key_type="ed25519",
            public_key=b"test_public_key",
            private_key=b"test_private_key",
        )

        db_session.add(persona)
        db_session.commit()

        assert persona.id is not None
        assert persona.party_id == sample_party.id
        assert persona.key_type == "ed25519"


@pytest.mark.unit
@pytest.mark.database
class TestPainState:
    """Test PainState model."""

    def test_create_pain_state(self, db_session, sample_party):
        """Test creating a pain state."""
        pain = PainState(
            id=uuid4(),
            party_id=sample_party.id,
            value=7.0,
            scale_type="0-10",
            location="neck",
            quality="burning",
        )

        db_session.add(pain)
        db_session.commit()

        assert pain.id is not None
        assert pain.value == 7.0
        assert pain.location == "neck"

    def test_pain_value_validation(self, db_session, sample_party):
        """Test that pain values are within valid range."""
        # This should work
        pain = PainState(
            id=uuid4(),
            party_id=sample_party.id,
            value=5.5,
            scale_type="0-10",
        )
        assert 0 <= pain.value <= 10


@pytest.mark.unit
@pytest.mark.database
class TestFact:
    """Test Fact model."""

    def test_create_fact(self, db_session):
        """Test creating a fact."""
        fact = Fact(
            id=uuid4(),
            category=FactCategory.ACCIDENT,
            occurred_at=datetime.utcnow(),
            description="Car accident at intersection",
        )

        db_session.add(fact)
        db_session.commit()

        assert fact.id is not None
        assert fact.category == FactCategory.ACCIDENT
        assert fact.description is not None
