# Technical Architecture: Conatus Legal Case Management System

## Overview

This document defines the technical architecture for Conatus, a Tauri-based desktop application for plaintiff law firm case management with blockchain-secured data integrity and AI-powered document automation.

---

## Architecture Principles

### 1. Local-First
- **Primary data storage**: Local SQLite database
- **Cloud sync**: Optional (user-controlled)
- **Offline-first**: Full functionality without internet
- **Performance**: Native speed, no latency

### 2. Privacy & Security
- **End-to-end encryption**: All PII encrypted at rest
- **Zero-knowledge**: Server (if used) never sees plaintext PII
- **Blockchain audit**: Cryptographic proof of data integrity
- **HIPAA compliant**: Full audit trails, access controls

### 3. Extensibility
- **Modular architecture**: Features as plugins
- **API-first**: All operations available via internal API
- **Template system**: User-customizable documents
- **Integration hooks**: Future EHR, e-filing, billing integrations

### 4. Developer Experience
- **Type safety**: TypeScript frontend, Rust backend
- **Testing**: Unit, integration, e2e test coverage
- **CI/CD**: Automated builds, code signing, releases
- **Documentation**: API docs, architecture diagrams, contribution guide

---

## System Architecture

### High-Level Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     TAURI DESKTOP APP                           │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │              FRONTEND (React + TypeScript)                │ │
│  │                                                           │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │ │
│  │  │  Client  │  │ Medical  │  │   Doc    │  │   Care   │ │ │
│  │  │   Mgmt   │  │ Records  │  │  Merge   │  │ Planner  │ │ │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘ │ │
│  │                                                           │ │
│  │  ┌──────────────────────────────────────────────────────┐ │ │
│  │  │           State Management (Zustand)                 │ │ │
│  │  └──────────────────────────────────────────────────────┘ │ │
│  └───────────────────────────────────────────────────────────┘ │
│                             ↕                                   │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │           TAURI COMMANDS (IPC Bridge)                     │ │
│  └───────────────────────────────────────────────────────────┘ │
│                             ↕                                   │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │            RUST BACKEND (Tauri Core)                      │ │
│  │                                                           │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │ │
│  │  │ Database │  │   Crypto │  │   File   │  │   NFT    │ │ │
│  │  │  Layer   │  │  Service │  │ I/O Mgr  │  │  Chain   │ │ │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘ │ │
│  │                                                           │ │
│  │  ┌──────────────────────────────────────────────────────┐ │ │
│  │  │            Local SQLite Database                     │ │ │
│  │  └──────────────────────────────────────────────────────┘ │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                             ↕
┌─────────────────────────────────────────────────────────────────┐
│                   EXTERNAL SERVICES                             │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │  OpenAI API  │  │  Blockchain  │  │   Cloud Sync │         │
│  │  (AI Merge)  │  │   (Polygon)  │  │  (Optional)  │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐                           │
│  │    Twilio    │  │  Phenomeno-  │                           │
│  │  (SMS Pain)  │  │  logical API │                           │
│  └──────────────┘  └──────────────┘                           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Technology Stack

### Desktop Application

**Tauri (v2.x)**
- **Why**: Cross-platform (Windows, macOS, Linux), small bundle size, native performance, security
- **Rust Core**: File I/O, crypto operations, database access, system integration
- **WebView**: Renders React UI using native OS webview (no Electron bloat)

**Frontend**
- **React 18**: UI library with hooks, concurrent features
- **TypeScript**: Type safety, better DX, catch bugs early
- **Vite**: Fast builds, HMR, optimized production bundles
- **Tailwind CSS**: Utility-first styling, consistent design system
- **shadcn/ui**: Accessible component library (built on Radix UI)
- **React Router**: Client-side routing for multi-page app feel

**State Management**
- **Zustand**: Lightweight, TypeScript-friendly, minimal boilerplate
- **Alternative**: Jotai (atomic state) if we need more granular subscriptions

**Forms & Validation**
- **React Hook Form**: Performant forms with minimal re-renders
- **Zod**: TypeScript-first schema validation, runtime type checking

**Data Fetching**
- **TanStack Query (React Query)**: Server state management, caching, optimistic updates
- **Tauri Commands**: IPC calls to Rust backend (wrapped by React Query)

### Backend (Tauri Rust Core)

**Database**
- **SQLite (via SQLx)**: Local relational database, ACID transactions, no server required
- **Schema Management**: SQL migrations in `migrations/` directory
- **ORM Alternative**: Consider Diesel if we need more ORM-like features

