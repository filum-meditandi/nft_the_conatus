# AI-Powered Mail Merge System

## Overview

The Conatus AI Mail Merge system transforms document generation for plaintiff attorneys by combining **traditional mail merge** (keyword-based templating) with **AI assistance** (intelligent drafting, gap analysis, template creation). This is not just "find and replace"—it's an intelligent document assistant that learns from user preferences and ensures accuracy.

---

## Core Principles

### 1. User Control
- AI **suggests**, user **decides**
- Templates are user-editable (not locked vendor templates)
- Always show what data will be inserted (preview before generation)

### 2. Data Security
- PII pulled from blockchain-secured storage
- Access logged (HIPAA compliance)
- Generated documents added to blockchain chain (tamper-evident)

### 3. Accuracy First
- Warn user if keywords can't be filled
- Fact-check against case data (e.g., "demand amount exceeds medical bills—is this intentional?")
- Version control for templates (revert if needed)

### 4. Learning System
- AI learns from user edits ("user always changes this phrase—suggest it next time")
- Community template sharing (opt-in)
- Feedback loop ("this template worked well / needs improvement")

---

## System Architecture

### High-Level Flow

```
┌──────────────┐
│ User selects │
│  template    │
└──────┬───────┘
       ↓
┌──────────────────────────────────────────┐
│  Template Parser                         │
│  - Extract {{KEYWORDS}}                  │
│  - Identify required vs. optional fields │
└──────┬───────────────────────────────────┘
       ↓
┌──────────────────────────────────────────┐
│  Data Binder                             │
│  - Match keywords to case/client data    │
│  - Decrypt PII from blockchain (logged)  │
│  - Calculate derived values              │
└──────┬───────────────────────────────────┘
       ↓
┌──────────────────────────────────────────┐
│  AI Enhancement (Optional)               │
│  - Suggest missing sections              │
│  - Improve phrasing                      │
│  - Fill "AI_SUGGEST_..." keywords        │
└──────┬───────────────────────────────────┘
       ↓
┌──────────────────────────────────────────┐
│  Preview & Edit                          │
│  - Show filled template                  │
│  - User reviews and modifies             │
│  - Warnings for missing/suspicious data  │
└──────┬───────────────────────────────────┘
       ↓
┌──────────────────────────────────────────┐
│  Document Generation                     │
│  - Render as DOCX or PDF                 │
│  - Compute file hash                     │
│  - Add to blockchain chain               │
│  - Save to disk                          │
└──────────────────────────────────────────┘
```

---

## Keyword System

### Keyword Structure

```typescript
interface Keyword {
  name: string;                  // "CLIENT_NAME"
  description: string;           // "Client's full legal name"
  category: KeywordCategory;     // "client" | "case" | "medical" | "computed"
  dataSource: string;            // "client.full_name" (dot notation for nested fields)
  transform?: Transform;         // Optional transformation
  required: boolean;             // Warn if missing
  pii: boolean;                  // Log access if true
  fallback?: string;             // Default value if not found
}

type Transform =
  | "uppercase"
  | "lowercase"
  | "titlecase"
  | "date_format_mdy"
  | "date_format_full"
  | "currency"
  | "age_from_dob"
  | "phone_format";
```

### Built-in Keywords

#### Client Keywords
```typescript
{
  "CLIENT_NAME": {
    name: "CLIENT_NAME",
    description: "Client's full legal name (First Middle Last)",
    category: "client",
    dataSource: "client.full_name",
    required: true,
    pii: false,
  },
  "CLIENT_FIRST_NAME": {
    name: "CLIENT_FIRST_NAME",
    description: "Client's first name",
    category: "client",
    dataSource: "client.first_name",
    required: false,
    pii: false,
  },
  "CLIENT_DOB": {
    name: "CLIENT_DOB",
    description: "Client's date of birth",
    category: "client",
    dataSource: "client.date_of_birth",
    transform: "date_format_mdy",
    required: false,
    pii: true, // Log access
  },
  "CLIENT_SSN": {
    name: "CLIENT_SSN",
    description: "Client's Social Security Number",
    category: "client",
    dataSource: "client.ssn_encrypted",
    required: false,
    pii: true,
    fallback: "XXX-XX-XXXX",
  },
  "CLIENT_ADDRESS": {
    name: "CLIENT_ADDRESS",
    description: "Client's full address",
    category: "client",
    dataSource: "client.address_encrypted",
    required: false,
    pii: true,
  },
  "CLIENT_AGE": {
    name: "CLIENT_AGE",
    description: "Client's current age (computed from DOB)",
    category: "computed",
    dataSource: "client.date_of_birth",
    transform: "age_from_dob",
    required: false,
    pii: false,
  },
}
```

