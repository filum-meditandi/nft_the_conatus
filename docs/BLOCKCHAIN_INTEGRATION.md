# Blockchain Integration Strategy

## Overview

This document details how Conatus integrates blockchain technology and NFTs to provide **cryptographic proof of data integrity** for legal case management. The system creates tamper-evident chains for client PII and case documents, enabling attorneys to prove document authenticity in court.

---

## Why Blockchain for Legal Case Management?

### The Problem

In litigation, opposing counsel frequently challenges:
1. **Document Timing**: "When was this demand letter actually created? Was it backdated?"
2. **Data Tampering**: "How do we know this medical chronology wasn't modified after the fact?"
3. **Access Logs**: "Who accessed this client's PHI and when? (HIPAA requirement)"

### Traditional Solutions (Inadequate)

- **File metadata**: Easily manipulated (change system clock, edit EXIF data)
- **PDF signatures**: Only proves who signed, not when or if content changed
- **Audit logs in database**: Can be altered by database admin

### Blockchain Solution

Blockchain provides **immutable, timestamped, cryptographically-signed records** that:

✓ **Cannot be backdated**: Timestamp embedded in blockchain (Polygon block time)
✓ **Cannot be tampered**: Hash chains detect any modification
✓ **Cannot be repudiated**: Digital signatures prove authorship
✓ **Third-party verifiable**: Anyone can verify the chain without trusting us

This is **not about cryptocurrency**—it's about using blockchain's core strength (immutable audit logs) for legal evidence integrity.

---

## Architecture Overview

### Two-Layer System

```
┌─────────────────────────────────────────────────────────────┐
│                   LOCAL CHAIN (SQLite)                      │
│  - Fast reads/writes                                        │
│  - Full history stored locally                              │
│  - Works offline                                            │
│  - No gas fees                                              │
└─────────────────────────────────────────────────────────────┘
                          ↓ (periodic sync)
┌─────────────────────────────────────────────────────────────┐
│              BLOCKCHAIN LAYER (Polygon/Solana)              │
│  - Immutable timestamps                                     │
│  - Third-party verifiable                                   │
│  - Batched commits (reduce costs)                           │
│  - On-demand minting (only when exporting proof)            │
└─────────────────────────────────────────────────────────────┘
```

**Local Chain** = Performance (instant operations)
**Blockchain Layer** = Proof (when you need it for court)

---

## Data Models

### 1. NFT Chains Table

```sql
CREATE TABLE nft_chains (
    id TEXT PRIMARY KEY,                -- Chain ID (UUID)
    client_id TEXT UNIQUE NOT NULL,     -- One chain per client
    blockchain_address TEXT,            -- Smart contract address (if minted)
    latest_block_hash TEXT NOT NULL,    -- Head of the chain
    entry_count INTEGER DEFAULT 0,      -- Number of entries in chain
    last_synced_at TEXT,                -- Last blockchain sync timestamp
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (client_id) REFERENCES clients(id)
);
```

### 2. Chain Entries Table

```sql
CREATE TABLE chain_entries (
    id TEXT PRIMARY KEY,                -- Entry ID (UUID)
    chain_id TEXT NOT NULL,
    entry_type TEXT NOT NULL,           -- Entry type (see below)
    payload_hash TEXT NOT NULL,         -- SHA-256 of canonical payload
    previous_hash TEXT,                 -- Link to previous entry (null for first)
    signature TEXT NOT NULL,            -- EdDSA signature (Ed25519)
    timestamp TEXT NOT NULL,            -- ISO 8601 timestamp
    payload_encrypted BLOB,             -- Encrypted payload (for PII entries)
    payload_metadata TEXT,              -- JSON metadata (non-sensitive)
    blockchain_tx_hash TEXT,            -- Polygon/Solana transaction hash (if synced)
    created_at TEXT NOT NULL,
    FOREIGN KEY (chain_id) REFERENCES nft_chains(id)
);

CREATE INDEX idx_chain_entries_chain ON chain_entries(chain_id);
CREATE INDEX idx_chain_entries_timestamp ON chain_entries(timestamp);
CREATE INDEX idx_chain_entries_type ON chain_entries(entry_type);
```

### 3. Entry Types