**Cryptography**
- **ring**: Fast, safe crypto primitives (Rust)
- **ed25519-dalek**: EdDSA signing (same as existing system)
- **aes-gcm**: AES-256-GCM encryption for PII
- **argon2**: Key derivation from user passwords
- **sha2**: Hashing for blockchain chains

**File I/O**
- **tokio::fs**: Async file operations
- **pdf-rs or printpdf**: PDF generation (Rust-native)
- **Alternative**: Shell out to Pandoc for Word/PDF conversion

**Serialization**
- **serde**: JSON/TOML serialization
- **serde_json**: JSON parsing (canonical JSON for blockchain)
- **bincode**: Binary serialization for performance-critical paths

### External Services

**AI (OpenAI API)**
- **Purpose**: Document template assistance, mail merge intelligence, demand letter drafting
- **Model**: GPT-4 Turbo (or GPT-4o for cost efficiency)
- **Fallback**: Claude (Anthropic) if OpenAI has issues
- **Local Alternative**: (Future) Llama 3 via Ollama for offline mode

**Blockchain (Polygon or Solana)**
- **Purpose**: NFT minting for client data chains, document hash storage
- **Why Polygon**: Low gas fees, Ethereum-compatible, established
- **Why Solana**: Even lower fees, faster transactions, growing ecosystem
- **Decision**: Start with Polygon (more mature tooling), evaluate Solana later
- **Libraries**: `web3.rs` or `ethers-rs` (Rust), `ethers.js` (TypeScript)

**SMS (Twilio)**
- **Purpose**: Pain tracking integration (existing phenomenological system)
- **Already Implemented**: Backend exists (see `twilio_handler.py`)
- **Integration**: Tauri app calls existing FastAPI backend

**Cloud Sync (Optional)**
- **Backend**: FastAPI (Python) — existing phenomenological evidence API extended
- **Storage**: PostgreSQL (server) + S3 (documents)
- **Sync Protocol**: Differential sync (only changed records), conflict resolution
- **Security**: E2EE (client encrypts before uploading)

---

## Database Schema

### Core Tables

#### clients
```sql
CREATE TABLE clients (
    id TEXT PRIMARY KEY,                    -- UUID
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    middle_name TEXT,
    date_of_birth TEXT NOT NULL,            -- ISO 8601 date
    ssn_encrypted BLOB NOT NULL,            -- Encrypted SSN
    phone TEXT,
    email TEXT,
    address_encrypted BLOB,                 -- Encrypted address
    nft_chain_id TEXT UNIQUE,               -- Reference to blockchain chain
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT                         -- Soft delete
);

CREATE INDEX idx_clients_last_name ON clients(last_name);
CREATE INDEX idx_clients_nft_chain ON clients(nft_chain_id);
```

#### cases
```sql
CREATE TABLE cases (
    id TEXT PRIMARY KEY,                    -- UUID
    client_id TEXT NOT NULL,
    case_number TEXT UNIQUE,
    case_type TEXT NOT NULL,                -- 'auto_accident', 'slip_fall', 'medical_malpractice', etc.
    status TEXT NOT NULL,                   -- 'intake', 'investigation', 'demand', 'litigation', 'settled', 'trial', 'closed'
    incident_date TEXT,                     -- Date of injury
    statute_of_limitations TEXT,            -- Calculated deadline
    assigned_attorney_id TEXT,
    assigned_paralegal_id TEXT,
    settlement_demand_amount REAL,
    settlement_actual_amount REAL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT,
    FOREIGN KEY (client_id) REFERENCES clients(id)
);

CREATE INDEX idx_cases_client ON cases(client_id);
CREATE INDEX idx_cases_status ON cases(status);
CREATE INDEX idx_cases_attorney ON cases(assigned_attorney_id);
```

#### medical_providers
```sql
CREATE TABLE medical_providers (
    id TEXT PRIMARY KEY,                    -- UUID
    name TEXT NOT NULL,
    specialty TEXT,
    address TEXT,
    phone TEXT,
    fax TEXT,
    email TEXT,
    is_favorite BOOLEAN DEFAULT FALSE,      -- Quick access for frequent providers
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX idx_providers_name ON medical_providers(name);
```