#### Case Keywords
```typescript
{
  "CASE_NUMBER": {
    name: "CASE_NUMBER",
    description: "Case file number",
    category: "case",
    dataSource: "case.case_number",
    required: true,
    pii: false,
  },
  "INCIDENT_DATE": {
    name: "INCIDENT_DATE",
    description: "Date of incident/injury",
    category: "case",
    dataSource: "case.incident_date",
    transform: "date_format_full",
    required: true,
    pii: false,
  },
  "ATTORNEY_NAME": {
    name: "ATTORNEY_NAME",
    description: "Assigned attorney's name",
    category: "case",
    dataSource: "case.assigned_attorney.full_name",
    required: false,
    pii: false,
  },
  "DEMAND_AMOUNT": {
    name: "DEMAND_AMOUNT",
    description: "Settlement demand amount",
    category: "case",
    dataSource: "case.settlement_demand_amount",
    transform: "currency",
    required: false,
    pii: false,
  },
}
```

#### Medical Keywords
```typescript
{
  "PROVIDER_NAME": {
    name: "PROVIDER_NAME",
    description: "Medical provider's name (context-specific)",
    category: "medical",
    dataSource: "context.provider.name", // Set by user when generating
    required: true,
    pii: false,
  },
  "PROVIDER_ADDRESS": {
    name: "PROVIDER_ADDRESS",
    description: "Medical provider's full address",
    category: "medical",
    dataSource: "context.provider.address",
    required: false,
    pii: false,
  },
  "DOS_FIRST": {
    name: "DOS_FIRST",
    description: "First date of service (earliest treatment)",
    category: "computed",
    dataSource: "treatments.min(date_of_service)",
    transform: "date_format_mdy",
    required: false,
    pii: false,
  },
  "DOS_LAST": {
    name: "DOS_LAST",
    description: "Last date of service (most recent treatment)",
    category: "computed",
    dataSource: "treatments.max(date_of_service)",
    transform: "date_format_mdy",
    required: false,
    pii: false,
  },
  "DOS_LIST": {
    name: "DOS_LIST",
    description: "Comma-separated list of all treatment dates",
    category: "computed",
    dataSource: "treatments.all(date_of_service)",
    transform: "date_list",
    required: false,
    pii: false,
  },
  "TOTAL_MEDICAL_BILLS": {
    name: "TOTAL_MEDICAL_BILLS",
    description: "Sum of all medical charges",
    category: "computed",
    dataSource: "treatments.sum(charges_amount)",
    transform: "currency",
    required: false,
    pii: false,
  },
}
```

#### Date Keywords
```typescript
{
  "TODAY": {
    name: "TODAY",
    description: "Current date",
    category: "computed",
    dataSource: "system.current_date",
    transform: "date_format_full",
    required: false,
    pii: false,
  },
  "CURRENT_YEAR": {
    name: "CURRENT_YEAR",
    description: "Current year (YYYY)",
    category: "computed",
    dataSource: "system.current_year",
    required: false,
    pii: false,
  },
}
```

### Custom Keywords

Users can define custom keywords:

```typescript
// Example: Create keyword for "months since incident"
{
  "MONTHS_SINCE_INCIDENT": {
    name: "MONTHS_SINCE_INCIDENT",
    description: "Number of months since incident date",
    category: "computed",
    dataSource: "case.incident_date",
    transform: "months_from_date_to_now",
    required: false,
    pii: false,
  }
}
```

---

## Template System

### Template Structure

```typescript
interface Template {
  id: string;                      // UUID
  name: string;                    // "Medical Records Request - Chiropractic"
  category: TemplateCategory;      // "records_request" | "demand_letter" | etc.
  content: string;                 // Template body (Markdown or HTML)
  keywords: Keyword[];             // Keywords used in this template
  metadata: TemplateMetadata;
  createdBy?: string;              // User ID
  isSystemTemplate: boolean;       // Built-in vs user-created
  version: number;                 // Template versioning
}

interface TemplateMetadata {
  description: string;
  usageCount: number;
  lastUsed?: string;
  tags: string[];
  documentType: "docx" | "pdf";
}
```