| Entry Type | Purpose | Payload | Encrypted |
|------------|---------|---------|-----------|
| `CHAIN_INIT` | First entry in chain | Client ID, public key | No |
| `PII_CREATED` | Client record created | Full client data | Yes |
| `PII_UPDATED` | Client data modified | Changed fields only | Yes |
| `DOCUMENT_CREATED` | Document generated | Document hash + metadata | No |
| `DOCUMENT_MODIFIED` | Document edited | New hash, change summary | No |
| `ACCESS_LOG` | PHI accessed | User, field, reason | No |
| `PAIN_REPORT` | SMS pain tracking | From phenomenological system | Yes |
| `TREATMENT_ADDED` | Medical treatment logged | Treatment summary | Partial |
| `RECORDS_REQUEST` | Records request sent | Provider, date | No |

---

## Chain Construction

### Entry Structure

```rust
#[derive(Serialize, Deserialize)]
struct ChainEntry {
    id: String,                      // UUID
    chain_id: String,
    entry_type: EntryType,
    payload_hash: String,            // SHA-256 hex
    previous_hash: Option<String>,   // SHA-256 hex (null for first entry)
    signature: String,               // Ed25519 signature (base64)
    timestamp: String,               // ISO 8601
    payload_encrypted: Option<Vec<u8>>, // Encrypted payload
    metadata: serde_json::Value,     // JSON metadata
}
```

### Hashing Algorithm

**Canonical Payload** (for deterministic hashing):
```rust
fn compute_payload_hash(entry: &ChainEntry) -> String {
    let canonical = serde_json::json!({
        "entry_type": entry.entry_type,
        "timestamp": entry.timestamp,
        "metadata": entry.metadata,
        "payload": entry.payload_encrypted.as_ref().map(base64::encode),
    });

    // Serialize with sorted keys (canonical JSON)
    let canonical_str = canonical_to_string(&canonical);

    // SHA-256 hash
    let hash = sha256(canonical_str.as_bytes());
    hex::encode(hash)
}
```

**Entry Hash** (for linking):
```rust
fn compute_entry_hash(entry: &ChainEntry) -> String {
    let linkable = serde_json::json!({
        "id": entry.id,
        "payload_hash": entry.payload_hash,
        "timestamp": entry.timestamp,
        "previous_hash": entry.previous_hash,
    });

    let linkable_str = canonical_to_string(&linkable);
    let hash = sha256(linkable_str.as_bytes());
    hex::encode(hash)
}
```

### Signing

**Algorithm**: Ed25519 (EdDSA)
**Key Pair**: Per-user signing key (stored securely, password-protected)

```rust
fn sign_entry(entry: &ChainEntry, private_key: &ed25519::PrivateKey) -> String {
    let entry_hash = compute_entry_hash(entry);
    let signature = private_key.sign(entry_hash.as_bytes());
    base64::encode(signature.as_bytes())
}

fn verify_entry_signature(
    entry: &ChainEntry,
    public_key: &ed25519::PublicKey
) -> Result<(), Error> {
    let entry_hash = compute_entry_hash(entry);
    let signature = base64::decode(&entry.signature)?;
    public_key.verify(entry_hash.as_bytes(), &signature)?;
    Ok(())
}
```

### Chain Verification

```rust
fn verify_chain(entries: &[ChainEntry]) -> Result<(), Error> {
    if entries.is_empty() {
        return Err(Error::EmptyChain);
    }

    // Verify first entry has no previous hash
    if entries[0].previous_hash.is_some() {
        return Err(Error::InvalidFirstEntry);
    }

    // Verify each subsequent entry
    for window in entries.windows(2) {
        let prev = &window[0];
        let curr = &window[1];

        // Compute previous entry's hash
        let prev_hash = compute_entry_hash(prev);

        // Check current entry's previous_hash matches
        match &curr.previous_hash {
            Some(hash) if hash == &prev_hash => {},
            _ => return Err(Error::BrokenChain {
                expected: prev_hash,
                actual: curr.previous_hash.clone(),
            }),
        }

        // Verify signature
        verify_entry_signature(curr, &get_public_key(curr.chain_id)?)?;
    }

    Ok(())
}
```

---