#### treatments
```sql
CREATE TABLE treatments (
    id TEXT PRIMARY KEY,                    -- UUID
    case_id TEXT NOT NULL,
    provider_id TEXT NOT NULL,
    date_of_service TEXT NOT NULL,          -- ISO 8601 date
    treatment_type TEXT,                    -- 'office_visit', 'surgery', 'pt', 'imaging', 'er', etc.
    diagnosis_codes TEXT,                   -- JSON array of ICD-10 codes
    procedure_codes TEXT,                   -- JSON array of CPT codes
    charges_amount REAL,
    notes_encrypted BLOB,                   -- Encrypted treatment notes
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (case_id) REFERENCES cases(id),
    FOREIGN KEY (provider_id) REFERENCES medical_providers(id)
);

CREATE INDEX idx_treatments_case ON treatments(case_id);
CREATE INDEX idx_treatments_date ON treatments(date_of_service);
```

#### records_requests
```sql
CREATE TABLE records_requests (
    id TEXT PRIMARY KEY,                    -- UUID
    case_id TEXT NOT NULL,
    provider_id TEXT NOT NULL,
    request_type TEXT NOT NULL,             -- 'medical_records', 'bills', 'imaging'
    sent_date TEXT,
    follow_up_date TEXT,
    received_date TEXT,
    status TEXT NOT NULL,                   -- 'pending', 'sent', 'partial', 'complete', 'denied'
    generated_document_id TEXT,             -- Link to generated request letter
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (case_id) REFERENCES cases(id),
    FOREIGN KEY (provider_id) REFERENCES medical_providers(id)
);

CREATE INDEX idx_requests_case ON records_requests(case_id);
CREATE INDEX idx_requests_status ON records_requests(status);
```

#### documents
```sql
CREATE TABLE documents (
    id TEXT PRIMARY KEY,                    -- UUID
    case_id TEXT,
    client_id TEXT,
    document_type TEXT NOT NULL,            -- 'request_letter', 'demand_letter', 'medical_record', 'contract', etc.
    file_path TEXT NOT NULL,                -- Path to file on disk
    file_hash TEXT NOT NULL,                -- SHA-256 hash for integrity
    blockchain_tx_hash TEXT,                -- Reference to blockchain transaction
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata TEXT,                          -- JSON metadata (original template, keywords used, etc.)
    FOREIGN KEY (case_id) REFERENCES cases(id),
    FOREIGN KEY (client_id) REFERENCES clients(id)
);

CREATE INDEX idx_documents_case ON documents(case_id);
CREATE INDEX idx_documents_type ON documents(document_type);
```

#### templates
```sql
CREATE TABLE templates (
    id TEXT PRIMARY KEY,                    -- UUID
    name TEXT NOT NULL,
    category TEXT NOT NULL,                 -- 'records_request', 'demand_letter', 'discovery', etc.
    content TEXT NOT NULL,                  -- Template content with {{keywords}}
    keywords TEXT NOT NULL,                 -- JSON array of keyword definitions
    is_system_template BOOLEAN DEFAULT FALSE, -- Built-in vs user-created
    created_by TEXT,                        -- User ID
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX idx_templates_category ON templates(category);
```

#### nft_chains
```sql
CREATE TABLE nft_chains (
    id TEXT PRIMARY KEY,                    -- Chain ID (UUID)
    client_id TEXT UNIQUE NOT NULL,
    blockchain_address TEXT,                -- NFT smart contract address
    latest_block_hash TEXT,                 -- Head of the chain
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (client_id) REFERENCES clients(id)
);
```

#### chain_entries
```sql
CREATE TABLE chain_entries (
    id TEXT PRIMARY KEY,                    -- Entry ID (UUID)
    chain_id TEXT NOT NULL,
    entry_type TEXT NOT NULL,               -- 'pii_update', 'document_created', 'pain_report', 'access_log'
    payload_hash TEXT NOT NULL,             -- SHA-256 of canonical payload
    previous_hash TEXT,                     -- Link to previous entry (Merkle chain)
    signature TEXT NOT NULL,                -- EdDSA signature
    timestamp TEXT NOT NULL,
    payload_encrypted BLOB,                 -- Optional encrypted payload for PII
    metadata TEXT,                          -- JSON metadata
    created_at TEXT NOT NULL,
    FOREIGN KEY (chain_id) REFERENCES nft_chains(id)
);

CREATE INDEX idx_chain_entries_chain ON chain_entries(chain_id);
CREATE INDEX idx_chain_entries_timestamp ON chain_entries(timestamp);
```