### Template Example: Medical Records Request

```markdown
{
  "name": "Medical Records Request - General",
  "category": "records_request",
  "content": """
{{ATTORNEY_FIRM_LETTERHEAD}}

{{TODAY}}

{{PROVIDER_NAME}}
{{PROVIDER_ADDRESS}}

Re: **{{CLIENT_NAME}}** (DOB: {{CLIENT_DOB}})
Authorization for Release of Medical Records

Dear Records Custodian:

Our office represents **{{CLIENT_NAME}}** in connection with injuries sustained on **{{INCIDENT_DATE}}**. We are writing to request a complete copy of all medical records for the above-named patient.

**Patient Information:**
- Name: {{CLIENT_NAME}}
- Date of Birth: {{CLIENT_DOB}}
- Social Security Number: {{CLIENT_SSN}}
- Address: {{CLIENT_ADDRESS}}

**Records Requested:**
Please provide all medical records, including but not limited to:
- Office visit notes
- Diagnostic test results
- Imaging reports and films
- Treatment plans
- Billing statements

**Date Range:**
From {{DOS_FIRST}} through {{DOS_LAST}} (and continuing).

Enclosed is a signed HIPAA authorization from {{CLIENT_NAME}}.

Please send the requested records to:

{{ATTORNEY_NAME}}
{{ATTORNEY_FIRM_NAME}}
{{ATTORNEY_ADDRESS}}
{{ATTORNEY_PHONE}}
{{ATTORNEY_EMAIL}}

If there are any copying fees, please notify us in advance. Thank you for your prompt attention to this matter.

Sincerely,

{{ATTORNEY_SIGNATURE}}
{{ATTORNEY_NAME}}, Esq.

Enclosure: HIPAA Authorization
  """,
  "keywords": [
    "CLIENT_NAME", "CLIENT_DOB", "CLIENT_SSN", "CLIENT_ADDRESS",
    "PROVIDER_NAME", "PROVIDER_ADDRESS",
    "INCIDENT_DATE", "DOS_FIRST", "DOS_LAST",
    "ATTORNEY_NAME", "ATTORNEY_FIRM_NAME", "ATTORNEY_ADDRESS",
    "TODAY"
  ]
}
```

### AI-Enhanced Templates

Templates can include **AI placeholders** for dynamic content:

```markdown
## Settlement Demand: {{DEMAND_AMOUNT}}

### Liability

{{AI_SUGGEST_LIABILITY}}
<!-- AI will generate liability section based on case facts -->

### Medical Treatment Summary

{{CLIENT_NAME}} sustained injuries on {{INCIDENT_DATE}} and has undergone the following treatment:

{{AI_SUMMARIZE_TREATMENTS}}
<!-- AI will summarize treatment timeline from database -->

### Damages

**Economic Damages:**
- Medical expenses (past): {{TOTAL_MEDICAL_BILLS}}
- Medical expenses (future): {{AI_ESTIMATE_FUTURE_MEDICAL}}
- Lost wages: {{TOTAL_LOST_WAGES}}

**Non-Economic Damages:**
{{AI_DRAFT_PAIN_AND_SUFFERING}}
<!-- AI drafts pain and suffering narrative from phenomenological pain reports -->
```

---

## AI Integration

### OpenAI API Usage

**Use Cases**:

1. **Template Creation**: "Write a template for requesting imaging records"
2. **Content Generation**: Fill `{{AI_SUGGEST_...}}` placeholders
3. **Gap Analysis**: "This demand letter is missing causation analysis"
4. **Quality Improvement**: "Suggest more persuasive phrasing for damages section"

### Implementation

**Rust Backend** (`src/ai/openai_client.rs`):