## Encryption Strategy

### PII Encryption

**Algorithm**: AES-256-GCM (via Fernet-compatible scheme)

**Key Hierarchy**:
```
User Password (Argon2)
    ↓
Master Key (256-bit)
    ↓
Data Encryption Keys (DEK, per-client, 256-bit)
    ↓
Individual PII Fields
```

**Encrypted Payload Structure**:
```rust
#[derive(Serialize, Deserialize)]
struct EncryptedPayload {
    version: u8,                    // Encryption version (for future upgrades)
    dek_id: String,                 // Which DEK was used
    nonce: String,                  // AES-GCM nonce (base64)
    ciphertext: String,             // Encrypted data (base64)
    tag: String,                    // Authentication tag (base64)
}
```

**Example Encrypted Entry**:
```json
{
  "entry_type": "PII_CREATED",
  "timestamp": "2025-11-23T10:30:00Z",
  "payload_encrypted": {
    "version": 1,
    "dek_id": "dek_client_abc123",
    "nonce": "q2HBfSr8...",
    "ciphertext": "xK9mPz...",
    "tag": "7FqT3w..."
  },
  "metadata": {
    "client_id": "abc123",
    "fields_updated": ["first_name", "ssn", "address"]
  }
}
```

**Decryption Process**:
1. User enters password → derive master key
2. Load DEK (encrypted with master key) → decrypt DEK
3. Use DEK to decrypt payload
4. **Log access to chain** (new `ACCESS_LOG` entry)

---

## Mail Merge Integration

### Document Generation Flow with Blockchain

```
1. User selects template + case
2. System extracts keywords (e.g., {{CLIENT_SSN}})
3. For PII keywords:
   a. Retrieve encrypted entry from chain
   b. Decrypt payload
   c. LOG ACCESS (new chain entry: "USER_123 accessed CLIENT_SSN for DOCUMENT_456")
4. Fill template with decrypted data
5. Generate document (DOCX/PDF)
6. Compute document hash (SHA-256)
7. Create chain entry:
   {
     "entry_type": "DOCUMENT_CREATED",
     "metadata": {
       "document_id": "doc_789",
       "template_id": "tpl_req_medical",
       "case_id": "case_456",
       "file_hash": "a3f5b2...",
       "file_name": "Records_Request_2025-11-23.pdf",
       "keywords_used": ["CLIENT_NAME", "PROVIDER_NAME", "DOS_FIRST"]
     }
   }
8. Save document to disk
9. Return to user
```

**Key Insight**: Every document generation is **timestamped and chained**. If opposing counsel questions when a demand letter was created, you can:
1. Show the chain entry (with timestamp)
2. Provide the document file (matches hash in chain)
3. Prove chain integrity (no tampering)
4. Export blockchain proof (if entry was synced to Polygon)

---

## Blockchain Layer (Polygon)

### Smart Contract

**Contract**: `ClientDataChain.sol`

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract ClientDataChain {
    struct ChainAnchor {
        bytes32 latestHash;      // Hash of latest entry
        uint256 entryCount;      // Number of entries
        uint256 lastUpdated;     // Block timestamp
    }

    // Mapping: clientId => ChainAnchor
    mapping(string => ChainAnchor) public chains;

    event ChainUpdated(
        string indexed clientId,
        bytes32 latestHash,
        uint256 entryCount,
        uint256 timestamp
    );

    function updateChain(
        string memory clientId,
        bytes32 latestHash,
        uint256 entryCount
    ) public {
        chains[clientId] = ChainAnchor({
            latestHash: latestHash,
            entryCount: entryCount,
            lastUpdated: block.timestamp
        });

        emit ChainUpdated(clientId, latestHash, entryCount, block.timestamp);
    }

    function getChain(string memory clientId)
        public
        view
        returns (ChainAnchor memory)
    {
        return chains[clientId];
    }
}
```

**Why this design?**:
- **No PII on-chain**: Only hashes and counts (privacy!)
- **Batched updates**: One transaction updates the entire chain head (cost-effective)
- **Lazy minting**: Only sync to blockchain when exporting proof for court
- **Verifiable**: Anyone can check `latestHash` matches local chain

### Rust Integration

**Dependency**: `ethers` crate

```rust
use ethers::prelude::*;