#### calendar_events
```sql
CREATE TABLE calendar_events (
    id TEXT PRIMARY KEY,                    -- UUID
    case_id TEXT,
    event_type TEXT NOT NULL,               -- 'court_date', 'appointment', 'deadline', 'follow_up'
    title TEXT NOT NULL,
    description TEXT,
    event_date TEXT NOT NULL,               -- ISO 8601 datetime
    reminder_offset_minutes INTEGER,        -- Notify X minutes before
    is_completed BOOLEAN DEFAULT FALSE,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (case_id) REFERENCES cases(id)
);

CREATE INDEX idx_calendar_case ON calendar_events(case_id);
CREATE INDEX idx_calendar_date ON calendar_events(event_date);
```

---

## Tauri Commands (IPC API)

### Client Management

```rust
#[tauri::command]
async fn create_client(
    client: CreateClientDto,
    state: tauri::State<'_, AppState>
) -> Result<Client, String>;

#[tauri::command]
async fn get_client(
    id: String,
    state: tauri::State<'_, AppState>
) -> Result<Client, String>;

#[tauri::command]
async fn update_client(
    id: String,
    updates: UpdateClientDto,
    state: tauri::State<'_, AppState>
) -> Result<Client, String>;

#[tauri::command]
async fn list_clients(
    filters: ClientFilters,
    state: tauri::State<'_, AppState>
) -> Result<Vec<ClientSummary>, String>;

#[tauri::command]
async fn search_clients(
    query: String,
    state: tauri::State<'_, AppState>
) -> Result<Vec<ClientSummary>, String>;
```

### Case Management

```rust
#[tauri::command]
async fn create_case(
    case: CreateCaseDto,
    state: tauri::State<'_, AppState>
) -> Result<Case, String>;

#[tauri::command]
async fn get_case(
    id: String,
    state: tauri::State<'_, AppState>
) -> Result<Case, String>;

#[tauri::command]
async fn update_case_status(
    id: String,
    status: CaseStatus,
    state: tauri::State<'_, AppState>
) -> Result<Case, String>;

#[tauri::command]
async fn get_case_timeline(
    case_id: String,
    state: tauri::State<'_, AppState>
) -> Result<Vec<TimelineEvent>, String>;
```

### Medical Records

```rust
#[tauri::command]
async fn add_treatment(
    treatment: CreateTreatmentDto,
    state: tauri::State<'_, AppState>
) -> Result<Treatment, String>;

#[tauri::command]
async fn create_records_request(
    request: CreateRecordsRequestDto,
    state: tauri::State<'_, AppState>
) -> Result<RecordsRequest, String>;

#[tauri::command]
async fn get_pending_requests(
    case_id: String,
    state: tauri::State<'_, AppState>
) -> Result<Vec<RecordsRequest>, String>;
```

### Document Generation

```rust
#[tauri::command]
async fn generate_document(
    template_id: String,
    case_id: String,
    keyword_overrides: HashMap<String, String>,
    state: tauri::State<'_, AppState>
) -> Result<GeneratedDocument, String>;

#[tauri::command]
async fn save_template(
    template: CreateTemplateDto,
    state: tauri::State<'_, AppState>
) -> Result<Template, String>;

#[tauri::command]
async fn get_template_keywords(
    template_id: String,
    case_id: String,
    state: tauri::State<'_, AppState>
) -> Result<HashMap<String, KeywordValue>, String>;
```

### Blockchain/NFT

```rust
#[tauri::command]
async fn init_client_chain(
    client_id: String,
    state: tauri::State<'_, AppState>
) -> Result<NftChain, String>;

#[tauri::command]
async fn add_chain_entry(
    chain_id: String,
    entry: CreateChainEntryDto,
    state: tauri::State<'_, AppState>
) -> Result<ChainEntry, String>;

#[tauri::command]
async fn verify_chain(
    chain_id: String,
    state: tauri::State<'_, AppState>
) -> Result<ChainVerificationResult, String>;

#[tauri::command]
async fn export_proof_bundle(
    chain_id: String,
    include_entries: Vec<String>,
    state: tauri::State<'_, AppState>
) -> Result<String, String>; // Returns path to generated proof JSON
```

### AI Assistance

```rust
#[tauri::command]
async fn suggest_template_content(
    prompt: String,
    template_type: String,
    state: tauri::State<'_, AppState>
) -> Result<String, String>;

#[tauri::command]
async fn analyze_demand_letter(
    document_id: String,
    state: tauri::State<'_, AppState>
) -> Result<DemandAnalysis, String>;
```