```rust
use serde::{Deserialize, Serialize};

pub struct OpenAIClient {
    client: reqwest::Client,
    api_key: String,
}

#[derive(Serialize)]
struct ChatRequest {
    model: String,
    messages: Vec<ChatMessage>,
    temperature: f32,
}

#[derive(Serialize, Deserialize)]
struct ChatMessage {
    role: String, // "system" | "user" | "assistant"
    content: String,
}

impl OpenAIClient {
    pub async fn suggest_template(
        &self,
        template_type: &str,
        user_prompt: &str,
    ) -> Result<String, Error> {
        let system_prompt = format!(
            "You are a legal document assistant for plaintiff personal injury attorneys. \
            Generate a {} template with {{{{keyword}}}} placeholders for dynamic content. \
            Use professional legal language. Include all necessary boilerplate.",
            template_type
        );

        let messages = vec![
            ChatMessage {
                role: "system".to_string(),
                content: system_prompt,
            },
            ChatMessage {
                role: "user".to_string(),
                content: user_prompt.to_string(),
            },
        ];

        let response = self.client
            .post("https://api.openai.com/v1/chat/completions")
            .header("Authorization", format!("Bearer {}", self.api_key))
            .json(&ChatRequest {
                model: "gpt-4-turbo".to_string(),
                messages,
                temperature: 0.7,
            })
            .send()
            .await?
            .json::<ChatResponse>()
            .await?;

        Ok(response.choices[0].message.content.clone())
    }

    pub async fn fill_ai_placeholder(
        &self,
        placeholder: &str,
        case_context: &CaseContext,
    ) -> Result<String, Error> {
        let prompt = match placeholder {
            "AI_SUGGEST_LIABILITY" => {
                format!(
                    "Write a liability analysis for a {} case that occurred on {}. \
                    Incident details: {}. Be specific and persuasive.",
                    case_context.case_type,
                    case_context.incident_date,
                    case_context.incident_description.as_deref().unwrap_or("(no details provided)")
                )
            }
            "AI_SUMMARIZE_TREATMENTS" => {
                let treatments_summary = case_context.treatments.iter()
                    .map(|t| format!("- {} on {} at {}", t.treatment_type, t.date_of_service, t.provider_name))
                    .collect::<Vec<_>>()
                    .join("\n");

                format!(
                    "Summarize the following medical treatment timeline in 2-3 paragraphs \
                    for a demand letter. Be concise but thorough:\n\n{}",
                    treatments_summary
                )
            }
            "AI_DRAFT_PAIN_AND_SUFFERING" => {
                let pain_reports = case_context.pain_reports.iter()
                    .map(|p| format!("{}: Pain level {} - {}", p.date, p.level, p.description))
                    .collect::<Vec<_>>()
                    .join("\n");

                format!(
                    "Draft a pain and suffering narrative based on these pain reports:\n\n{}\n\n\
                    Use vivid but professional language. Emphasize impact on daily life.",
                    pain_reports
                )
            }
            _ => return Err(Error::UnknownPlaceholder(placeholder.to_string())),
        };

        let messages = vec![
            ChatMessage {
                role: "system".to_string(),
                content: "You are a legal writing assistant. Generate professional, persuasive content for demand letters.".to_string(),
            },
            ChatMessage {
                role: "user".to_string(),
                content: prompt,
            },
        ];

        let response = self.client
            .post("https://api.openai.com/v1/chat/completions")
            .header("Authorization", format!("Bearer {}", self.api_key))
            .json(&ChatRequest {
                model: "gpt-4-turbo".to_string(),
                messages,
                temperature: 0.8, // Slightly higher for more creative writing
            })
            .send()
            .await?
            .json::<ChatResponse>()
            .await?;

        Ok(response.choices[0].message.content.clone())
    }
}
```

**Tauri Command**:

```rust
#[tauri::command]
async fn ai_fill_placeholder(
    placeholder: String,
    case_id: String,
    state: tauri::State<'_, AppState>,
) -> Result<String, String> {
    // 1. Fetch case context
    let case_context = db::get_case_context(&state.db, &case_id)
        .await
        .map_err(|e| e.to_string())?;

    // 2. Call OpenAI
    let content = state.ai_client
        .fill_ai_placeholder(&placeholder, &case_context)
        .await
        .map_err(|e| e.to_string())?;

    Ok(content)
}
```

### Frontend Hook

