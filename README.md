# BITBYBIT — Autonomous AI Payment & Project Agent (AAPPA)

BITBYBIT is an AI-powered intermediary platform for freelance project management that autonomously decomposes projects, verifies deliverables across code/content/design modalities, manages escrow payments with cryptographic integrity, and maintains a credit-score-style reputation system.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Tech Stack](#tech-stack)
3. [Complete System Flow](#complete-system-flow)
4. [AI Project Decomposition (AAPPA-Core)](#ai-project-decomposition-aappa-core)
5. [Clarity Analysis & Clarification Engine](#clarity-analysis--clarification-engine)
6. [Verification Engine — Modality-Aware AQA](#verification-engine--modality-aware-aqa)
   - [Code Verification (4-Layer Pipeline)](#code-verification-4-layer-pipeline)
   - [Content Verification (7-Step CMS Pipeline)](#content-verification-7-step-cms-pipeline)
   - [Design Verification (5-Dimension Pipeline)](#design-verification-5-dimension-pipeline)
   - [Mixed Modality Handling](#mixed-modality-handling)
   - [Standard Fallback Pipeline](#standard-fallback-pipeline)
7. [Composite Scoring & Payment Decision Engine](#composite-scoring--payment-decision-engine)
8. [Escrow System & Financial Integrity](#escrow-system--financial-integrity)
9. [PFI — Professional Fidelity Index](#pfi--professional-fidelity-index)
10. [HITL — Human-in-the-Loop Override](#hitl--human-in-the-loop-override)
11. [Authentication & Security](#authentication--security)
12. [NLP & Deterministic Text Analysis](#nlp--deterministic-text-analysis)
13. [Frontend Architecture](#frontend-architecture)
14. [Backend API Reference](#backend-api-reference)
15. [Database Schema](#database-schema)
16. [Setup & Running](#setup--running)

---

## Architecture Overview

```
┌────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (React 19)                        │
│  EmployerDashboard ─ FreelancerDashboard ─ EscrowLedger ─ PFI     │
│  One-click create+decompose ─ Clarification Q&A ─ AQA Reports     │
└────────────────────┬───────────────────────────────────────────────┘
                     │ REST API (JWT Bearer)
┌────────────────────▼───────────────────────────────────────────────┐
│                        BACKEND (FastAPI)                            │
│                                                                     │
│  ┌─────────┐  ┌──────────┐  ┌─────────┐  ┌───────┐  ┌──────────┐ │
│  │  Auth   │  │ Employer │  │Freelancer│  │Escrow │  │   PFI    │ │
│  │ Routes  │  │  Routes  │  │  Routes  │  │Routes │  │  Routes  │ │
│  └────┬────┘  └────┬─────┘  └────┬─────┘  └───┬───┘  └────┬─────┘ │
│       │            │             │             │            │       │
│  ┌────▼────────────▼─────────────▼─────────────▼────────────▼────┐ │
│  │                     SERVICE LAYER                              │ │
│  │  ┌──────────────────────────────────────────────────────────┐ │ │
│  │  │           Verification Engine (Orchestrator)              │ │ │
│  │  │  ┌──────────────┬──────────────┬──────────────────────┐  │ │ │
│  │  │  │Code Verifier │Content Verif.│  Design Verifier     │  │ │ │
│  │  │  │  4 Layers    │  7 Steps     │  5 Dimensions        │  │ │ │
│  │  │  │ AST→Tests→   │ Structure→   │ Requirements→        │  │ │ │
│  │  │  │ Sonar→LLM    │ Grammar→LLM  │ Visual→A11y→LLM     │  │ │ │
│  │  │  └──────────────┴──────────────┴──────────────────────┘  │ │ │
│  │  └──────────────────────────────────────────────────────────┘ │ │
│  │  ┌─────────┐ ┌───────────┐ ┌─────────┐ ┌─────────────────┐   │ │
│  │  │AI Service│ │Escrow Svc │ │PFI Svc  │ │Content/Design   │   │ │
│  │  │(Groq LLM)│ │(SHA-256)  │ │(Scoring)│ │  Metrics        │   │ │
│  │  └─────────┘ └───────────┘ └─────────┘ └─────────────────┘   │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │              PostgreSQL (async via asyncpg)                   │   │
│  │  Projects ─ Milestones ─ Users ─ Proposals ─ Escrow ─ PFI   │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                     │
                     ▼ External APIs
          ┌──────────────────────┐
          │  Groq (LLaMA 3.3)   │
          │  Figma API (optional)│
          │  SonarQube (optional)│
          └──────────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 19, Vite 8, Tailwind CSS, Framer Motion, Radix UI, Lucide Icons |
| **Backend** | FastAPI (Python 3.12+), async throughout |
| **Database** | PostgreSQL via SQLAlchemy 2 (async, `asyncpg`) |
| **ORM** | SQLAlchemy 2 with mapped columns, `selectinload` for eager loading |
| **AI/LLM** | Groq API — `llama-3.3-70b-versatile` model |
| **Auth** | JWT (python-jose), bcrypt (passlib) |
| **HTTP** | httpx (async) for all external API calls |
| **Crypto** | SHA-256 chain hashing, HMAC-SHA256 signatures for financial ops |
| **Containerization** | Docker for sandboxed test execution and SonarQube |

---

## Complete System Flow

### Employer Journey

```
1. Register/Login → JWT token issued
2. Create Project → Enter description
3. One-Click Decompose:
   a. Project created in DB (status: "draft")
   b. Clarity analysis via LLM → ambiguity_score calculated
   c. If vague (score > 0.4):
      → Show clarification questions
      → User answers → Answers appended to description
   d. If clear OR after answers:
      → Full AI decomposition into milestones (status: "decomposed")
4. Publish for Proposals → status: "funded" (visible to freelancers)
5. Review Proposals → See freelancer bids, PFI scores, cover letters
6. Accept Proposal:
   → Escrow created with freelancer's bid amount
   → Funds locked, milestone budgets allocated proportionally
   → Project status: "active"
7. Monitor Progress → View milestone statuses, AQA reports
8. HITL Override → Manually resolve low-confidence verifications
```

### Freelancer Journey

```
1. Register/Login → JWT token, PFI score initialized at 500
2. Browse Open Projects → Filter by status "funded"
3. Submit Proposal → Cover letter + bid amount + estimated days
4. Get Assigned → Proposal accepted, project becomes "active"
5. Activate Milestone → Status: PENDING → IN_PROGRESS
6. Submit Work:
   a. Modality-specific deliverables required:
      - Code: GitHub repo URL (required) + commit hash (optional)
      - Design: Design URLs — Figma, images, etc. (required)
      - Content: Document URL
      - Mixed: Combination based on scoring_weights detection
   b. Verification Engine runs automatically (AQA)
   c. Payment decision: FULL_PAY / PARTIAL_PAY / REFUND / HITL
7. PFI score updated after each milestone resolution
```

---

## AI Project Decomposition (AAPPA-Core)

**Service:** `services/ai.py` — `decompose_project()`
**Endpoint:** `POST /api/employer/projects/{id}/decompose`

### How It Works

1. **Prompt Engineering**: A structured system prompt (`DECOMPOSE_SYSTEM_PROMPT`) instructs the LLM to act as "AAPPA-Core" — an autonomous project decomposition and verification planning engine.

2. **The LLM generates a strict JSON schema** containing:
   - `project_classification` — primary type (code/content/design/mixed), complexity, ambiguity score
   - `clarification` — questions the AI would ask if the description is vague, plus assumptions
   - `milestones[]` — 3-9 milestones, each with title, description, task_type, dependencies, estimated_days, payment_percentage, acceptance_criteria, scoring_weights, definition_of_done
   - `dag[]` — directed acyclic graph of milestone dependencies
   - `global_verification_policy` — pass/partial/fail thresholds
   - `risk_flags` — identified project risks

3. **Validation Pipeline** (`_validate_decomposition`):
   - Pydantic schema validation (`DecompositionResult`)
   - Key normalization for camelCase ↔ snake_case variants the LLM might output
   - Payment percentage auto-normalization (must sum to 100%)
   - Acceptance criteria normalization (string → structured dict)
   - Risk level computation from complexity + ambiguity

4. **Retry Logic**: Up to 3 attempts with full re-generation on failure.

### Scoring Policy by Modality (embedded in prompt)

| Modality | Weights |
|----------|---------|
| **Code** | correctness 40%, security 20%, test_coverage 20%, maintainability 20% |
| **Content** | factuality 30%, originality 25%, readability 20%, SEO structure 15%, style alignment 10% |
| **Design** | requirements_coverage 25%, visual_consistency 25%, accessibility 20%, responsive_completeness 20%, export_readiness 10% |

---

## Clarity Analysis & Clarification Engine

**Service:** `services/ai.py` — `check_clarity()`
**Endpoint:** `POST /api/employer/projects/{id}/clarify`

### Logic

When a project is created, the system automatically analyzes the description's clarity before decomposing:

1. A lightweight LLM call evaluates the description across 5 dimensions:
   - Specificity of deliverables
   - Technology/tool mentions
   - Scope clarity
   - Measurable outcomes
   - Target audience/platform

2. Returns an `ambiguity_score` from 0.0 (crystal clear) to 1.0 (extremely vague).

3. **Decision threshold**: If `ambiguity_score > 0.4` AND the LLM says `needs_clarification: true`, the system pauses and presents 2-5 targeted clarification questions to the employer.

4. **Answers flow**: When the user answers, the Q&A is appended to the original description as a "Clarification Q&A" block, giving the decomposition LLM much richer context.

5. **Graceful degradation**: If the clarity check fails (API error), it defaults to `needs_clarification: false` and proceeds directly to decomposition.

---

## Verification Engine — Modality-Aware AQA

**Orchestrator:** `services/verification_engine.py` — `orchestrate_verification()`

The verification engine is the core intelligence of BITBYBIT. When a freelancer submits work, it:

1. **Classifies the modality** — from `task_type` or heuristic keyword matching against the domain string
2. **Routes to the appropriate pipeline** based on modality + available evidence
3. **Computes a composite score** blending deterministic and LLM evaluations
4. **Makes a payment decision** with confidence-gated thresholds

### Routing Logic

```
if modality == "code" AND repo_url exists → 4-Layer Code Pipeline
if modality == "content"                  → 7-Step Content Pipeline
if modality == "design"                   → 5-Dimension Design Pipeline
else (mixed / no repo)                    → Standard Heuristic + LLM Pipeline
```

---

### Code Verification (4-Layer Pipeline)

**Service:** `services/code_verifier.py` (1,578 lines)

The most sophisticated pipeline — clones the actual GitHub repository and runs multi-layer deterministic analysis before LLM review.

#### Layer 1: Static Analysis (AST) — 15% weight

- **Git clone** to a temporary directory with optional commit checkout
- **Language detection**: Python, JavaScript/TypeScript, Go (extensible)
- **AST parsing** using Python's `ast` module (for Python) or regex-based analysis (JS/TS/Go)
- **Metrics computed**:
  - Function count, class count, total lines of code
  - Error handling patterns (try/except/catch)
  - Import structure analysis
  - Cyclomatic complexity estimation
  - Code-to-comment ratio

#### Layer 2: Runtime Tests (Sandbox) — 35% weight

- **Docker sandbox** (`--network=none` for security isolation):
  - Python: discovers and runs `pytest` with timeout
  - Node.js: runs `npm test` or `jest`
  - Go: runs `go test ./...`
- **Subprocess fallback** when Docker is unavailable
- **Scoring**:
  - Test discovery score (do tests exist?)
  - Test pass rate
  - Coverage estimation from output parsing

#### Layer 3: SonarQube Quality Gate — 20% weight

- **Docker-based SonarQube Scanner** with project key isolation
- **CLI fallback** (`sonar-scanner`) when Docker isn't available
- **Metrics pulled from SonarQube API**:
  - Quality gate status (PASS/WARN/FAIL)
  - Bug count, vulnerability count, code smell count
  - Technical debt ratio
  - Coverage percentage
- **Hard rule**: SonarQube FAIL caps the overall score at 70

#### Layer 4: LLM Semantic Review — 30% weight

- The LLM receives an **enriched submission** containing:
  - The freelancer's written description
  - **Actual source code** extracted from the cloned repository (file contents, up to token limits)
  - The **client's original project description** for requirement matching
- Evaluates each acceptance criterion independently (0-100)
- Assesses code quality, naming conventions, DRY principles, business logic completeness

#### Additional Code Checks

- **Security Scanning**: Regex-based detection of hardcoded secrets, `eval()` usage, SQL injection patterns, dangerous system calls
- **Dependency Analysis**: Checks for `package.json`, `requirements.txt`, `go.mod` — verifies dependency management exists
- **Description Matching**: Compares repository structure against client requirements to detect mismatches between what was requested and what was built

#### Hard Rules

- LLM alone cannot produce `FULLY_COMPLETED` — at least one static/runtime layer must pass (score ≥ 50)
- SonarQube FAIL (`gate_score ≤ 25`) hard-caps the composite at 70
- If the 4-layer pipeline fails entirely, falls back to standard heuristic + LLM

---

### Content Verification (7-Step CMS Pipeline)

**Service:** `services/content_verifier.py` (524 lines)
**Metrics:** `services/content_metrics.py` (182 lines)

A 7-step pipeline that blends deterministic NLP analysis with LLM evaluation.

#### CMS Weights

| Dimension | Weight |
|-----------|--------|
| requirement_coverage | 25% |
| content_quality | 20% |
| structure | 15% |
| originality | 15% |
| readability | 10% |
| grammar | 10% |
| keyword_coverage | 5% |

#### Deterministic Steps (computed locally, zero external calls)

1. **Structure Analysis** (15%):
   - Paragraph count and distribution
   - Heading detection (Markdown `#` patterns)
   - Section organization scoring

2. **Originality / Self-Similarity** (15%):
   - 4-gram analysis across the submission
   - Cross-similarity between first and second halves of the content
   - Formula: `ratio = (duplication × 0.4) + (cross_similarity × 0.6)`
   - Score: `100 × (1 - similarity_ratio)`

3. **Grammar Error Detection** (10%):
   - 10 regex-based grammar patterns:
     - Lowercase "i" standalone
     - "a" before vowel sounds / "an" before consonants
     - Repeated consecutive words
     - Missing apostrophes in contractions (`dont` → `don't`)
     - Comma splices
     - Sentences starting with lowercase after line breaks
     - Excessively long sentences (>50 words)
     - Excessive punctuation

4. **Keyword Coverage** (5%):
   - Case-insensitive word-boundary matching against required keywords extracted from acceptance criteria
   - Score: `found_keywords / total_required_keywords × 100`

5. **Readability — Flesch-Kincaid** (10%):
   - Formula: `206.835 − (1.015 × ASL) − (84.6 × ASW)`
   - ASL = average sentence length, ASW = average syllables per word
   - Syllable counting via vowel-group heuristic
   - Score mapped to 0-100 range

#### LLM Steps (via Groq)

6. **Requirement Coverage** (25%): LLM evaluates whether the content addresses all acceptance criteria
7. **Content Quality** (20%): LLM assesses depth, accuracy, and usefulness

#### Verdict Logic

- CMS ≥ 85 → `FULLY_COMPLETED`
- CMS 50-84 → `PARTIALLY_COMPLETED` (pro-rated payout)
- CMS < 50 → `UNMET` (refund)

---

### Design Verification (5-Dimension Pipeline)

**Service:** `services/design_verifier.py` (600 lines)
**Metrics:** `services/design_metrics.py` (254 lines)

Optimized for VPS deployment (8 GB) — no image downloads or headless browsers.

#### 5 Dimensions

| Dimension | Weight |
|-----------|--------|
| requirements_coverage | 25% |
| visual_consistency | 25% |
| accessibility | 20% |
| responsive_completeness | 20% |
| export_readiness | 10% |

#### Deterministic Signals (regex-based, zero external calls)

1. **Design Tool URL Detection**: Regex patterns for 9 platforms — Figma, Dribbble, Behance, InVision, Zeplin, Adobe XD, Canva, Sketch Cloud
2. **Export Format Detection**: Recognizes 15+ formats (`.png`, `.svg`, `.fig`, `.sketch`, `.xd`, `.psd`, `.pdf`, etc.)
3. **Accessibility Signals**: Detects mentions of WCAG, alt-text, ARIA labels, contrast ratios, screen readers, keyboard navigation, focus states
4. **Responsive Signals**: Detects mentions of breakpoints (320px, 375px, 768px, 1024px, 1440px), media queries, mobile/tablet/desktop
5. **Typography & Color Specs**: Font families, type scales, color palettes, dark/light mode mentions
6. **Screen/Component Coverage**: Counts mentions of required screens (dashboard, login, profile, etc.) and UI components (buttons, forms, cards, modals, etc.)
7. **Design System Signals**: Atomic design, component libraries, design tokens, spacing scales

#### Optional Figma API Enrichment

If a Figma URL is detected and a `FIGMA_ACCESS_TOKEN` is configured:
- Fetches lightweight file metadata via `GET /v1/files/{key}?depth=2`
- Extracts: page count, frame names, component names, last modified date
- No image downloads — just a ~2-20 KB JSON response

#### LLM Evaluation

- `requirements_coverage` (25%): Whether all required screens and deliverables are present
- `visual_consistency` (25%): Consistent spacing, color usage, typography across screens

---

### Mixed Modality Handling

For milestones with `task_type: "mixed"`, the system detects which modalities are involved by inspecting the `scoring_weights` dictionary:

```python
CODE_KEYS = {"correctness", "security", "test_coverage", "maintainability"}
DESIGN_KEYS = {"visual_consistency", "accessibility", "responsive_completeness", ...}
CONTENT_KEYS = {"factuality", "originality", "readability", "seo_structure", ...}
```

The frontend dynamically shows the appropriate submission fields:
- Code + Design → GitHub repo URL (required) + Design URLs (required)
- Code + Content → GitHub repo URL (required) + Content URL
- Design + Content → Design URLs (required) + Content URL

The backend enforces these requirements and combines all evidence into the submission for verification.

---

### Standard Fallback Pipeline

When no specialized pipeline applies (mixed modality, code without repo URL), the engine runs:

1. **Heuristic Checks** based on modality:
   - Code: regex pattern matching for functions/classes/imports, error handling, test presence
   - Content: word count, readability scoring, paragraph structure, heading analysis
   - Design: export format detection, design tool URLs, accessibility/responsive mentions
   - Mixed: all three combined with prefixed keys

2. **LLM Evaluation** via `ai_service.evaluate_submission()`

3. **Score Blending**: deterministic 30% + LLM 70%

---

## Composite Scoring & Payment Decision Engine

### Score Computation

**Standard pipeline** (`compute_composite_score`):

```
if both deterministic AND LLM scores exist:
    composite = deterministic_avg × 0.3 + llm_avg × 0.7
    confidence = 0.6 + 0.4 × agreement_factor
elif only deterministic:
    composite = deterministic_avg, confidence = 0.5
elif only LLM:
    composite = llm_avg, confidence = 0.5
```

Where `agreement_factor = 1 - |det_avg - llm_avg| / 100`

**Code pipeline** (`compute_code_pipeline_score`):

```
composite = static × 0.15 + runtime × 0.35 + sonarqube × 0.20 + llm × 0.30
```

Confidence increases with more data layers and inter-layer agreement.

### Payment Decision Logic (`make_payment_decision`)

```
if confidence < 0.7          → HITL (human review required)
if evidence_completeness < 0.3 AND score < 85 → HITL
if score ≥ 85                → FULL_PAY (100%)
if score ≥ 50                → PARTIAL_PAY (pro-rated at score%)
if score < 50                → REFUND
```

### Hard Rules

1. **LLM alone cannot produce FULL_PAY** — at least one deterministic layer must pass (≥50)
2. **SonarQube FAIL hard-caps score at 70** — prevents full-pay for code with quality gate failures
3. **Low confidence always triggers HITL** — the system never auto-pays when uncertain

---

## Escrow System & Financial Integrity

**Service:** `services/escrow.py` (348 lines)
**Model:** `models/escrow.py`

### State Machine

```
CREATED → FUNDED → MILESTONE_ACTIVE → WORK_SUBMITTED → AQA_REVIEW
                                                          ↓
                                              ┌──────────┴──────────┐
                                              ↓                      ↓
                                         PAID_FULL              REFUND_INITIATED
                                         PAID_PARTIAL
                                              ↓
                                          COMPLETED (all milestones resolved)
```

### Escrow Funded on Proposal Acceptance

Funds are **not** locked when the employer creates or publishes a project. Instead:
1. Employer publishes project (no money required)
2. Freelancers submit proposals with bid amounts
3. When the employer **accepts a proposal**, escrow is created with the **freelancer's bid amount**
4. Milestone budgets are allocated proportionally by complexity score:
   ```python
   ms.payment_amount = total_budget × (ms.complexity_score / total_complexity)
   ```

### SHA-256 Chain Hashing (Tamper Detection)

Every ledger entry is cryptographically chained to the previous one:

```python
tx_hash = SHA-256(previous_hash || event || amount || timestamp)
```

This creates an **append-only blockchain-like ledger** where:
- Any modification to a past entry breaks the chain
- The `verify_ledger_integrity()` endpoint re-computes all hashes and detects the exact entry where tampering occurred

### HMAC-SHA256 Signatures (Financial Operation Integrity)

All financial operations (deposits, payments, refunds) are signed:

```python
signature = HMAC-SHA256(PAYMENT_HMAC_SECRET, "{event}:{amount}:{escrow_id}")
```

The signature is computed and immediately verified before any fund movement. This ensures:
- Operations haven't been tampered with in transit
- The server's HMAC secret is required to authorize financial operations

### Idempotency

Every ledger entry gets a unique `idempotency_key` (UUID v4) stored with a unique constraint in the database. This prevents duplicate transactions from being processed even if a request is retried.

### Ledger Entry Types

| Type | Events |
|------|--------|
| `STATE_CHANGE` | CONTRACT_CREATED, MILESTONE_ACTIVATED, WORK_SUBMITTED, AQA_REVIEW_STARTED, CONTRACT_COMPLETED |
| `DEPOSIT` | FUNDS_DEPOSITED |
| `PAYMENT` | FULL_PAYMENT_RELEASED, PARTIAL_PAYMENT_RELEASED |
| `REFUND` | REFUND_INITIATED |

### Integrity Verification Endpoint

`GET /api/escrow/projects/{id}/verify` — Re-computes the entire hash chain and returns:
```json
{ "valid": true, "total_entries": 12, "broken_at_index": null }
```

---

## PFI — Professional Fidelity Index

**Service:** `services/pfi.py` (152 lines)
**Model:** `models/pfi.py`

A credit-score-style reputation system (300–1000 range) for freelancers.

### Weighted Base Score Calculation

| Factor | Weight | What It Measures |
|--------|--------|------------------|
| Completion History | 35% | Milestone accuracy minus dispute penalty (disputes weighted 2×) |
| Quality Metrics | 30% | Average AQA scores across all evaluated milestones |
| Reliability | 20% | On-time delivery rate (submitted_at - started_at ≤ estimated_days) |
| Experience | 15% | Total milestones completed, capped at 50 for full score |

### Formulas

```
completion_score = max(0, milestone_accuracy - dispute_penalty × 2)
quality_score    = average(all_aqa_scores)  [default 50 if none]
reliability_score = on_time_deliveries / total_deliveries × 100
experience_score  = min(100, total_milestones / 50 × 100)

base_100 = completion × 0.35 + quality × 0.30 + reliability × 0.20 + experience × 0.15
final_pfi = 300 + (base_100 / 100) × 700    [clamped to 300–1000]
```

### Risk Labels

| Score Range | Label |
|-------------|-------|
| ≥ 850 | Elite |
| ≥ 720 | Trusted |
| ≥ 580 | Established |
| ≥ 450 | Developing |
| < 450 | Unproven |

### When PFI Updates

PFI is recalculated after **every milestone resolution** (PAID_FULL, PAID_PARTIAL, or REFUND_INITIATED). The full milestone history for the project is re-evaluated, ensuring the score always reflects the latest state.

### History Tracking

Every PFI change is recorded in `pfi_history` with the score, event type, and timestamp — enabling trend analysis and the leaderboard.

---

## HITL — Human-in-the-Loop Override

**Endpoint:** `POST /api/employer/projects/{id}/hitl/{milestone_id}/resolve`
**Frontend:** `HITLOverride` component

When the AQA system has low confidence (< 0.7) or insufficient evidence (< 30%), it queues the result for human review instead of auto-deciding payment.

### Available Actions

| Action | Effect |
|--------|--------|
| `approve` | Release pro-rated payment based on AQA's recommended percentage |
| `full_pay` | Release 100% payment (override AQA score) |
| `refund` | Initiate full refund for the milestone |
| `resubmit` | Reset milestone to IN_PROGRESS, clear submission, let freelancer resubmit |

### HITL Queue

The `hitl_queue` table stores:
- The full AQA result (for employer review)
- The original submission text
- Resolution status, action taken, reason, and who resolved it

---

## Authentication & Security

### JWT Authentication

**Middleware:** `middleware/auth.py`

- Tokens contain: `sub` (user_id), `role` (employer/freelancer), `exp`, `iat`
- Algorithm: HS256 (configurable via `JWT_ALGORITHM`)
- Expiration: 1440 minutes / 24 hours (configurable)
- Tokens are validated on every request via FastAPI's `HTTPBearer` dependency

### Password Security

- **bcrypt** hashing via `passlib.CryptContext`
- Passwords are never stored in plaintext
- `verify_password()` uses constant-time comparison (built into passlib)

### Role-Based Access Control

The `require_role()` dependency factory restricts endpoints:
- Employer endpoints: project creation, decomposition, proposals, HITL, analytics
- Freelancer endpoints: browsing, proposals, milestone work, PFI

Attempting to access a wrong-role endpoint returns `403 Forbidden`.

### CORS Policy

Configured in `main.py`:
- Explicit origin whitelist (`CORS_ORIGINS`) + regex pattern matching
- Credentials allowed
- All methods and headers exposed
- 10-minute preflight cache

### API Key Management

Users can store their own Groq API key via `PUT /api/auth/api-key`. Keys are stored in-memory (per-session). If no user key is set, the server's `GROQ_API_KEY` is used as fallback.

### Sandboxed Code Execution

When running freelancer tests in the code verification pipeline:
- Docker containers run with `--network=none` (no internet access)
- Execution is time-bounded with `--stop-timeout`
- Temporary directories are cleaned up after verification
- Subprocess fallback also uses `timeout` parameter

---

## NLP & Deterministic Text Analysis

### Content Metrics (`services/content_metrics.py`)

All NLP is done locally with zero external dependencies:

1. **Tokenization**: Regex-based word extraction (`[a-zA-Z']+`)
2. **Sentence Splitting**: Split on `.!?` followed by whitespace, minimum 2-word sentences
3. **Paragraph Detection**: Split on double newlines
4. **Flesch-Kincaid Readability**: Syllable counting via vowel-group heuristic, standard FK formula
5. **Grammar Error Detection**: 10 regex patterns covering common English errors
6. **Self-Similarity / Originality**: 4-gram overlap analysis between document halves
7. **Keyword Coverage**: Word-boundary regex matching against required terms

### Design Metrics (`services/design_metrics.py`)

Pure string/regex analysis for design quality signals:

1. **URL Pattern Matching**: 9 design tool URL patterns (Figma, Dribbble, Behance, InVision, Zeplin, Adobe XD, Canva, Sketch)
2. **Export Format Detection**: 15+ file formats via dot-extension and standalone keyword matching
3. **Accessibility Signals**: 15+ WCAG/a11y keyword patterns
4. **Responsive Signals**: Breakpoint values, media query terms, device names
5. **Typography/Color**: Font family names, color specification patterns, theme mentions
6. **Screen/Component Detection**: 30+ screen type patterns, 30+ UI component patterns
7. **Design System Detection**: Atomic design, component libraries, design tokens

### Code Heuristics (`services/verification_engine.py`)

For code submissions without a repository URL:

1. **Structure Check**: Regex counting of language keywords (`def`, `function`, `class`, `import`, `async`)
2. **Error Handling Check**: Patterns for `try/catch/except/raise/throw`
3. **Test Presence Check**: Patterns for `test_`, `describe(`, `expect(`, `assert`, `pytest`, `jest`
4. **Artifact URL Check**: Whether the submission contains URLs
5. **Line Count Check**: Basic volume metric

---

## Frontend Architecture

### State Management

Uses React's `useReducer` with a centralized store (`store/reducer.js`):
- 20+ action types covering auth, projects, escrow, AQA, PFI, proposals, analytics
- Global state flows via props (`state`, `dispatch`) from `App.jsx`
- Local component state for UI-specific concerns (forms, selections, loading)

### Routing

React Router v7 with role-based navigation:
- **Employer**: `/projects`, `/analytics`, `/leaderboard`
- **Freelancer**: `/browse`, `/proposals`, `/projects`, `/pfi`, `/leaderboard`
- Shared: `EscrowLedger` sidebar panel

### Key Components

| Component | Purpose |
|-----------|---------|
| `EmployerDashboard` | One-click create+decompose, clarification Q&A, milestone DAG, publish, proposal review |
| `FreelancerDashboard` | Browse projects, submit proposals, modality-aware work submission, AQA reports |
| `EscrowLedger` | Real-time escrow state, ledger entries, integrity verification |
| `PFIDashboard` | Score display, history chart, leaderboard |
| `AnalyticsPanel` | Employer analytics — funnel metrics, escrow totals |
| `HITLOverride` | Pending HITL items with approve/refund/resubmit actions |
| `AQAReport` | Detailed AQA result display with criteria breakdown |

### UI Features

- **Progress Stepper**: 3-step indicator during create+decompose flow (Creating → Analyzing clarity → Decomposing)
- **DAG Visualization**: SVG-based milestone dependency graph with complexity-colored nodes
- **Modality Badges**: Color-coded task type indicators (code=cyan, design=purple, content=green)
- **Animated Transitions**: Framer Motion for page transitions, card hover effects, fade-ins

---

## Backend API Reference

### Auth (`/api/auth`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/register` | Register new user (employer/freelancer) |
| POST | `/login` | Login, returns JWT + user |
| GET | `/me` | Get current user profile |
| PUT | `/api-key` | Store Groq API key for session |

### Employer (`/api/employer`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/projects` | Create a new project |
| GET | `/projects` | List employer's projects |
| GET | `/projects/{id}` | Get project detail |
| POST | `/projects/{id}/clarify` | Check description clarity |
| POST | `/projects/{id}/decompose` | AI decomposition (with optional clarification answers) |
| POST | `/projects/{id}/publish` | Publish for freelancer proposals |
| POST | `/projects/{id}/fund` | Legacy funding endpoint |
| GET | `/projects/{id}/proposals` | List proposals for project |
| POST | `/projects/{id}/proposals/{pid}/accept` | Accept proposal → create escrow |
| POST | `/projects/{id}/proposals/{pid}/reject` | Reject proposal |
| GET | `/projects/{id}/hitl` | List HITL queue items |
| POST | `/projects/{id}/hitl/{mid}/resolve` | Resolve HITL item |
| GET | `/analytics` | Employer analytics dashboard data |
| GET | `/freelancers` | List all freelancers with PFI |

### Freelancer (`/api/freelancer`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/open-projects` | Browse funded projects |
| POST | `/projects/{id}/propose` | Submit proposal |
| GET | `/proposals` | List own proposals |
| DELETE | `/proposals/{id}` | Withdraw proposal |
| GET | `/projects` | List assigned projects |
| GET | `/projects/{id}` | Get assigned project detail |
| POST | `/projects/{id}/milestones/{mid}/activate` | Start working on milestone |
| POST | `/projects/{id}/milestones/{mid}/submit` | Submit work → triggers AQA |
| GET | `/pfi` | Get own PFI score |
| GET | `/pfi/history` | Get PFI history |

### Escrow (`/api/escrow`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/projects/{id}` | Get escrow account |
| GET | `/projects/{id}/ledger` | Get full ledger |
| GET | `/projects/{id}/verify` | Verify ledger hash chain integrity |

### PFI (`/api/pfi`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/scores/{user_id}` | Get PFI score for any user |
| GET | `/leaderboard` | Global leaderboard (top 50) |
| GET | `/history/{user_id}` | PFI score history |

### AI (`/api/ai`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/decompose` | Standalone decomposition |
| POST | `/evaluate` | Standalone AQA evaluation |
| POST | `/demo` | Generate demo project |
| POST | `/score-match` | Skill-domain matching |
| POST | `/detect-bias` | Rating history bias detection |

### Content (`/api/content`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/verify-content` | Standalone content verification |
| POST | `/projects/{id}/milestones/{mid}/verify` | Milestone content verification |

### Design (`/api/design`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/verify-design` | Standalone design verification |
| POST | `/projects/{id}/milestones/{mid}/verify` | Milestone design verification |

---

## Database Schema

### Core Tables

```
users
├── id (UUID, PK)
├── email (unique, indexed)
├── password_hash (bcrypt)
├── role (enum: employer/freelancer)
├── name
└── created_at

freelancer_profiles
├── id (UUID, PK)
├── user_id (FK → users, unique)
├── skills (JSONB array)
└── bio (text)

projects
├── id (UUID, PK)
├── employer_id (FK → users)
├── freelancer_id (FK → users, nullable)
├── description (text)
├── budget (float, nullable)
├── deadline (date, nullable)
├── status (draft/decomposed/funded/active/completed)
├── risk_level (Low/Medium/High)
├── total_estimated_days
├── decomposition (JSONB — full AI output)
├── project_type (code/content/design/mixed)
└── created_at

milestones
├── id (UUID, PK)
├── project_id (FK → projects)
├── index (ordering)
├── title, description, domain
├── estimated_days, complexity_score
├── acceptance_criteria (JSONB array)
├── task_type (code/content/design/mixed)
├── scoring_weights (JSONB)
├── verification_profile (JSONB)
├── status (PENDING/IN_PROGRESS/WORK_SUBMITTED/AQA_REVIEW/PAID_*/REFUND_INITIATED)
├── payment_amount, payment_released
├── submission, submission_url
├── aqa_result (JSONB — full AQA output)
├── started_at, submitted_at
└── project (relationship)

proposals
├── id (UUID, PK)
├── project_id (FK → projects)
├── freelancer_id (FK → users)
├── cover_letter (text)
├── bid_amount (float, nullable)
├── estimated_days (int, nullable)
├── status (pending/accepted/rejected/withdrawn)
├── created_at, updated_at
```

### Financial Tables

```
escrow_accounts
├── id (UUID, PK)
├── project_id (FK → projects, unique)
├── total_funds, locked_funds, released_funds, refunded_funds
├── state (CREATED/FUNDED/MILESTONE_ACTIVE/WORK_SUBMITTED/AQA_REVIEW/PAID_*/REFUND_*/COMPLETED)
├── created_at
└── ledger_entries (relationship)

ledger_entries
├── id (UUID, PK)
├── escrow_id (FK → escrow_accounts)
├── timestamp
├── event (CONTRACT_CREATED/FUNDS_DEPOSITED/MILESTONE_ACTIVATED/...)
├── amount (nullable)
├── type (STATE_CHANGE/DEPOSIT/PAYMENT/REFUND)
├── details (text)
├── contract_state
├── tx_hash (SHA-256 chain hash)
├── idempotency_key (UUID, unique)
└── escrow (relationship)
```

### Reputation Tables

```
pfi_scores
├── id (UUID, PK)
├── user_id (FK → users, unique)
├── score (300-1000)
├── rating (Glicko-2, default 1500)
├── rd (rating deviation, default 350)
├── volatility (default 0.06)
└── updated_at

pfi_history
├── id (UUID, PK)
├── user_id (FK → users)
├── score, rating
├── event_type (MILESTONE_COMPLETED/...)
└── timestamp

hitl_queue
├── id (UUID, PK)
├── milestone_id (FK → milestones)
├── project_id (FK → projects)
├── aqa_result (JSONB)
├── submission (text)
├── status (pending/resolved)
├── resolution, resolution_reason
├── resolved_by (FK → users)
└── created_at
```

---

## Setup & Running

### Prerequisites

- Python 3.12+
- Node.js 18+
- PostgreSQL 15+
- Docker (optional — for sandboxed code tests and SonarQube)

### Backend

```bash
cd Backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create .env file
cat > .env << EOF
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/bitbybit
JWT_SECRET_KEY=your-secret-key
PAYMENT_HMAC_SECRET=your-hmac-secret
GROQ_API_KEY=your-groq-api-key
EOF

# Run
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd Frontend
npm install

# Create .env file
echo "VITE_BACKEND_URL=http://localhost:8000" > .env

# Run
npm run dev
```

### Optional Services

- **SonarQube**: Set `SONARQUBE_URL` and `SONARQUBE_TOKEN` in `.env` for code quality gate analysis
- **Figma API**: Set `FIGMA_ACCESS_TOKEN` for design verification metadata enrichment
- **Docker**: Install Docker for sandboxed test execution (`--network=none`) in code verification

---

## License

This project is part of an academic/research initiative. All rights reserved.