---

## Frontend Architecture

### Directory Structure

```
src-tauri/                       # Rust backend
├── src/
│   ├── main.rs                  # Tauri app entry point
│   ├── commands/                # Tauri command handlers
│   │   ├── mod.rs
│   │   ├── client.rs
│   │   ├── case.rs
│   │   ├── document.rs
│   │   ├── blockchain.rs
│   │   └── ai.rs
│   ├── db/                      # Database layer
│   │   ├── mod.rs
│   │   ├── connection.rs
│   │   ├── migrations.rs
│   │   └── models.rs
│   ├── crypto/                  # Cryptography services
│   │   ├── mod.rs
│   │   ├── encryption.rs
│   │   ├── signing.rs
│   │   └── hashing.rs
│   ├── blockchain/              # NFT/chain logic
│   │   ├── mod.rs
│   │   ├── chain.rs
│   │   └── verification.rs
│   ├── ai/                      # AI integration
│   │   ├── mod.rs
│   │   └── openai_client.rs
│   └── utils/
│       ├── mod.rs
│       └── file.rs
├── Cargo.toml
└── tauri.conf.json

src/                             # React frontend
├── main.tsx                     # App entry point
├── App.tsx                      # Root component
├── routes/                      # Page components
│   ├── Dashboard.tsx
│   ├── Clients/
│   │   ├── ClientList.tsx
│   │   ├── ClientDetail.tsx
│   │   └── ClientForm.tsx
│   ├── Cases/
│   │   ├── CaseList.tsx
│   │   ├── CaseDetail.tsx
│   │   └── CaseTimeline.tsx
│   ├── MedicalRecords/
│   │   ├── TreatmentList.tsx
│   │   ├── RecordsRequestDashboard.tsx
│   │   └── ProviderDirectory.tsx
│   ├── Documents/
│   │   ├── TemplateEditor.tsx
│   │   ├── DocumentGenerator.tsx
│   │   └── DocumentLibrary.tsx
│   ├── CarePlanner/
│   │   ├── MedicalChronology.tsx
│   │   ├── DamagesCalculator.tsx
│   │   └── ExhibitBuilder.tsx
│   └── Settings/
│       └── SettingsPage.tsx
├── components/                  # Reusable components
│   ├── ui/                      # shadcn components
│   ├── Layout/
│   │   ├── AppLayout.tsx
│   │   ├── Sidebar.tsx
│   │   └── Header.tsx
│   ├── Forms/
│   │   ├── ClientFormFields.tsx
│   │   └── DatePicker.tsx
│   └── DataDisplay/
│       ├── Timeline.tsx
│       └── DataTable.tsx
├── lib/                         # Utilities & hooks
│   ├── tauri.ts                 # Tauri command wrappers
│   ├── queries/                 # React Query hooks
│   │   ├── useClients.ts
│   │   ├── useCases.ts
│   │   └── useDocuments.ts
│   ├── stores/                  # Zustand stores
│   │   ├── authStore.ts
│   │   └── uiStore.ts
│   └── utils/
│       ├── dates.ts
│       └── formatting.ts
├── types/                       # TypeScript types
│   ├── client.ts
│   ├── case.ts
│   ├── document.ts
│   └── api.ts
└── styles/
    └── globals.css
```

### State Management Strategy

**Local UI State (Zustand)**
- User preferences (theme, sidebar collapsed)
- Modal open/closed states
- Form draft states (auto-save)

**Server State (TanStack Query)**
- All data from Tauri backend (clients, cases, documents)
- Caching strategy:
  - `staleTime`: 5 minutes (data considered fresh)
  - `cacheTime`: 30 minutes (data kept in cache)
  - Optimistic updates for mutations
- Query keys structure: `['clients', clientId]`, `['cases', caseId]`, etc.

**Form State (React Hook Form)**
- Validation with Zod schemas
- Automatic error handling
- Dirty state tracking

---

## Cryptography Architecture

### PII Encryption

**Approach**: Encrypt PII fields individually (not full records)

**Algorithm**: AES-256-GCM (via Fernet-like scheme)

**Key Hierarchy**:
1. **Master Key**: Derived from user password (Argon2)
2. **Data Encryption Keys (DEK)**: Per-client keys wrapped by master key
3. **Field Encryption**: Each PII field encrypted with DEK

**Benefits**:
- Key rotation without re-encrypting all data (just re-wrap DEKs)
- Per-client isolation (compromised DEK only affects one client)
- Searchable metadata (names/dates indexed, SSN encrypted)