```typescript
import { invoke } from '@tauri-apps/api/tauri';

export const useAIMailMerge = () => {
  const fillPlaceholder = async (
    placeholder: string,
    caseId: string
  ): Promise<string> => {
    return invoke<string>('ai_fill_placeholder', {
      placeholder,
      caseId,
    });
  };

  const suggestTemplate = async (
    templateType: string,
    prompt: string
  ): Promise<string> => {
    return invoke<string>('suggest_template_content', {
      templateType,
      prompt,
    });
  };

  return { fillPlaceholder, suggestTemplate };
};
```

### AI Training (Learning from Edits)

**Track User Edits**:

```typescript
// When user generates document, save:
{
  "template_id": "tpl_001",
  "ai_suggestions": {
    "AI_SUGGEST_LIABILITY": "Original AI text...",
    "AI_DRAFT_PAIN_AND_SUFFERING": "Original AI text..."
  },
  "user_edits": {
    "AI_SUGGEST_LIABILITY": "User's modified text...",
    "AI_DRAFT_PAIN_AND_SUFFERING": "User's modified text..."
  },
  "feedback": {
    "AI_SUGGEST_LIABILITY": { "helpful": true, "rating": 4 },
    "AI_DRAFT_PAIN_AND_SUFFERING": { "helpful": false, "rating": 2 }
  }
}
```

**Improve Over Time**:
- Periodically fine-tune prompts based on user edits
- Show "frequently edited" warnings ("Users often change this section—review carefully")
- Surface top-rated AI suggestions as template examples

---

## Document Generation Pipeline

### Step-by-Step Flow

#### 1. Template Selection

```typescript
// User selects template from library
const template = await invoke<Template>('get_template', {
  templateId: 'tpl_medical_request',
});
```

#### 2. Keyword Extraction & Binding

```rust
#[tauri::command]
async fn get_template_keywords(
    template_id: String,
    case_id: String,
    context: Option<HashMap<String, String>>, // e.g., {"provider_id": "prov_123"}
    state: tauri::State<'_, AppState>,
) -> Result<HashMap<String, KeywordValue>, String> {
    let template = db::get_template(&state.db, &template_id).await?;
    let case = db::get_case(&state.db, &case_id).await?;
    let client = db::get_client(&state.db, &case.client_id).await?;

    let mut keyword_values = HashMap::new();

    for keyword in &template.keywords {
        let value = match keyword.data_source.as_str() {
            "client.full_name" => client.full_name.clone(),
            "client.date_of_birth" => client.date_of_birth.clone(),
            "client.ssn_encrypted" => {
                // Decrypt PII (and log access)
                let ssn = decrypt_pii(
                    &client.ssn_encrypted,
                    &state.crypto,
                    &format!("Template generation: {}", template.name),
                ).await?;
                log_pii_access(&state.db, &client.id, "ssn", "template_generation").await?;
                ssn
            }
            "case.incident_date" => case.incident_date.clone().unwrap_or_default(),
            "treatments.min(date_of_service)" => {
                db::get_first_treatment_date(&state.db, &case_id).await?
            }
            "treatments.sum(charges_amount)" => {
                db::sum_medical_bills(&state.db, &case_id).await?.to_string()
            }
            "context.provider.name" => {
                context.get("provider_id")
                    .and_then(|id| db::get_provider_name(&state.db, id).await.ok())
                    .unwrap_or_default()
            }
            _ => String::new(),
        };

        // Apply transform
        let transformed = apply_transform(&value, &keyword.transform)?;

        keyword_values.insert(keyword.name.clone(), KeywordValue {
            value: transformed,
            source: keyword.data_source.clone(),
            pii: keyword.pii,
            found: !value.is_empty(),
        });
    }

    Ok(keyword_values)
}
```

#### 3. AI Enhancement (Optional)

```typescript
// If template has AI placeholders, fill them
const aiPlaceholders = ['AI_SUGGEST_LIABILITY', 'AI_SUMMARIZE_TREATMENTS'];

for (const placeholder of aiPlaceholders) {
  const content = await fillPlaceholder(placeholder, caseId);
  keywordValues[placeholder] = { value: content, found: true };
}
```

#### 4. Preview & Edit

```typescript
// Show preview in UI
const preview = renderTemplate(template.content, keywordValues);

// User reviews, makes manual edits
const userEdits = await showPreviewModal(preview);

// Merge user edits with AI suggestions
const finalContent = applyUserEdits(preview, userEdits);
```

#### 5. Generate Document

