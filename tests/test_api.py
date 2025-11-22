"""
API endpoint tests
"""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.api
class TestHealthEndpoints:
    """Test health check and monitoring endpoints."""

    def test_health_check(self, client: TestClient):
        """Test /health endpoint."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "version" in data
        assert "database" in data

    def test_root_endpoint(self, client: TestClient):
        """Test root endpoint."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data


@pytest.mark.api
@pytest.mark.skip(reason="Implement API tests")
class TestPhenomenologyEndpoints:
    """Test phenomenology data submission endpoints."""

    def test_submit_pain_state(self, client: TestClient):
        """Test submitting a pain state."""
        # TODO: Implement pain state submission test
        pass

    def test_submit_perspective_note(self, client: TestClient):
        """Test submitting a perspective note."""
        # TODO: Implement perspective note submission test
        pass

    def test_get_attestation_proof(self, client: TestClient):
        """Test retrieving attestation proof."""
        # TODO: Implement attestation proof retrieval test
        pass


@pytest.mark.api
@pytest.mark.skip(reason="Implement SMS tests")
class TestTwilioEndpoints:
    """Test Twilio SMS webhook endpoints."""

    def test_inbound_sms(self, client: TestClient):
        """Test receiving inbound SMS."""
        # TODO: Implement inbound SMS test
        pass

    def test_parse_pain_sms(self, client: TestClient):
        """Test parsing pain report SMS."""
        # TODO: Implement SMS parsing test
        pass