### Blockchain Chain Construction

**Chain Structure** (same as existing system):
```
Entry 1: [payload_hash, signature, previous_hash=null]
   ↓
Entry 2: [payload_hash, signature, previous_hash=hash(Entry 1)]
   ↓
Entry 3: [payload_hash, signature, previous_hash=hash(Entry 2)]
```

**Entry Types**:
1. **PII_UPDATE**: Client data changed (encrypted payload)
2. **DOCUMENT_CREATED**: New document generated (hash + metadata)
3. **ACCESS_LOG**: PHI accessed (who, when, why)
4. **PAIN_REPORT**: SMS pain tracking entry (from phenomenological system)

**Verification**:
- Compute hash of each entry's payload
- Verify signature with public key
- Check previous_hash links to actual previous entry hash
- Any mismatch = chain tampered

---

## AI Integration Architecture

### OpenAI API Usage

**Use Cases**:
1. **Template Assistance**: "Write a medical records request for chiropractic treatment"
2. **Keyword Suggestion**: Analyze template, suggest missing keywords
3. **Document Drafting**: Generate demand letter sections from case data
4. **Quality Check**: Analyze demand for missing facts, weak arguments

**Implementation**:

**Rust Backend** (`src/ai/openai_client.rs`):
```rust
pub struct OpenAIClient {
    client: reqwest::Client,
    api_key: String,
}

impl OpenAIClient {
    pub async fn chat_completion(
        &self,
        messages: Vec<ChatMessage>,
        model: &str,
    ) -> Result<String, Error> {
        // Call OpenAI API
    }

    pub async fn suggest_template(
        &self,
        template_type: &str,
        user_prompt: &str,
    ) -> Result<String, Error> {
        let system_prompt = format!(
            "You are a legal document assistant. Generate a {} template with {{{{keyword}}}} placeholders.",
            template_type
        );
        // ...
    }
}
```

**Frontend Hook**:
```typescript
const useAISuggestion = () => {
  const suggest = async (prompt: string, templateType: string) => {
    return invoke<string>('suggest_template_content', {
      prompt,
      templateType,
    });
  };

  return { suggest };
};
```

**Cost Control**:
- User quota (X tokens/month)
- Local caching of suggestions (avoid re-generating same content)
- Option to use cheaper models (GPT-3.5) for simple tasks

---

## Blockchain Integration

### Polygon (Ethereum L2)

**Smart Contract** (Solidity):
```solidity
// ClientDataChain.sol
pragma solidity ^0.8.0;

contract ClientDataChain {
    struct ChainEntry {
        bytes32 payloadHash;
        bytes32 previousHash;
        uint256 timestamp;
        string metadata; // JSON
    }

    mapping(string => ChainEntry[]) public clientChains;

    event EntryAdded(
        string indexed clientId,
        bytes32 payloadHash,
        uint256 timestamp
    );

    function addEntry(
        string memory clientId,
        bytes32 payloadHash,
        bytes32 previousHash,
        string memory metadata
    ) public {
        clientChains[clientId].push(ChainEntry({
            payloadHash: payloadHash,
            previousHash: previousHash,
            timestamp: block.timestamp,
            metadata: metadata
        }));

        emit EntryAdded(clientId, payloadHash, block.timestamp);
    }

    function getChain(string memory clientId)
        public
        view
        returns (ChainEntry[] memory)
    {
        return clientChains[clientId];
    }
}
```

**Rust Integration** (`ethers-rs`):
```rust
use ethers::prelude::*;

pub struct BlockchainService {
    provider: Provider<Http>,
    contract: Contract<Http>,
    signer: LocalWallet,
}

impl BlockchainService {
    pub async fn add_entry(
        &self,
        client_id: &str,
        payload_hash: [u8; 32],
        previous_hash: [u8; 32],
        metadata: &str,
    ) -> Result<TransactionReceipt, Error> {
        let tx = self.contract
            .method::<_, ()>("addEntry", (
                client_id,
                payload_hash,
                previous_hash,
                metadata,
            ))?
            .send()
            .await?
            .await?;

        Ok(tx.expect("Transaction failed"))
    }
}
```

**Cost Optimization**:
- Batch entries (add 10 entries in one transaction)
- Off-chain storage (IPFS for large payloads, only hash on-chain)
- Lazy minting (only mint NFT when exporting proof, not every entry)

---