```rust
#[tauri::command]
async fn generate_document(
    template_id: String,
    case_id: String,
    filled_content: String,
    output_format: String, // "docx" | "pdf"
    state: tauri::State<'_, AppState>,
) -> Result<GeneratedDocument, String> {
    // 1. Convert to target format (using Pandoc or Rust lib)
    let file_path = match output_format.as_str() {
        "docx" => generate_docx(&filled_content).await?,
        "pdf" => generate_pdf(&filled_content).await?,
        _ => return Err("Invalid format".to_string()),
    };

    // 2. Compute file hash
    let file_hash = compute_file_hash(&file_path)?;

    // 3. Add to blockchain chain
    let chain_entry = add_chain_entry(
        &state.db,
        &case_id,
        ChainEntry {
            entry_type: EntryType::DocumentCreated,
            metadata: json!({
                "template_id": template_id,
                "case_id": case_id,
                "file_name": file_path.file_name(),
                "file_hash": file_hash,
                "output_format": output_format,
            }),
            // ...
        },
    ).await?;

    // 4. Save document record
    let document = db::create_document(
        &state.db,
        Document {
            id: Uuid::new_v4().to_string(),
            case_id,
            document_type: "generated".to_string(),
            file_path: file_path.to_string(),
            file_hash,
            blockchain_tx_hash: chain_entry.id,
            // ...
        },
    ).await?;

    Ok(GeneratedDocument {
        id: document.id,
        file_path,
        file_hash,
        chain_entry_id: chain_entry.id,
    })
}
```

#### 6. Save & Track

```rust
// Save to disk (organized by client/case)
// ~/Documents/Conatus/John_Doe/Case_12345/Records_Request_2025-11-23.pdf

// Add to database
// documents table (id, case_id, file_path, file_hash, created_at)

// Log in blockchain chain
// Entry type: DOCUMENT_CREATED
// Metadata: {template_id, file_hash, keywords_used}
```

---

## User Interface

### Template Editor

**Features**:
- Markdown/rich text editor
- Keyword insertion button (autocomplete)
- Live preview
- AI assistant sidebar ("Suggest section for...")
- Version history (revert to previous versions)

**UI Mockup**:
```
┌─────────────────────────────────────────────────────────────┐
│ Template Editor: Medical Records Request                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  [Template Name: _______________]  [Category: ▼]            │
│                                                             │
│  ┌─────────────────────────┬─────────────────────────────┐ │
│  │ Editor                  │ AI Assistant                │ │
│  │                         │                             │ │
│  │ {{ATTORNEY_LETTERHEAD}} │ 💡 Suggestions:             │ │
│  │                         │                             │ │
│  │ {{TODAY}}               │ • Add {{PROVIDER_FAX}}      │ │
│  │                         │   for fax transmission      │ │
│  │ {{PROVIDER_NAME}}       │                             │ │
│  │ {{PROVIDER_ADDRESS}}    │ • Consider adding a         │ │
│  │                         │   follow-up date reminder   │ │
│  │ Re: {{CLIENT_NAME}}     │                             │ │
│  │     (DOB: {{CLIENT_DOB}}│ [Ask AI...]                 │ │
│  │                         │                             │ │
│  │ Dear Records Custodian, │ Keywords Used:              │ │
│  │                         │ ☑ CLIENT_NAME               │ │
│  │ Our office represents...│ ☑ CLIENT_DOB                │ │
│  │                         │ ☑ PROVIDER_NAME             │ │
│  │ [Insert Keyword ▼]      │ ☐ CLIENT_SSN (optional)     │ │
│  │                         │                             │ │
│  └─────────────────────────┴─────────────────────────────┘ │
│                                                             │
│  [Save Template]  [Preview]  [Test with Case...]           │
└─────────────────────────────────────────────────────────────┘
```

### Document Generator

