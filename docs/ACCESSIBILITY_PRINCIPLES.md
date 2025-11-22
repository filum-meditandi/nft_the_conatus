# Accessibility Principles

## Constitutional Constraints for Phenomenological Evidence Systems

This document defines the non-negotiable design principles for any system that captures lived experience from injured, ill, or cognitively impaired persons for legal purposes.

These are not "nice to haves." They are **constitutional constraints**. Any feature, interface, or workflow that violates these principles must be redesigned or rejected.

---

## Core Principle

> **The system must be usable by someone in pain, with brain fog, with a cheap phone, with limited energy, at 3am, while scared.**

If the system requires cognitive overhead, technical sophistication, or sustained attention that an injured plaintiff cannot provide, then the system has failed—regardless of how elegant the cryptography or how sophisticated the inference.

---

## The Four Constraints

### 1. Single-Step Interactions

**Rule**: Any input must work as a standalone action. No multi-step wizards. No "you must complete this form to continue."

**Rationale**: Brain fog, pain, and fatigue destroy working memory. If someone has to remember what step they're on, they will abandon the process.

**Implementation**:
- SMS commands work without prior context: `PAIN 7 neck` is complete.
- Voice prompts ask ONE question, accept ONE answer, then confirm.
- The system MUST accept partial information and still record something useful.

**Anti-patterns to avoid**:
- "Please complete all required fields"
- "Step 2 of 5"
- "Your session has expired, please start over"

---

### 2. Cognitive Load Limits

**Rule**: Never ask for more than one piece of information at a time. Prefer micro-prompts over comprehensive forms.

**Rationale**: Injured people have limited cognitive bandwidth. Every additional field is a reason to give up.

**Implementation**:
- Default prompts: "How's your pain right now? (0-10)"
- Follow-ups only if they respond: "Where does it hurt most?"
- NEVER require all fields. Accept `PAIN 7` without location, quality, or context.
- Summaries and reviews happen later, not during capture.

**Anti-patterns to avoid**:
- Intake forms with 20+ fields
- Required fields for optional context
- "Please describe in detail..."

---

### 3. Robust to Partial Information

**Rule**: The system MUST extract value from incomplete, ambiguous, or fragmentary input.

**Rationale**: Real reports look like:
- "bad day"
- "7"
- "neck again"
- "cant sleep"

These are valid phenomenological data. The system must not reject them.

**Implementation**:
- HMM feature extraction handles missing values gracefully (imputation, masking).
- Canonical payloads include `null` for missing fields—they're still attested.
- Chain entries are created even with sparse data.
- The parser tries multiple interpretations before asking for clarification.

**Anti-patterns to avoid**:
- "Invalid input, please try again"
- "Pain score is required"
- Silently dropping malformed messages

---

### 4. Explainability and Recall

**Rule**: Every automated conclusion must be traceable to the underlying attestations, and the plaintiff must be able to ask "show me the notes behind this."

**Rationale**: 
- Legal defensibility requires auditability.
- The plaintiff owns their story—they must be able to see and understand how it was structured.
- Opacity breeds distrust and disempowerment.

**Implementation**:
- Every `StateInference` links to `attested_entry_id`.
- Every `FeatureVector` links to `attested_entry_id`.
- Summary reports include "Based on N reports from [date] to [date]."
- On request: "EXPLAIN" returns the raw notes that fed a conclusion.
- The NFT payload includes pointers to the full chain, not just summaries.

**Anti-patterns to avoid**:
- "AI determined you had 14 flare episodes" (with no supporting detail)
- Black-box scores with no provenance
- Summaries that can't be drilled into

---

## Channel-Specific Guidelines

### SMS (Primary Channel)

SMS is the most accessible channel. It works on any phone, requires no app installation, and is familiar to everyone.

**Commands**:
| Command | Example | What it does |
|---------|---------|--------------|
| PAIN | `PAIN 7 neck burning` | Records pain with optional location/quality |
| WORK | `WORK left early` | Records work impact |
| SLEEP | `SLEEP 3 hours` | Records sleep disruption |
| FLARE | `FLARE` | Triggers brief follow-up questions |
| STATUS | `STATUS` | Returns current trajectory summary |
| HELP | `HELP` | Returns command list |

**Response style**:
- Acknowledge receipt immediately: "Got it."
- Keep confirmations under 160 characters.
- Never lecture or give medical advice.
- If unclear: "I recorded 'bad day'. Want to add a pain score? Reply with a number 0-10."

### Voice (Secondary Channel)

For those who can't type or prefer speaking.

**Design**:
- Single question per turn: "How would you rate your pain right now, from 0 to 10?"
- Accept natural language: "about a 7" → 7
- Confirm and end: "I recorded pain level 7. Take care."
- No menus. No "press 1 for..." trees.

### Web/App (Tertiary Channel)

Only for review, not primary capture.

**Design**:
- Timeline view of their own reports.
- Tap any entry to see full context.
- Export their data (PDF, JSON).
- Never require the app for capture—SMS must always work.

---

## Testing Against These Principles

Before any release, ask:

1. **Can someone with a $30 Android phone use this?**
2. **Can someone with a concussion use this at 3am?**
3. **Can someone who's never used the system send one message and have it recorded?**
4. **Can we explain every conclusion by pointing to specific attestations?**
5. **Does the plaintiff have access to their own data in a form they can understand?**

If any answer is "no," the feature is not ready.

---

## The Stakes

This system exists to serve people at the worst moments of their lives—injured, in pain, fighting for recognition of their suffering.

If we build something that only works for the technically sophisticated, the cognitively intact, or the persistently energetic, we have failed the people who need it most.

Accessibility is not a feature. It is the foundation.

---

*"For the sake of the people's justice."*