## Document Generation Pipeline

### Mail Merge Flow

1. **Template Selection**: User picks template (e.g., "Medical Records Request")
2. **Keyword Extraction**: Parse template for `{{KEYWORD}}` placeholders
3. **Data Binding**: Match keywords to case/client data
   - `{{CLIENT_NAME}}` → Decrypt from PII storage
   - `{{DOS_FIRST}}` → Query treatments table, get earliest date
   - `{{PROVIDER_NAME}}` → Lookup provider by ID
4. **AI Enhancement**: (Optional) User requests AI to expand sections
5. **Preview**: Show filled template in UI
6. **Generate**: Create final document
   - **Format**: DOCX (via Pandoc) or PDF (via printpdf)
   - **Hash**: SHA-256 of final file
   - **Blockchain**: Add entry to client's chain (hash + metadata)
7. **Save**: Store document in `~/Documents/Conatus/{ClientName}/{CaseNumber}/`

### Keyword System

**Keyword Definition**:
```typescript
interface Keyword {
  name: string;              // "CLIENT_NAME"
  description: string;       // "Client's full legal name"
  dataSource: string;        // "client.full_name"
  transform?: string;        // "uppercase" | "titlecase" | "date_format"
  fallback?: string;         // "[NAME NOT FOUND]"
}
```

**Built-in Keywords**:
- **Client**: `CLIENT_NAME`, `CLIENT_DOB`, `CLIENT_ADDRESS`, `CLIENT_SSN`
- **Case**: `CASE_NUMBER`, `INCIDENT_DATE`, `ATTORNEY_NAME`
- **Medical**: `PROVIDER_NAME`, `PROVIDER_ADDRESS`, `DOS_FIRST`, `DOS_LAST`, `DOS_LIST`
- **Dates**: `TODAY`, `CURRENT_YEAR`, `STATUTE_DEADLINE`

**AI Training**:
- User types: "Add a keyword for the client's age"
- AI suggests: `{{CLIENT_AGE}}` with data source `client.date_of_birth` + transform `age_from_dob`
- User confirms, keyword added to template

---

## Security & Compliance

### HIPAA Compliance

**Requirements**:
1. **Encryption at Rest**: All PHI encrypted (✓ Fernet/AES-256)
2. **Encryption in Transit**: HTTPS for any cloud sync (✓)
3. **Access Controls**: Role-based permissions (TODO)
4. **Audit Logs**: Track all PHI access (✓ Blockchain chain)
5. **Data Breach Notification**: Alert if unauthorized access detected (TODO)

**Audit Trail**:
- Every PII decryption logged to blockchain chain
- Entry type: `ACCESS_LOG`
- Metadata: `{user_id, action, field_accessed, timestamp, justification}`

### Code Signing

**Desktop App Distribution**:
- **Windows**: Sign with EV code signing certificate (avoid SmartScreen warnings)
- **macOS**: Sign with Apple Developer ID, notarize app
- **Linux**: GPG sign AppImage/Flatpak

**Auto-Update Security**:
- Sign update manifests with private key
- Tauri updater verifies signature before installing

---

## Testing Strategy

### Unit Tests

**Rust (Tauri Backend)**:
```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_encrypt_decrypt_pii() {
        let crypto = CryptoService::new(test_key());
        let plaintext = "123-45-6789";
        let encrypted = crypto.encrypt(plaintext).unwrap();
        let decrypted = crypto.decrypt(&encrypted).unwrap();
        assert_eq!(plaintext, decrypted);
    }

    #[test]
    fn test_chain_verification() {
        let chain = build_test_chain();
        assert!(verify_chain(&chain).is_ok());
    }
}
```

**TypeScript (Frontend)**:
```typescript
import { describe, it, expect } from 'vitest';
import { formatSSN } from '@/lib/utils/formatting';

describe('formatSSN', () => {
  it('formats SSN with dashes', () => {
    expect(formatSSN('123456789')).toBe('123-45-6789');
  });
});
```

### Integration Tests

**Tauri Commands**:
```rust
#[cfg(test)]
mod integration_tests {
    use tauri::test::mock_builder;

    #[tokio::test]
    async fn test_create_client_command() {
        let app = mock_builder().build().unwrap();
        let result = create_client(
            CreateClientDto { /* ... */ },
            app.state(),
        ).await;
        assert!(result.is_ok());
    }
}
```

### E2E Tests