**UI Mockup**:
```
┌─────────────────────────────────────────────────────────────┐
│ Generate Document                                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Step 1: Select Template                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ ○ Medical Records Request - General                │   │
│  │ ○ Medical Records Request - Imaging                 │   │
│  │ ● Demand Letter - Auto Accident                     │   │
│  │ ○ Discovery Responses                               │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Step 2: Select Case                                       │
│  [Search cases... ▼] → Case #12345: John Doe v. Smith     │
│                                                             │
│  Step 3: Provide Context (if needed)                       │
│  Provider: [Select provider ▼] → Dr. Sarah Johnson         │
│                                                             │
│  Step 4: Review Keywords                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ ✓ CLIENT_NAME: John Michael Doe                     │   │
│  │ ✓ INCIDENT_DATE: January 15, 2024                   │   │
│  │ ⚠ DEMAND_AMOUNT: (not set) [Edit]                   │   │
│  │ ✓ TOTAL_MEDICAL_BILLS: $45,230.00                   │   │
│  │ ✓ AI_SUGGEST_LIABILITY: (will generate)             │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  [Cancel]  [Preview Document] → [Generate PDF ▼]           │
└─────────────────────────────────────────────────────────────┘
```

### Preview Modal

```
┌─────────────────────────────────────────────────────────────┐
│ Preview: Demand Letter                             [✕ Close]│
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  [Edit Mode ▼]  [Export PDF]  [Export DOCX]                │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ Smith & Associates Law Firm                          │ │
│  │ 123 Main Street, Anytown, USA                        │ │
│  │                                                       │ │
│  │ November 23, 2025                                    │ │
│  │                                                       │ │
│  │ Defendant's Insurance Company                        │ │
│  │ Claims Department                                    │ │
│  │                                                       │ │
│  │ Re: Settlement Demand - John Michael Doe             │ │
│  │     Incident Date: January 15, 2024                  │ │
│  │                                                       │ │
│  │ Dear Claims Adjuster:                                │ │
│  │                                                       │ │
│  │ This office represents John Michael Doe in          │ │
│  │ connection with injuries sustained in an automobile  │ │
│  │ collision on January 15, 2024.                       │ │
│  │                                                       │ │
│  │ DEMAND: $250,000.00                                  │ │
│  │                                                       │ │
│  │ [Edit this section ✏]                               │ │
│  │ ...                                                   │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
│  ⚠ Warnings:                                               │
│  • DEMAND_AMOUNT ($250,000) exceeds 5x medical bills       │
│    ($45,230). Ensure strong pain/suffering justification.  │
│                                                             │
│  [Generate Final Document]                                 │
└─────────────────────────────────────────────────────────────┘
```

---

## Quality Assurance Features

### 1. Missing Data Warnings

```typescript
// Before generating, check for missing required keywords
const warnings: Warning[] = [];

for (const keyword of template.keywords) {
  if (keyword.required && !keywordValues[keyword.name]?.found) {
    warnings.push({
      severity: 'error',
      message: `Required keyword ${keyword.name} is missing. Please provide this data before generating.`,
    });
  }
}

if (warnings.some(w => w.severity === 'error')) {
  // Block generation until resolved
}
```

### 2. Fact-Checking

```rust
// Example: Check if demand amount is reasonable
fn validate_demand_amount(
    demand: f64,
    medical_bills: f64,
) -> Vec<ValidationWarning> {
    let mut warnings = vec![];

    if demand < medical_bills {
        warnings.push(ValidationWarning {
            severity: Severity::Error,
            message: format!(
                "Demand (${:.2}) is LESS than medical bills (${:.2}). This is likely an error.",
                demand, medical_bills
            ),
        });
    }

    if demand > medical_bills * 10.0 {
        warnings.push(ValidationWarning {
            severity: Severity::Warning,
            message: format!(
                "Demand (${:.2}) is >10x medical bills (${:.2}). Ensure strong justification for non-economic damages.",
                demand, medical_bills
            ),
        });
    }

    warnings
}
```

### 3. Completeness Score

```typescript
interface CompletenessReport {
  score: number; // 0-100
  missingElements: string[];
  suggestions: string[];
}

function analyzeDocumentCompleteness(
  documentType: string,
  content: string
): CompletenessReport {
  const requiredSections = getRequiredSections(documentType);

  // Check for presence of each section
  const missingSections = requiredSections.filter(
    section => !content.includes(section.heading)
  );

  const score = ((requiredSections.length - missingSections.length) /
    requiredSections.length) * 100;

  return {
    score,
    missingElements: missingSections.map(s => s.heading),
    suggestions: missingSections.map(s => s.suggestion),
  };
}

// Example for demand letter:
const requiredSections = [
  { heading: 'Liability', suggestion: 'Add liability analysis section' },
  { heading: 'Medical Treatment', suggestion: 'Summarize medical treatment' },
  { heading: 'Damages', suggestion: 'Break down economic and non-economic damages' },
  { heading: 'Settlement Demand', suggestion: 'State demand amount clearly' },
];
```

