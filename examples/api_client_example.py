"""
API Client Example

Demonstrates how to interact with the Phenomenological Evidence System API
using Python requests library.

Prerequisites:
- Server running (make run or docker-compose up)
- Database initialized (make migrate)

Usage:
    python examples/api_client_example.py
"""

import requests
from uuid import uuid4
from datetime import datetime


# =============================================================================
# CONFIGURATION
# =============================================================================

API_BASE_URL = "http://localhost:8000/api/v1"


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def check_health():
    """Check if the API is healthy."""
    response = requests.get("http://localhost:8000/health")
    if response.status_code == 200:
        print("✓ API is healthy")
        print(f"  Version: {response.json()['version']}")
        return True
    else:
        print("✗ API is not responding")
        return False


def create_party(name: str, email: str, role: str = "plaintiff"):
    """Create a party (plaintiff, defendant, etc.)."""
    payload = {
        "name": name,
        "email": email,
        "role": role,
    }

    response = requests.post(f"{API_BASE_URL}/parties", json=payload)

    if response.status_code == 201:
        party = response.json()
        print(f"✓ Created party: {party['name']} ({party['id']})")
        return party
    else:
        print(f"✗ Failed to create party: {response.status_code}")
        print(f"  {response.text}")
        return None


def submit_pain_state(party_id: str, value: float, location: str = None, quality: str = None):
    """Submit a pain state report."""
    payload = {
        "party_id": party_id,
        "value": value,
        "scale_type": "0-10",
    }

    if location:
        payload["location"] = location
    if quality:
        payload["quality"] = quality

    response = requests.post(f"{API_BASE_URL}/phenomenology/pain", json=payload)

    if response.status_code == 201:
        result = response.json()
        print(f"✓ Submitted pain state: {value}/10 {location or ''}")
        print(f"  Attestation ID: {result['attestation_id']}")
        return result
    else:
        print(f"✗ Failed to submit pain state: {response.status_code}")
        print(f"  {response.text}")
        return None


def submit_perspective_note(party_id: str, text: str):
    """Submit a perspective note (subjective narrative)."""
    payload = {
        "party_id": party_id,
        "text": text,
    }

    response = requests.post(f"{API_BASE_URL}/phenomenology/perspective", json=payload)

    if response.status_code == 201:
        result = response.json()
        print(f"✓ Submitted perspective note")
        print(f"  Attestation ID: {result['attestation_id']}")
        return result
    else:
        print(f"✗ Failed to submit perspective note: {response.status_code}")
        return None


def get_attestation_proof(attestation_id: str):
    """Retrieve attestation proof for verification."""
    response = requests.get(f"{API_BASE_URL}/phenomenology/attestation/{attestation_id}")

    if response.status_code == 200:
        proof = response.json()
        print(f"✓ Retrieved attestation proof")
        print(f"  Entry hash: {proof['entry_hash'][:16]}...")
        print(f"  Chain index: {proof['chain_index']}")
        return proof
    else:
        print(f"✗ Failed to retrieve proof: {response.status_code}")
        return None


# =============================================================================
# MAIN EXAMPLE
# =============================================================================

def main():
    """Run the example workflow."""
    print("=" * 70)
    print("Phenomenological Evidence System - API Client Example")
    print("=" * 70)
    print()

    # Step 1: Check API health
    print("Step 1: Checking API health...")
    if not check_health():
        print("Error: API is not available. Please start the server.")
        return
    print()

    # Step 2: Create a party (plaintiff)
    print("Step 2: Creating a plaintiff...")
    party = create_party(
        name="Jane Doe",
        email="jane.doe@example.com",
        role="plaintiff"
    )
    if not party:
        return
    party_id = party["id"]
    print()

    # Step 3: Submit pain states
    print("Step 3: Submitting pain states...")
    submit_pain_state(
        party_id=party_id,
        value=7.0,
        location="neck",
        quality="burning"
    )
    submit_pain_state(
        party_id=party_id,
        value=8.5,
        location="lower back",
        quality="sharp"
    )
    print()

    # Step 4: Submit perspective note
    print("Step 4: Submitting perspective note...")
    submit_perspective_note(
        party_id=party_id,
        text="Woke up at 3am with severe neck pain. Can't turn my head to the right. "
             "Pain radiates down my right arm. Took ibuprofen but no relief yet."
    )
    print()

    # Step 5: Retrieve attestation proof
    print("Step 5: Retrieving attestation proof...")
    # Note: You'd need to store the attestation_id from previous calls
    # This is just an example of how to retrieve it
    print("(Use attestation_id from previous submissions)")
    print()

    print("=" * 70)
    print("Example completed successfully!")
    print("=" * 70)


if __name__ == "__main__":
    main()