**Playwright or Tauri WebDriver**:
```typescript
test('create new client and case', async ({ page }) => {
  await page.goto('/clients');
  await page.click('button:has-text("New Client")');
  await page.fill('input[name="firstName"]', 'John');
  await page.fill('input[name="lastName"]', 'Doe');
  await page.click('button:has-text("Save")');
  await expect(page.locator('text=John Doe')).toBeVisible();
});
```

---

## Deployment & Distribution

### Build Process

```bash
# Development
npm run tauri dev

# Production build
npm run tauri build

# Outputs:
# - Windows: .exe, .msi
# - macOS: .app, .dmg
# - Linux: .AppImage, .deb
```

### Auto-Update System

**Tauri Updater**:
1. App checks for updates on launch
2. Fetches update manifest from server (signed JSON)
3. Downloads new version (signature verified)
4. Prompts user to install
5. Silent background install (or restart required)

**Update Server**:
- Static file hosting (S3, GitHub Releases, Cloudflare R2)
- Manifest format:
  ```json
  {
    "version": "1.1.0",
    "notes": "Bug fixes and new features",
    "platforms": {
      "windows": {
        "signature": "...",
        "url": "https://releases.conatus.io/v1.1.0/Conatus_1.1.0_x64_en-US.msi"
      }
    }
  }
  ```

### Installation

**First-Run Setup**:
1. Create local database (`~/.conatus/conatus.db`)
2. Generate master encryption key (password-based)
3. Create default templates
4. Show onboarding wizard (optional)

**Data Location**:
- **Database**: `~/.conatus/conatus.db` (SQLite)
- **Documents**: `~/Documents/Conatus/` (organized by client/case)
- **Config**: `~/.conatus/config.toml`

---

## Performance Considerations

### Optimization Targets

- **App Launch**: < 2 seconds (cold start)
- **Client List Load**: < 100ms (1000 clients)
- **Document Generation**: < 3 seconds (complex demand letter)
- **Chain Verification**: < 500ms (1000 entries)
- **Search**: < 200ms (full-text across all clients/cases)

### Strategies

**Database**:
- Indexes on frequently queried columns (client name, case status, dates)
- Pagination for large lists (50 items per page)
- Lazy loading for detail views (fetch only when needed)

**Frontend**:
- Code splitting (React.lazy for routes)
- Virtual scrolling for long lists (react-window)
- Memoization (useMemo, React.memo) for expensive computations

**Tauri Commands**:
- Async all the things (tokio::spawn for parallelism)
- Batch operations (e.g., bulk import clients)
- Streaming for large datasets (tauri::api::stream)

---

## Future Considerations

### Cloud Sync Architecture

**Server Components**:
- **PostgreSQL**: Server-side database (superset of local SQLite schema)
- **S3**: Document storage (encrypted blobs)
- **FastAPI**: Sync API (reuse existing phenomenological backend)

**Sync Protocol**:
1. Client tracks `updated_at` timestamps
2. On sync: `POST /sync` with last sync timestamp
3. Server returns changed records since timestamp
4. Client merges changes (conflict resolution: last-write-wins or manual)

**Conflict Resolution**:
- Optimistic: Assume no conflicts, use timestamps
- Pessimistic: Lock records during edit (requires server)
- Manual: Show diff UI, let user choose

### Mobile App

**React Native** (share frontend code):
- Read-only view of cases (no editing on mobile)
- Document viewer
- Pain tracking (integrate with SMS system)
- Push notifications for deadlines

### Integrations

**EHR Systems**:
- Import treatment data from Epic, Cerner, Athenahealth
- Standard: HL7 FHIR API

**E-Filing**:
- Export documents to court e-filing systems (Tyler Technologies, File & ServeXpress)

**Billing**:
- Track time spent on cases (integrate with QuickBooks, Xero)

---

## Conclusion

This architecture provides a **solid foundation** for building Conatus:

✓ **Local-first** (fast, private, offline-capable)
✓ **Secure** (encryption, blockchain audit trails)
✓ **Extensible** (modular, API-first)
✓ **Modern** (Tauri, React, TypeScript, Rust)
✓ **Scalable** (cloud sync optional, handles thousands of cases)

**Next Steps**:
1. Set up Tauri project skeleton
2. Implement database layer (SQLite + migrations)
3. Build basic CRUD for clients/cases
4. Prototype mail merge system
5. Integrate blockchain (start with local chain, add Polygon later)

---

*Document Version: 1.0*
*Last Updated: 2025-11-23*
*Author: Conatus Team*