---

## Security & Privacy

### PII Access Logging

Every time a PII keyword is accessed during document generation:

```rust
async fn log_pii_access(
    db: &Database,
    client_id: &str,
    field: &str,
    reason: &str,
) -> Result<(), Error> {
    add_chain_entry(
        db,
        client_id,
        ChainEntry {
            entry_type: EntryType::AccessLog,
            metadata: json!({
                "field": field,
                "accessed_by": "current_user_id",
                "reason": reason,
                "timestamp": Utc::now().to_rfc3339(),
            }),
            // ...
        },
    ).await
}
```

### Document Hash Storage

```rust
// After generating document, add to blockchain chain
{
  "entry_type": "DOCUMENT_CREATED",
  "metadata": {
    "file_name": "Demand_Letter_2025-11-23.pdf",
    "file_hash": "a3f5b2c1d4e6...",
    "template_id": "tpl_demand_auto",
    "keywords_used": ["CLIENT_NAME", "DEMAND_AMOUNT", "AI_SUGGEST_LIABILITY"]
  }
}
```

If document is ever modified:
- New hash computed
- New chain entry: `DOCUMENT_MODIFIED`
- Change summary logged
- Original version preserved

---

## Performance Optimization

### Caching Strategy

```typescript
// Cache AI responses (avoid regenerating same content)
const aiCache = new Map<string, { content: string; timestamp: number }>();

async function fillPlaceholderWithCache(
  placeholder: string,
  caseId: string
): Promise<string> {
  const cacheKey = `${placeholder}_${caseId}`;

  // Check cache (valid for 1 hour)
  const cached = aiCache.get(cacheKey);
  if (cached && Date.now() - cached.timestamp < 3600000) {
    return cached.content;
  }

  // Generate new content
  const content = await fillPlaceholder(placeholder, caseId);

  // Cache it
  aiCache.set(cacheKey, { content, timestamp: Date.now() });

  return content;
}
```

### Batch Processing

```rust
// If generating 10 medical records requests for different providers,
// batch the AI calls to reduce latency
async fn batch_generate_documents(
    template_id: String,
    case_id: String,
    providers: Vec<String>,
    state: tauri::State<'_, AppState>,
) -> Result<Vec<GeneratedDocument>, String> {
    // Fetch case data once
    let case_context = db::get_case_context(&state.db, &case_id).await?;

    // Generate all documents in parallel
    let futures = providers.into_iter().map(|provider_id| {
        let context = case_context.clone();
        async move {
            generate_document_for_provider(template_id, case_id, provider_id, context).await
        }
    });

    futures::future::try_join_all(futures).await
}
```

---

## Future Enhancements

### 1. Community Template Marketplace

- Users share templates (anonymized)
- Rating/review system
- Download popular templates
- Revenue share for top contributors (optional)

### 2. Multi-Language Support

- Translate templates to Spanish, Mandarin, etc.
- AI assists with translation
- Maintain keyword bindings across languages

### 3. Voice-to-Template

- Attorney dictates: "Create a records request for Dr. Smith for John Doe's chiropractic treatment"
- AI generates template + fills keywords
- Attorney reviews and approves

### 4. Smart Suggestions Based on Case Type

```typescript
// If case_type === "auto_accident", suggest:
- "Add police report reference"
- "Include witness statements"
- "Request defendant's insurance info"

// If case_type === "medical_malpractice", suggest:
- "Expert witness qualifications"
- "Standard of care analysis"
- "Deviation from standard"
```

---

## Conclusion

The Conatus AI Mail Merge system is **not just automation—it's intelligence**:

✓ **Keyword framework**: User-trainable, extensible
✓ **AI assistance**: Content generation, gap analysis, quality improvement
✓ **Blockchain security**: PII logged, documents hashed, tamper-evident
✓ **User control**: AI suggests, user decides
✓ **Learning system**: Improves from user feedback

**This is the mail merge system plaintiff attorneys deserve**: fast, intelligent, secure, and built for trial.

---

*Document Version: 1.0*
*Last Updated: 2025-11-23*
*Author: Conatus Team*