pub struct BlockchainService {
    provider: Provider<Http>,
    contract: Contract,
    wallet: LocalWallet,
}

impl BlockchainService {
    pub async fn sync_chain(
        &self,
        client_id: &str,
        latest_hash: &str,
        entry_count: u64,
    ) -> Result<TransactionReceipt, Error> {
        let tx = self.contract
            .method::<_, ()>("updateChain", (
                client_id.to_string(),
                H256::from_slice(&hex::decode(latest_hash)?),
                U256::from(entry_count),
            ))?
            .send()
            .await?
            .await?
            .ok_or(Error::TransactionFailed)?;

        Ok(tx)
    }

    pub async fn verify_chain_onchain(
        &self,
        client_id: &str,
        expected_hash: &str,
        expected_count: u64,
    ) -> Result<bool, Error> {
        let anchor: (H256, U256, U256) = self.contract
            .method::<_, _>("getChain", client_id.to_string())?
            .call()
            .await?;

        let (latest_hash, entry_count, _timestamp) = anchor;

        Ok(
            latest_hash == H256::from_slice(&hex::decode(expected_hash)?)
            && entry_count == U256::from(expected_count)
        )
    }
}
```

### Batch Syncing Strategy

**Problem**: Polygon gas fees (even low) add up if syncing every entry individually

**Solution**: Batch updates

```rust
async fn batch_sync_chains(
    service: &BlockchainService,
    chains_to_sync: Vec<(String, String, u64)>, // (client_id, hash, count)
) -> Result<TransactionReceipt, Error> {
    // Call contract with array of updates
    // (Requires modified smart contract to accept batches)
    service.contract
        .method::<_, ()>("batchUpdateChains", chains_to_sync)?
        .send()
        .await?
        .await?
        .ok_or(Error::TransactionFailed)
}
```

**When to sync**:
1. **User-triggered**: "Sync all chains to blockchain" button
2. **Before export**: Automatically sync when exporting proof bundle
3. **Scheduled**: Nightly batch sync (optional, for peace of mind)

### Cost Analysis

**Polygon Costs** (as of Nov 2025):
- Gas price: ~30 Gwei
- Update transaction: ~50,000 gas
- Cost per update: ~0.0015 MATIC (~$0.001 USD)

**Example**:
- 100 clients × 1 sync/month = 100 transactions/month = $0.10/month
- High-volume firm (1000 clients) = $1/month

**Negligible cost** compared to case management subscription fees.

---

## Proof Bundle Export

### Use Case

Attorney needs to submit evidence to court showing:
1. Demand letter was created on [date]
2. Medical chronology has not been altered since [date]
3. Client pain reports are authentic and timestamped

### Proof Bundle Structure

```json
{
  "version": "1.0",
  "client_id": "abc123",
  "client_name": "John Doe (redacted per court rules)",
  "case_id": "case_456",
  "generated_at": "2025-11-23T15:30:00Z",
  "chain_summary": {
    "entry_count": 127,
    "first_entry_timestamp": "2024-01-15T09:00:00Z",
    "latest_entry_timestamp": "2025-11-23T10:30:00Z",
    "latest_hash": "a3f5b2c1d4e6..."
  },
  "blockchain_anchor": {
    "network": "Polygon Mainnet",
    "contract_address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
    "transaction_hash": "0x9c5e...",
    "block_number": 51234567,
    "block_timestamp": "2025-11-23T15:00:00Z"
  },
  "entries": [
    {
      "id": "entry_001",
      "entry_type": "DOCUMENT_CREATED",
      "timestamp": "2025-10-01T14:22:00Z",
      "payload_hash": "f7a3b1...",
      "previous_hash": "d2c4e9...",
      "signature": "q8K3mP...",
      "metadata": {
        "document_id": "doc_789",
        "file_name": "Demand_Letter_2025-10-01.pdf",
        "file_hash": "a3f5b2..."
      }
    },
    {
      "id": "entry_002",
      "entry_type": "PAIN_REPORT",
      "timestamp": "2025-10-02T03:15:00Z",
      "payload_hash": "c4d2a1...",
      "previous_hash": "f7a3b1...",
      "signature": "r9L4nQ...",
      "metadata": {
        "pain_level": 8,
        "location": "neck",
        "via": "SMS"
      }
    }
  ],
  "verification_instructions": {
    "step_1": "Verify chain integrity by hashing each entry and checking previous_hash links",
    "step_2": "Verify signatures using public key: 0x3a7f...",
    "step_3": "Verify blockchain anchor by querying Polygon contract at address above",
    "step_4": "Match document file hashes with metadata hashes"
  },
  "public_key": "0x3a7f4b2c1d5e...",
  "attestation": "I, [Attorney Name], certify that this proof bundle accurately represents the cryptographic chain for client [redacted] in case [redacted]. The chain has been verified and no tampering has been detected. Signed: [Digital Signature]"
}
```

### Export Process

```rust
#[tauri::command]
async fn export_proof_bundle(
    chain_id: String,
    entry_ids: Vec<String>, // Which entries to include (or all)
    include_documents: bool,
    state: tauri::State<'_, AppState>,
) -> Result<String, Error> {
    // 1. Fetch chain entries from database
    let entries = db::get_chain_entries(&state.db, &chain_id, &entry_ids).await?;

    // 2. Verify chain integrity locally
    verify_chain(&entries)?;

    // 3. Sync to blockchain (if not already synced)
    let tx_hash = blockchain::sync_chain(
        &state.blockchain,
        &chain_id,
        &entries.last().unwrap().payload_hash,
        entries.len() as u64,
    ).await?;

    // 4. Build proof bundle JSON
    let bundle = ProofBundle {
        version: "1.0".to_string(),
        chain_summary: ChainSummary::from_entries(&entries),
        blockchain_anchor: BlockchainAnchor {
            network: "Polygon Mainnet".to_string(),
            transaction_hash: tx_hash,
            // ...
        },
        entries: entries.into_iter().map(|e| e.into()).collect(),
        // ...
    };

    // 5. Save to file
    let output_path = format!("~/Documents/Conatus/Proofs/proof_{}.json", chain_id);
    std::fs::write(&output_path, serde_json::to_string_pretty(&bundle)?)?;

    // 6. Optionally include document files in a ZIP
    if include_documents {
        create_proof_archive(&output_path, &entries)?;
    }

    Ok(output_path)
}
```

### Court Submission

**Attorney provides**:
1. Proof bundle JSON
2. Original documents (PDFs, etc.)
3. Expert declaration explaining the system

**Expert witness testimony** (optional):
> "The Conatus system uses industry-standard cryptographic techniques—SHA-256 hashing, Ed25519 signatures, and blockchain timestamping—to create a tamper-evident audit trail. I have verified the chain integrity and confirmed that the documents match their recorded hashes. The timestamps are anchored to the Polygon blockchain, which is independently verifiable."

---

## Privacy Considerations

### PII Never Leaves Local Device (Unless User Chooses Cloud Sync)

**Encrypted Payloads**:
- PII fields encrypted before adding to chain
- Encryption keys never leave local device
- Blockchain only sees **hashes** (not plaintext)

**Example**:
```
❌ WRONG: Store "SSN: 123-45-6789" in blockchain entry
✓ CORRECT: Store encrypted blob + hash in local DB, hash in blockchain
```

### HIPAA Compliance

**Requirements Met**:
1. ✓ **Encryption at rest**: All PHI encrypted (AES-256)
2. ✓ **Access logs**: Every PII access logged to chain
3. ✓ **Audit trail**: Complete history, immutable
4. ✓ **Minimum necessary**: Only hashes on public blockchain
5. ✓ **Patient rights**: Export functionality (patient owns their data)

**Access Logging Example**:
```rust
async fn decrypt_pii(
    entry_id: &str,
    user_id: &str,
    reason: &str,
    state: &AppState,
) -> Result<String, Error> {
    // 1. Decrypt the PII
    let plaintext = crypto::decrypt_entry(entry_id, &state.crypto)?;

    // 2. Log the access
    let access_entry = ChainEntry {
        entry_type: EntryType::AccessLog,
        metadata: json!({
            "accessed_entry": entry_id,
            "accessed_by": user_id,
            "reason": reason,
            "timestamp": Utc::now().to_rfc3339(),
        }),
        // ...
    };
    add_entry_to_chain(&state.db, access_entry).await?;

    Ok(plaintext)
}
```

---

## Integration with Phenomenological Evidence System

### Existing System

The repository already has an **SMS-based pain tracking system** (`twilio_handler.py`, `attestation_service.py`) that:
- Accepts SMS like "PAIN 7 neck burning"
- Creates cryptographic attestation chains
- Uses Ed25519 signing
- Stores encrypted subjective notes

### Integration Strategy

**Unified Chain**:
- Pain reports become entries in the same client chain
- Entry type: `PAIN_REPORT`
- Payload: Pain level, location, quality, timestamp
- Encrypted: Subjective notes (if provided)

**Data Flow**:
1. Client sends SMS → Twilio → FastAPI backend (existing)
2. Backend creates attestation entry (existing)
3. **NEW**: Backend calls Tauri app API to add entry to local chain
4. Tauri app syncs entry to local SQLite
5. Entry appears in client's timeline (case management UI)

**Example Entry**:
```json
{
  "entry_type": "PAIN_REPORT",
  "timestamp": "2025-11-23T03:15:00Z",
  "metadata": {
    "pain_level": 7,
    "location": "neck",
    "quality": "burning",
    "via": "SMS",
    "phone_number": "+1234567890",
    "original_message": "PAIN 7 neck burning"
  },
  "payload_encrypted": {
    "subjective_note": "Can't sleep, burning sensation radiating to shoulders"
  }
}
```

**UI Integration**:
- Timeline view shows pain reports alongside medical treatments
- Demand letter generator auto-includes pain trajectory
- Care planner visualizes pain over time

**Blockchain Benefit**:
- Proves pain reports are contemporaneous (not fabricated later)
- Opposing counsel cannot claim plaintiff exaggerated symptoms after filing suit

---

## Alternative: Solana Instead of Polygon

### Trade-offs

| Feature | Polygon | Solana |
|---------|---------|--------|
| **Transaction Cost** | ~$0.001 | ~$0.0001 (10x cheaper) |
| **Transaction Speed** | ~2 seconds | ~400ms (5x faster) |
| **Ecosystem Maturity** | High (Ethereum-compatible) | Medium (growing) |
| **Developer Tools** | Excellent (ethers.js, hardhat) | Good (Anchor, solana-web3.js) |
| **EVM Compatibility** | Yes (can reuse Solidity skills) | No (Rust-based) |

### Recommendation

**Start with Polygon**, switch to Solana if:
1. Transaction volume is very high (>10,000/month)
2. Solana ecosystem matures further
3. Users request it

---

## Future Enhancements

### 1. IPFS for Document Storage

**Problem**: Large documents (50 MB medical records) are expensive to store on-chain

**Solution**: Store documents on IPFS, put IPFS hash on-chain

```rust
async fn upload_to_ipfs(document: &[u8]) -> Result<String, Error> {
    let client = ipfs_api::IpfsClient::default();
    let response = client.add(document).await?;
    Ok(response.hash) // Returns CID (Content Identifier)
}

