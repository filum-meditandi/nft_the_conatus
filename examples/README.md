# Usage Examples

This directory contains example scripts demonstrating how to use the Phenomenological Evidence System.

## Examples

### 1. SMS Flow Example (`sms_flow_example.py`)
Demonstrates how a single SMS becomes a cryptographically attested entry:
- Parse SMS: "PAIN 7 neck burning, can't sleep"
- Extract structured data
- Create attestation entry
- Link to evidence and facts

### 2. API Client Example (`api_client_example.py`)
Shows how to interact with the API programmatically:
- Submit pain states
- Submit perspective notes
- Retrieve attestation proofs
- Verify chain integrity

### 3. Encryption Example (`encryption_example.py`)
Demonstrates PHI separation and encryption:
- Encrypt subjective notes
- Generate normalized projections
- Key wrapping and rotation
- Decrypt with proper keys

### 4. Chain Verification Example (`chain_verification_example.py`)
Shows how to verify attestation chain integrity:
- Retrieve chain entries
- Verify hash links
- Check signatures
- Detect tampering

## Running Examples

```bash
# Make sure you're in the project root
cd /path/to/nft_the_conatus

# Install dependencies
pip install -e .

# Set up environment
cp .env.example .env
# Edit .env with your settings

# Run an example
python examples/api_client_example.py
```

## API Examples with curl

See `curl_examples.md` for examples using curl to interact with the API.
