# API Examples with curl

Examples of interacting with the Phenomenological Evidence System using curl.

## Health Check

```bash
# Check API health
curl http://localhost:8000/health

# Expected response:
# {
#   "status": "healthy",
#   "version": "0.1.0",
#   "environment": "development",
#   "database": "connected"
# }
```

## Create a Party

```bash
# Create a plaintiff
curl -X POST http://localhost:8000/api/v1/parties \
  -H "Content-Type: application/json" \
  -d '{
    "name": "John Doe",
    "email": "john.doe@example.com",
    "role": "plaintiff"
  }'

# Expected response:
# {
#   "id": "550e8400-e29b-41d4-a716-446655440000",
#   "name": "John Doe",
#   "email": "john.doe@example.com",
#   "role": "plaintiff",
#   "created_at": "2024-01-15T10:30:00Z"
# }
```

## Submit Pain State

```bash
# Submit a pain report
PARTY_ID="550e8400-e29b-41d4-a716-446655440000"  # Replace with actual party ID

curl -X POST http://localhost:8000/api/v1/phenomenology/pain \
  -H "Content-Type: application/json" \
  -d "{
    \"party_id\": \"$PARTY_ID\",
    \"value\": 7.5,
    \"scale_type\": \"0-10\",
    \"location\": \"neck\",
    \"quality\": \"burning\",
    \"functional_impact\": {
      \"sleep_disruption\": true,
      \"work_limitation\": true
    }
  }"

# Expected response:
# {
#   "id": "...",
#   "attestation_id": "...",
#   "entry_hash": "...",
#   "chain_index": 0,
#   "created_at": "..."
# }
```

## Submit Perspective Note

```bash
# Submit a subjective narrative
curl -X POST http://localhost:8000/api/v1/phenomenology/perspective \
  -H "Content-Type: application/json" \
  -d "{
    \"party_id\": \"$PARTY_ID\",
    \"text\": \"Woke up at 3am with severe neck pain. Can't turn my head. Pain radiates down right arm.\",
    \"valence\": \"negative\"
  }"
```

## Retrieve Attestation Proof

```bash
# Get attestation proof for verification
ATTESTATION_ID="..."  # From previous response

curl http://localhost:8000/api/v1/phenomenology/attestation/$ATTESTATION_ID

# Expected response:
# {
#   "id": "...",
#   "entry_hash": "...",
#   "previous_hash": "...",
#   "payload_hash": "...",
#   "chain_index": 0,
#   "signature": "...",
#   "verified_at": "...",
#   "payload": { ... }
# }
```

## Verify Chain Integrity

```bash
# Verify entire chain for a persona
PERSONA_ID="..."  # Persona token ID

curl http://localhost:8000/api/v1/phenomenology/verify/$PERSONA_ID

# Expected response:
# {
#   "is_valid": true,
#   "chain_length": 10,
#   "first_entry": "...",
#   "last_entry": "...",
#   "verified_at": "..."
# }
```

## SMS Webhook (Twilio)

```bash
# Simulate Twilio inbound SMS webhook
curl -X POST http://localhost:8000/api/v1/twilio/inbound \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "From=%2B15551234567" \
  -d "Body=PAIN%207%20neck%20burning" \
  -d "MessageSid=SM1234567890"

# Expected response: TwiML
# <?xml version="1.0" encoding="UTF-8"?>
# <Response>
#   <Message>Pain report recorded: 7/10 neck. Attestation created.</Message>
# </Response>
```

## Get NFT Proof Payload

```bash
# Generate NFT-ready proof bundle
PERSONA_ID="..."

curl http://localhost:8000/api/v1/phenomenology/nft/$PERSONA_ID

# Expected response:
# {
#   "version": "1.0",
#   "chain_summary": { ... },
#   "trajectory": { ... },
#   "statistics": { ... },
#   "cryptographic_proof": { ... }
# }
```

## Pagination Example

```bash
# Get pain states with pagination
curl "http://localhost:8000/api/v1/phenomenology/pain?party_id=$PARTY_ID&limit=10&offset=0"

# Get next page
curl "http://localhost:8000/api/v1/phenomenology/pain?party_id=$PARTY_ID&limit=10&offset=10"
```

## Error Handling

```bash
# Invalid pain value (should fail validation)
curl -X POST http://localhost:8000/api/v1/phenomenology/pain \
  -H "Content-Type: application/json" \
  -d "{
    \"party_id\": \"$PARTY_ID\",
    \"value\": 15.0
  }"

# Expected response: 422 Unprocessable Entity
# {
#   "detail": [
#     {
#       "loc": ["body", "value"],
#       "msg": "ensure this value is less than or equal to 10",
#       "type": "value_error.number.not_le"
#     }
#   ]
# }
```

## Authentication (if enabled)

```bash
# Get JWT token
curl -X POST http://localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{
    "username": "user@example.com",
    "password": "secret"
  }'

# Use token in requests
TOKEN="eyJ..."

curl http://localhost:8000/api/v1/phenomenology/pain \
  -H "Authorization: Bearer $TOKEN"
```

## Tips

- **Pretty print JSON**: Add `| jq` to curl commands (requires jq installed)
- **Save response**: Add `-o response.json` to save output
- **Verbose mode**: Add `-v` to see request/response headers
- **Timing**: Add `-w "@curl-timing.txt"` to measure response time

Example with jq:
```bash
curl http://localhost:8000/health | jq .
```