// Chain entry metadata
{
  "document_id": "doc_789",
  "ipfs_cid": "QmX3f5b2c1d4e6...",
  "file_hash": "a3f5b2..." // SHA-256 for integrity check
}
```

### 2. Zero-Knowledge Proofs (zk-SNARKs)

**Problem**: Want to prove facts about data without revealing the data

**Example**: Prove "client had 5+ severe pain episodes in October" without showing actual pain levels

**Solution**: Use zk-SNARKs to generate cryptographic proof of claim

```
Claim: "COUNT(entries WHERE entry_type='PAIN_REPORT' AND pain_level >= 8 AND month='2025-10') >= 5"
Proof: zk-SNARK that verifies claim without revealing individual pain levels
```

**Status**: Future research (complex, but powerful)

### 3. Multi-Signature Chains

**Problem**: Want multiple attorneys to co-sign important entries (e.g., settlement demand)

**Solution**: Multi-sig entries requiring 2-of-3 signatures

```rust
{
  "entry_type": "DOCUMENT_CREATED",
  "metadata": {
    "document": "Settlement_Demand_$2M.pdf",
    "requires_signatures": ["attorney_1", "attorney_2", "managing_partner"]
  },
  "signatures": {
    "attorney_1": "q8K3mP...",
    "attorney_2": "r9L4nQ...",
    "managing_partner": "s0M5oR..."
  }
}
```

---

## Developer Guide

### Creating a New Chain

```rust
#[tauri::command]
async fn init_client_chain(
    client_id: String,
    state: tauri::State<'_, AppState>,
) -> Result<NftChain, Error> {
    // 1. Generate chain ID
    let chain_id = Uuid::new_v4().to_string();

    // 2. Create first entry (CHAIN_INIT)
    let init_entry = ChainEntry {
        id: Uuid::new_v4().to_string(),
        chain_id: chain_id.clone(),
        entry_type: EntryType::ChainInit,
        payload_hash: compute_payload_hash(&json!({
            "client_id": client_id,
            "initialized_at": Utc::now().to_rfc3339(),
        })),
        previous_hash: None, // First entry
        signature: sign_entry(&init_entry, &state.crypto.signing_key),
        timestamp: Utc::now().to_rfc3339(),
        // ...
    };

    // 3. Save to database
    db::create_chain(&state.db, &chain_id, &client_id).await?;
    db::add_entry(&state.db, &init_entry).await?;

    Ok(NftChain {
        id: chain_id,
        client_id,
        latest_block_hash: compute_entry_hash(&init_entry),
        entry_count: 1,
        // ...
    })
}
```

### Adding an Entry

```rust
#[tauri::command]
async fn add_chain_entry(
    chain_id: String,
    entry_data: CreateChainEntryDto,
    state: tauri::State<'_, AppState>,
) -> Result<ChainEntry, Error> {
    // 1. Get latest entry (for previous_hash)
    let latest = db::get_latest_entry(&state.db, &chain_id).await?;

    // 2. Build new entry
    let entry = ChainEntry {
        id: Uuid::new_v4().to_string(),
        chain_id: chain_id.clone(),
        entry_type: entry_data.entry_type,
        payload_hash: compute_payload_hash(&entry_data.payload),
        previous_hash: Some(compute_entry_hash(&latest)),
        timestamp: Utc::now().to_rfc3339(),
        signature: "placeholder", // Sign after hashing
        // ...
    };

    // 3. Sign entry
    let signature = sign_entry(&entry, &state.crypto.signing_key);
    entry.signature = signature;

    // 4. Save to database
    db::add_entry(&state.db, &entry).await?;

    // 5. Update chain head
    db::update_chain_head(&state.db, &chain_id, &entry.payload_hash).await?;

    Ok(entry)
}
```

### Verifying a Chain

```rust
#[tauri::command]
async fn verify_chain(
    chain_id: String,
    state: tauri::State<'_, AppState>,
) -> Result<ChainVerificationResult, Error> {
    // 1. Fetch all entries
    let entries = db::get_all_entries(&state.db, &chain_id).await?;

    // 2. Verify integrity
    match crypto::verify_chain(&entries) {
        Ok(_) => Ok(ChainVerificationResult {
            valid: true,
            entry_count: entries.len(),
            first_entry_timestamp: entries[0].timestamp.clone(),
            latest_entry_timestamp: entries.last().unwrap().timestamp.clone(),
            errors: vec![],
        }),
        Err(e) => Ok(ChainVerificationResult {
            valid: false,
            errors: vec![format!("Chain verification failed: {}", e)],
            // ...
        }),
    }
}
```

---

## Conclusion

Blockchain integration in Conatus provides **unprecedented data integrity** for legal case management:

✓ **Tamper-evident chains**: Any modification is detectable
✓ **Third-party verifiable**: Court can independently verify
✓ **Privacy-preserving**: Only hashes on public blockchain
✓ **Cost-effective**: ~$0.001 per update (Polygon)
✓ **HIPAA-compliant**: Encrypted PII, access logs, audit trails

**This is not blockchain hype—it's blockchain used correctly**: immutable audit logs for high-stakes legal evidence.

---

*Document Version: 1.0*
*Last Updated: 2025-11-23*
*Author: Conatus Team*
