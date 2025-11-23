# Phenomenological Evidence System

> *Cryptographically verified lived experience documentation for legal use*

A legal tech platform that enables injured plaintiffs to submit accessible, privacy-preserving evidence of their suffering via SMS, creating tamper-evident attestation chains that are legally defensible and explainable.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)

> **Project Status:** Early-stage development. Core architecture implemented; security hardening, compliance validation, and production deployment in progress. Not yet cleared for production use with real PHI.

---

## Table of Contents

- [Overview](#overview)
- [Who This Is For](#who-this-is-for)
- [Core Principles](#core-principles)
- [Features](#features)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Documentation](#documentation)
- [Development](#development)
- [Security & Compliance](#security--compliance)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

The Phenomenological Evidence System transforms how injured plaintiffs document their lived experience of pain and suffering for legal proceedings. It addresses a critical gap: current evidence collection is **inaccessible** (complex forms, multiple steps) and **non-verifiable** (easy to fabricate or alter).

### The Problem

When someone is in pain at 3am with brain fog, they can't navigate multi-step intake forms. When they submit pain notes months later, opposing counsel questions their authenticity. Traditional systems fail on two fronts:
1. **Accessibility**: Too complex for someone in acute pain
2. **Integrity**: No cryptographic proof of timing and authenticity

### Our Solution

**"PAIN 7 neck"** — A single SMS becomes:
- An **encrypted** record of subjective experience (PHI-protected)
- A **cryptographically chained** attestation entry (tamper-evident)
- A **statistical data point** for pain trajectory inference (HMM-based)
- A **legally defensible** piece of evidence (explainable methodology)

### Who This Is For

- **Plaintiff law firms** who need authentic, time-stamped pain logs instead of backfilled journals submitted months after injury.
- **Nurse life care planners and damages experts** who want a defensible trajectory of suffering and functional limitation over time.
- **Legal tech developers** building intake or case management tools who need a drop-in, HIPAA-aware evidence engine with cryptographic verification.

---

## Core Principles

See [`ACCESSIBILITY_PRINCIPLES.md`](ACCESSIBILITY_PRINCIPLES.md) for full constitutional constraints.

### 1. Single-Step Interactions
No wizards, no multi-step processes. "PAIN 7 neck" is complete.

### 2. Cognitive Load Limits
Never ask for more than one piece of information at a time.

### 3. Robust to Partial Information
Accept incomplete or ambiguous input gracefully.

### 4. Explainability & Recall
Every conclusion must trace back to specific attestations.

---

## Features

### 🔐 **Cryptographic Integrity**
- **Hash Chains**: Each entry cryptographically linked to the previous (blockchain-style linked hash chain)
- **Digital Signatures**: Ed25519/ECDSA signing for non-repudiation
- **Tamper Detection**: Any modification invalidates the entire chain

### 🏥 **PHI Separation**
- **"Hash the shadow, protect the diary"**: Raw narratives encrypted separately
- **Fernet Encryption**: AES-256-GCM for subjective notes
- **Key Wrapping**: Master key wraps data encryption keys (DEK rotation without re-encryption)

### 📱 **Accessible Input**
- **SMS-First**: Twilio integration for text-based reporting
- **Voice Input**: (Roadmap) Speech-to-text processing
- **Web API**: Direct integration for apps and intake forms

### 📊 **Statistical Inference**
- **Hidden Markov Models**: Infer latent pain states from noisy observations
- **Trajectory Analysis**: BASELINE → FLARE → IMPROVEMENT → SEVERE
- **Anomaly Detection**: Flag inconsistent patterns for review

### 📄 **Cryptographic Proof Bundle**
- **Portable commitment**: Self-contained proof package with complete chain verification
- **Optional NFT-style tokenization**: Each persona chain can be bound to a unique token ID for external systems (blockchains, registries, etc.)
- **Legally Defensible**: Includes methodology, assumptions, and limitations
- **Court-Ready**: Designed with Daubert admissibility standards in mind

### ⚖️ **Legal Structure**
- **Evidence Graph**: Facts linked to evidence with semantic roles
- **Duty→Breach→Causation→Damages**: Maps to legal framework
- **Audit Trail**: Complete history of PHI access for HIPAA compliance

---

## Architecture

### 8-Layer System

```
┌─────────────────────────────────────────────────────┐
│  CAPTURE LAYER                                      │
│  SMS (Twilio) → Web API → Voice (future)           │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  PHI SEPARATION LAYER                               │
│  Encrypt raw text → Produce normalized projection   │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  DOMAIN MODELS                                      │
│  Party, PersonaToken, PainState, Fact, Evidence     │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  SIGNING & CRYPTOGRAPHY                             │
│  Ed25519/ECDSA signing, Key management              │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  ATTESTATION CHAIN                                  │
│  Tamper-evident hash chain per persona              │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  HMM INFERENCE                                      │
│  Pain trajectory analysis, anomaly detection        │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  CONTEXT & STATISTICS                               │
│  Temporal/spatial context, case timeline tracking   │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  NFT & INTEGRATION                                  │
│  Cryptographic proof generation, system bridges     │
└─────────────────────────────────────────────────────┘
```

### Key Components

| Component | Purpose | Technology |
|-----------|---------|------------|
| `models.py` | Domain models & database schema | SQLAlchemy |
| `attestation_service.py` | Hash chain management | SHA-256, Canonical JSON |
| `phi_separation.py` | Encrypt/decrypt PHI | Fernet (AES-256) |
| `signing_infrastructure.py` | Digital signatures | Ed25519, ECDSA |
| `hmm_inference.py` | Pain trajectory inference | NumPy, HMM |
| `twilio_handler.py` | SMS inbound/outbound | Twilio API |
| `routes.py` | API endpoints | FastAPI |
| `nft_payload.py` | Cryptographic proof builder | JSON, Base64 |

---

## Quick Start

### Prerequisites

- **Python 3.10+**
- **PostgreSQL 12+**
- **Docker & Docker Compose** (recommended)

### Option 1: Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/filum-meditandi/nft_the_conatus.git
cd nft_the_conatus

# Create environment file
make env
# Edit .env and add your configuration (see .env.example)

# Start services (PostgreSQL + API)
make docker-up

# Run migrations
make migrate

# Check health
make health-check
```

Visit:
- **API**: http://localhost:8000
- **Docs**: http://localhost:8000/docs
- **Health**: http://localhost:8000/health

### Option 2: Local Development

```bash
# Clone repository
git clone https://github.com/filum-meditandi/nft_the_conatus.git
cd nft_the_conatus

# Install dependencies
make dev

# Create .env file
make env
# Edit .env with your settings

# Set up PostgreSQL
# Create database: createdb phenomenological_evidence

# Run migrations
make migrate

# Start server
make run
```

### Generate Cryptographic Keys

```bash
# Generate required keys for .env
make generate-keys

# Add output to your .env file:
# MASTER_ENCRYPTION_KEY=<generated_fernet_key>
# SECRET_KEY=<generated_secret_key>
```

### First Request: Log a Pain Event

Once the server is running, test it with your first pain report:

```bash
curl -X POST http://localhost:8000/api/v1/phenomenology/pain \
  -H "Content-Type: application/json" \
  -d '{
    "party_id": "550e8400-e29b-41d4-a716-446655440000",
    "value": 7.0,
    "location": "neck",
    "quality": "burning",
    "functional_impact": {
      "sleep_disruption": true
    }
  }'
```

**Example response:**
```json
{
  "id": "b3f0c1f0-a4d2-4e8f-9c7b-1a2b3c4d5e6f",
  "attestation_id": "d7e8f9a0-b1c2-3d4e-5f6a-7b8c9d0e1f2a",
  "entry_hash": "5c8f2a1b...e2d3c4b5",
  "payload_hash": "9d1a2b3c...4e5f6a7b",
  "chain_index": 0,
  "created_at": "2025-11-23T03:41:22Z"
}
```

**What just happened:**
- Created an **encrypted PHI record** of the subjective pain note
- Generated a **tamper-evident chain link** with cryptographic hash
- Recorded a **normalized PainState** for HMM statistical analysis
- Returned proof of attestation with verifiable timestamp

See [examples/curl_examples.md](examples/curl_examples.md) for more API examples.

---

## Documentation

### Getting Started
- [Quick Start](#quick-start) - Get up and running
- [Configuration](docs/configuration.md) - Environment variables explained (TODO)
- [API Reference](http://localhost:8000/docs) - Interactive API documentation

### Architecture
- [System Architecture](docs/architecture.md) - 8-layer design (TODO)
- [Database Schema](docs/database.md) - Table relationships (TODO)
- [Cryptography](docs/cryptography.md) - Signing, encryption, chains (TODO)

### Guides
- [SMS Integration](docs/sms-guide.md) - Twilio setup (TODO)
- [HMM Inference](docs/hmm-guide.md) - Statistical analysis (TODO)
- [Deployment](docs/deployment.md) - Production deployment (TODO)

### Compliance
- [HIPAA Compliance](docs/hipaa.md) - PHI handling (TODO)
- [Legal Admissibility](docs/daubert.md) - Court standards (TODO)

---

## Development

### Common Commands

```bash
make help              # Show all available commands
make dev               # Install development dependencies
make run               # Start development server
make test              # Run test suite
make lint              # Run linters
make format            # Format code with black
make migrate-create    # Create new migration
```

### Running Tests

```bash
# All tests
make test

# With coverage
make test-coverage

# Unit tests only
make test-unit

# Integration tests only
make test-integration
```

### Code Quality

```bash
# Format code
make format

# Run linters
make lint

# Type checking
make type-check

# Pre-commit hooks
make pre-commit
```

### Database

```bash
# Create migration
make migrate-create MSG="add new field"

# Run migrations
make migrate

# Rollback one migration
make migrate-down

# Reset database (⚠️ destroys data)
make db-reset
```

---

## Security & Compliance

### HIPAA Compliance

- **PHI Encryption**: All subjective notes encrypted at rest (Fernet/AES-256)
- **Access Logging**: Audit trail for all PHI access
- **Minimum Necessary**: Only normalized projections in attestation chain
- **Key Management**: Recommend HSM/KMS for production master keys

### Cryptographic Standards

- **Signing**: Ed25519 (EdDSA) or ECDSA P-256/P-384
- **Encryption**: Fernet (AES-256-GCM + HMAC)
- **Hashing**: SHA-256 for chain links
- **Canonical Serialization**: Deterministic JSON for reproducible hashes

### Security Best Practices

1. **Never commit secrets** — Use `.env` file (in `.gitignore`)
2. **Rotate keys regularly** — Supports key rotation with previous key list
3. **Use HSM/KMS in production** — Don't store master keys in environment variables
4. **Enable audit logging** — Track all PHI access
5. **Review CORS origins** — Whitelist only trusted domains

---

## Technology Stack

- **Framework**: FastAPI (Python 3.10+)
- **Database**: PostgreSQL 12+ with SQLAlchemy ORM
- **Migrations**: Alembic
- **Cryptography**: `cryptography` library (Fernet, Ed25519, ECDSA)
- **SMS**: Twilio API
- **Statistics**: NumPy (Hidden Markov Models)
- **Containerization**: Docker & Docker Compose
- **Testing**: pytest, pytest-asyncio

---

## Project Structure

```
nft_the_conatus/
├── alembic/                    # Database migrations
│   ├── versions/
│   │   ├── 001_phenomenological_evidence.py
│   │   └── 002_complete_schema.py
│   └── env.py
├── docs/                       # Documentation
│   ├── design/                 # Design documents (PDFs)
│   └── ACCESSIBILITY_PRINCIPLES.md
├── tests/                      # Test suite
│   ├── test_models.py
│   ├── test_attestation.py
│   └── ...
├── *.py                        # Core application modules
│   ├── main.py                 # FastAPI app entry point
│   ├── config.py               # Configuration management
│   ├── database.py             # Database session management
│   ├── models.py               # Domain models
│   ├── routes.py               # API endpoints
│   ├── twilio_handler.py       # SMS integration
│   ├── attestation_service.py  # Hash chain management
│   ├── phi_separation.py       # PHI encryption
│   ├── signing_infrastructure.py # Digital signatures
│   ├── hmm_inference.py        # Statistical inference
│   └── ...
├── pyproject.toml              # Project dependencies
├── Dockerfile                  # Container image
├── docker-compose.yml          # Local dev environment
├── Makefile                    # Common operations
├── .env.example                # Environment template
└── README.md                   # This file
```

---

## Roadmap

### Phase 1: Core Platform - Architecture Complete (Integration in Progress)
- [x] Database schema and models (code complete, not yet tested end-to-end)
- [x] Attestation chain implementation (core logic complete, integration pending)
- [x] PHI separation and encryption (implemented, needs production hardening)
- [x] SMS integration (Twilio handlers written, webhook testing needed)
- [x] HMM inference engine (statistical models implemented, validation pending)
- [x] FastAPI endpoints (routes defined, database integration in progress)
- [x] Docker deployment (containers configured, orchestration ready)

### Phase 2: Production Readiness (Current)
- [ ] Comprehensive test suite
- [ ] API authentication (JWT)
- [ ] Rate limiting
- [ ] Monitoring and observability
- [ ] Production deployment guide
- [ ] HIPAA compliance audit

### Phase 3: Enhanced Features
- [ ] Voice input processing
- [ ] Mobile app (React Native)
- [ ] Multi-language support
- [ ] Advanced HMM tuning
- [ ] Blockchain integration (optional)
- [ ] NFT minting

### Phase 4: Ecosystem Integration
- [ ] EHR integrations
- [ ] Case management system bridge
- [ ] Expert witness portal
- [ ] Court filing automation

---

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Setup

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (`make test`)
5. Format code (`make format`)
6. Commit (`git commit -m 'Add amazing feature'`)
7. Push (`git push origin feature/amazing-feature`)
8. Open a Pull Request

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Citation

If you use this system in research or legal proceedings, please cite:

```
The Conatus Project. (2024). Phenomenological Evidence System:
Cryptographically verified lived experience documentation for legal use.
https://github.com/filum-meditandi/nft_the_conatus
```

---

## Contact & Support

- **Issues**: [GitHub Issues](https://github.com/filum-meditandi/nft_the_conatus/issues)
- **Discussions**: [GitHub Discussions](https://github.com/filum-meditandi/nft_the_conatus/discussions)

---

## Acknowledgments

Built on principles of:
- **Accessibility-first design** for vulnerable users
- **Privacy-preserving cryptography** for sensitive health data
- **Explainable AI** for legal admissibility (Daubert standards)
- **Open source transparency** for trust and auditability

---

**Built with care for those in pain.**
