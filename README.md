<div align="center">

# Indian Loan Analyzer

### AI-Powered Multi-Loan Optimizer with Tax-Aware Repayment Strategies for India

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.7-3178C6?style=for-the-badge&logo=typescript&logoColor=white)](https://typescriptlang.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16+pgvector-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://postgresql.org)
[![Azure](https://img.shields.io/badge/100%25_Azure-0078D4?style=for-the-badge&logo=microsoftazure&logoColor=white)](https://azure.microsoft.com)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-Welcome-brightgreen?style=for-the-badge)](https://github.com/DandaAkhilReddy/Claude_Loan_Management_Indian/pulls)

**Scan loan documents with AI | Optimize repayment across multiple loans | Save lakhs in interest**

[Live Demo](https://app-loan-analyzer-web.azurewebsites.net) | [API Swagger](https://app-loan-analyzer-api.azurewebsites.net/docs)

[Getting Started](#quick-start) | [Features](#features) | [Architecture](#architecture) | [API Docs](#api-endpoints) | [CI/CD](#cicd-pipeline) | [Contributing](#contributing)

---

</div>

## Features

<table>
<tr>
<td width="25%" align="center">

**Smart Optimizer**

4 repayment strategies with freed-EMI relay race cascade
</td>
<td width="25%" align="center">

**Document Scanner**

Azure AI OCR extracts loan details from bank statements
</td>
<td width="25%" align="center">

**EMI Calculator**

Public calculator with instant results — no login needed
</td>
<td width="25%" align="center">

**AI Advisor**

RAG-powered Q&A about loans, RBI rules & tax benefits
</td>
</tr>
<tr>
<td align="center">

**Trilingual**

English, Hindi, Telugu — UI + AI output + TTS
</td>
<td align="center">

**Firebase Auth**

Phone OTP (India-first) + Google Sign-In
</td>
<td align="center">

**Tax Optimization**

Old vs New regime comparison with 80C, 24(b), 80E, 80EEA
</td>
<td align="center">

**Indian Formatting**

INR display as 1,00,000 — not 100,000
</td>
</tr>
</table>

---

## The Killer Feature: Smart Hybrid Algorithm

> **"Jab ek loan khatam, uski EMI dusre loan pe lagao"**
> *(When one loan finishes, redirect its EMI to the next loan)*

The **Freed-EMI Relay Race** is what makes this optimizer unique. When Loan A pays off, its monthly EMI doesn't disappear — it gets added to the extra payment pool for Loan B. This creates an accelerating payoff cascade that saves you lakhs.

### Strategy Comparison

| Strategy | Logic | Best For |
|:---------|:------|:---------|
| **Avalanche** | Highest interest rate first | Saving maximum interest (mathematically optimal) |
| **Snowball** | Smallest balance first | Quick psychological wins |
| **Smart Hybrid** | Post-tax effective rate + 3-EMI bump + foreclosure awareness | **India-specific tax optimization (Recommended)** |
| **Proportional** | Pro-rata by outstanding balance | Balanced progress on all loans |

### Smart Hybrid in Action

```
Home Loan:     8.5% nominal  -  Section 24(b) at 30% bracket  =  5.95% effective
Personal Loan: 12.0% nominal -  No tax benefit                = 12.0%  effective
Education Loan: 9.0% nominal -  Section 80E at 30% bracket    =  6.3%  effective

Result: Pay personal loan first (12% effective), even though
        education loan has higher nominal rate than home loan!
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                 React 19 + TypeScript PWA                    │
│              Vite + Tailwind CSS + Recharts                  │
│  ┌──────────┐ ┌───────────┐ ┌────────┐ ┌────────────────┐  │
│  │Dashboard │ │ Optimizer │ │Scanner │ │ EMI Calculator │  │
│  │          │ │  Wizard   │ │  OCR   │ │   (public)     │  │
│  └──────────┘ └───────────┘ └────────┘ └────────────────┘  │
│  ┌──────────┐ ┌───────────┐ ┌────────────────────────────┐  │
│  │  Loans   │ │ Settings  │ │  i18n: EN / HI / TE       │  │
│  └──────────┘ └───────────┘ └────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTPS + Firebase Auth Token
┌────────────────────────▼────────────────────────────────────┐
│              Python FastAPI (async) — App Service B1         │
│                                                              │
│  ┌─── API Layer ──────────────────────────────────────────┐  │
│  │ /auth  /loans  /optimizer  /scanner  /emi  /ai         │  │
│  └────────────────────────┬───────────────────────────────┘  │
│  ┌─── Service Layer ──────▼───────────────────────────────┐  │
│  │ AuthSvc · ScannerSvc · AISvc · TranslatorSvc · TTSSvc  │  │
│  └────────────────────────┬───────────────────────────────┘  │
│  ┌─── Core Engine ────────▼───────────────────────────────┐  │
│  │ FinancialMath · Strategies · Optimizer · IndianRules    │  │
│  │          (Decimal precision to the paisa)               │  │
│  └────────────────────────────────────────────────────────┘  │
└───────┬──────────────┬────────────────────┬─────────────────┘
        │              │                    │
┌───────▼──────┐ ┌─────▼────────────┐ ┌────▼──────────────────┐
│ Azure Blob   │ │ PostgreSQL 16    │ │ Azure AI Services     │
│ Storage      │ │ + pgvector       │ │                       │
│              │ │                  │ │ • Document Intelligence│
│ Raw docs     │ │ • users          │ │   (Layout model)      │
│ Hot→Cool→    │ │ • loans          │ │ • OpenAI GPT-4o-mini  │
│ Archive      │ │ • scan_jobs      │ │ • Translator (free)   │
│              │ │ • repayment_plans│ │ • Neural TTS (free)   │
│              │ │ • doc_embeddings │ │   Neerja / Swara /    │
│              │ │ • consent_records│ │   Shruti              │
│              │ │ • audit_logs     │ │                       │
└──────────────┘ └──────────────────┘ └───────────────────────┘
```

---

## Tech Stack

### Backend

| Category | Technology | Version |
|:---------|:-----------|:--------|
| Framework | FastAPI + Uvicorn | 0.115.6 |
| Database | SQLAlchemy (async) + AsyncPG | 2.0.36 |
| Migrations | Alembic | 1.14.1 |
| Vector DB | pgvector | 0.3.6 |
| OCR | Azure Document Intelligence | 1.0.0 |
| AI/LLM | OpenAI SDK (Azure OpenAI) | 1.58.1 |
| Auth | Firebase Admin | 6.6.0 |
| Blob Storage | Azure Storage Blob | 12.24.1 |
| Translator | Azure AI Translation | 1.0.1 |
| TTS | Azure Cognitive Services Speech | 1.42.0 |
| Config | Pydantic Settings | 2.7.1 |
| Testing | Pytest + Pytest-AsyncIO | 8.3.4 |

### Frontend

| Category | Technology | Version |
|:---------|:-----------|:--------|
| UI Framework | React | 19.0.0 |
| Build Tool | Vite | 6.0.5 |
| Language | TypeScript | 5.7.2 |
| Routing | React Router DOM | 7.13.0 |
| Server State | TanStack Query | 5.90.20 |
| Client State | Zustand | 5.0.11 |
| Styling | Tailwind CSS | 4.1.18 |
| Charts | Recharts | 3.7.0 |
| i18n | i18next + react-i18next | 25.8.4 |
| Auth | Firebase | 12.9.0 |
| Validation | Zod | 4.3.6 |
| File Upload | React Dropzone | 14.4.0 |
| Icons | Lucide React | 0.563.0 |
| PWA | Vite Plugin PWA | 1.2.0 |

---

## Database Schema

7 tables on **PostgreSQL 16 + pgvector** for unified relational + vector storage:

```
┌──────────────────┐       ┌──────────────────┐
│      users       │       │   audit_logs     │
│──────────────────│       │──────────────────│
│ id (PK, UUID)    │──┐    │ id (PK)          │
│ firebase_uid     │  │    │ user_id (FK)     │
│ email            │  │    │ action           │
│ phone            │  │    │ details (JSONB)  │
│ preferred_lang   │  │    └──────────────────┘
│ tax_regime       │  │
│ annual_income    │  │    ┌──────────────────┐
└──────────────────┘  │    │ consent_records  │
                      │    │──────────────────│
    ┌─────────────────┤    │ id (PK)          │
    │                 ├───>│ user_id (FK)     │
    │                 │    │ purpose          │
    │                 │    │ consent_text     │
    ▼                 │    └──────────────────┘
┌──────────────────┐  │
│      loans       │  │    ┌──────────────────────┐
│──────────────────│  │    │ document_embeddings  │
│ id (PK, UUID)    │  │    │──────────────────────│
│ user_id (FK)     │  │    │ id (PK)              │
│ bank_name        │  │    │ embedding Vector(1536)│ ◄── pgvector
│ loan_type        │  │    │ chunk_text           │
│ principal_amount │  │    │ source_type          │
│ outstanding_     │  │    │ metadata (JSONB)     │
│   principal      │  │    └──────────────────────┘
│ interest_rate    │  │
│ emi_amount       │  │    ┌──────────────────┐
│ eligible_80c     │  └───>│ repayment_plans  │
│ eligible_24b     │       │──────────────────│
│ eligible_80e     │       │ id (PK)          │
│ eligible_80eea   │       │ user_id (FK)     │
│ status           │       │ strategy         │
└──────────────────┘       │ config (JSONB)   │
        │                  │ results (JSONB)  │
        ▼                  │ is_active        │
┌──────────────────┐       └──────────────────┘
│    scan_jobs     │
│──────────────────│
│ id (PK, UUID)    │
│ user_id (FK)     │
│ blob_url         │
│ status           │
│ extracted_fields │
│   (JSONB)        │
│ confidence_scores│
│   (JSONB)        │
│ created_loan_id  │
└──────────────────┘
```

---

## API Endpoints

### Authentication

| Method | Endpoint | Auth | Description |
|:-------|:---------|:-----|:------------|
| `POST` | `/api/auth/verify-token` | - | Firebase token exchange + user upsert |
| `GET` | `/api/auth/me` | Required | Current user profile |
| `PUT` | `/api/auth/me` | Required | Update profile (language, tax regime) |

### Loans

| Method | Endpoint | Auth | Description |
|:-------|:---------|:-----|:------------|
| `GET` | `/api/loans` | Required | List loans (filter by type/status/bank) |
| `POST` | `/api/loans` | Required | Create loan manually |
| `GET` | `/api/loans/{id}` | Required | Loan detail |
| `PUT` | `/api/loans/{id}` | Required | Update loan |
| `DELETE` | `/api/loans/{id}` | Required | Delete loan |
| `GET` | `/api/loans/{id}/amortization` | Required | Amortization schedule with prepayments |

### Document Scanner

| Method | Endpoint | Auth | Description |
|:-------|:---------|:-----|:------------|
| `POST` | `/api/scanner/upload` | Required | Upload PDF/PNG/JPG (max 10MB) for OCR |
| `GET` | `/api/scanner/status/{id}` | Required | Poll OCR processing status |
| `POST` | `/api/scanner/{id}/confirm` | Required | Confirm extracted fields, create loan |

### Multi-Loan Optimizer

| Method | Endpoint | Auth | Description |
|:-------|:---------|:-----|:------------|
| `POST` | `/api/optimizer/analyze` | Required | Full optimization (all 4 strategies) |
| `POST` | `/api/optimizer/quick-compare` | Required | Quick savings preview |
| `POST` | `/api/optimizer/what-if` | Required | Single loan scenario analysis |
| `POST` | `/api/optimizer/tax-impact` | Required | Old vs New tax regime comparison |
| `POST` | `/api/optimizer/save-plan` | Required | Save repayment plan |
| `GET` | `/api/optimizer/plans` | Required | List saved plans |

### EMI Calculator (Public)

| Method | Endpoint | Auth | Description |
|:-------|:---------|:-----|:------------|
| `POST` | `/api/emi/calculate` | - | EMI + total interest + savings |
| `POST` | `/api/emi/reverse-calculate` | - | Find interest rate from target EMI |
| `POST` | `/api/emi/affordability` | - | Max borrowable for given budget |

### AI Insights

| Method | Endpoint | Auth | Description |
|:-------|:---------|:-----|:------------|
| `POST` | `/api/ai/explain-loan` | Required | Plain-language loan explanation |
| `POST` | `/api/ai/explain-strategy` | Required | Strategy recommendation explanation |
| `POST` | `/api/ai/ask` | Required | RAG-powered Q&A (loans, RBI rules, tax) |
| `POST` | `/api/ai/tts` | Required | Text-to-Speech (EN/HI/TE voices) |

---

## Quick Start

### Prerequisites

- **Node.js** 18+ and **npm**
- **Python** 3.11+
- **Docker** (for PostgreSQL + pgvector)

### 1. Clone the repo

```bash
git clone https://github.com/DandaAkhilReddy/Claude_Loan_Management_Indian.git
cd Claude_Loan_Management_Indian
```

### 2. Start the database

```bash
# Create a .env file with your Postgres password
echo "POSTGRES_PASSWORD=your_secure_password" > .env

# Start PostgreSQL 16 + pgvector
docker compose up -d
```

### 3. Set up the backend

```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment (copy and fill in your Azure keys)
cp .env.example .env
# Edit .env with your credentials

# Run database migrations
alembic upgrade head

# Start the API server
uvicorn app.main:app --reload --port 8000
```

### 4. Set up the frontend

```bash
cd frontend

# Install dependencies
npm install

# Configure environment
cp .env.example .env
# Edit .env with your Firebase config

# Start the dev server
npm run dev
```

Open **http://localhost:5173** and you're ready to go!

---

## Project Structure

```
Indian_Loan_Analyzer_Claude/
│
├── .github/
│   └── workflows/
│       └── deploy.yml            # CI/CD: test → build → deploy to Azure
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes/           # auth, loans, optimizer, scanner, emi, ai
│   │   │   ├── deps.py           # Firebase auth dependencies
│   │   │   └── middleware.py     # Logging, rate limiting, error handler
│   │   ├── core/
│   │   │   ├── financial_math.py    # EMI, amortization, reverse EMI
│   │   │   ├── strategies.py        # Avalanche, Snowball, SmartHybrid, Proportional
│   │   │   ├── optimization.py      # Multi-loan simulator + freed-EMI rollover
│   │   │   └── indian_rules.py      # Tax 80C/24b/80E/80EEA, RBI rules
│   │   ├── db/
│   │   │   ├── models.py           # 7 SQLAlchemy models + pgvector
│   │   │   ├── session.py          # Async engine + session factory
│   │   │   └── repositories/      # user, loan, scan, plan, embedding repos
│   │   ├── schemas/               # Pydantic v2 request/response models
│   │   ├── services/              # Azure AI, auth, blob, translator, TTS
│   │   └── config.py              # Environment config (pydantic-settings)
│   ├── tests/                     # 409 unit tests (financial math, API, services)
│   ├── alembic/                   # Database migrations
│   ├── Dockerfile                 # Python 3.11-slim + uvicorn
│   ├── .env.example               # Template for backend env vars
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── auth/              # LoginPage (Email/Password + Google)
│   │   │   ├── layout/            # AppShell, Header, Sidebar, MobileNav
│   │   │   ├── optimizer/         # 4-step wizard components
│   │   │   ├── loans/             # LoanForm
│   │   │   └── shared/            # ErrorBoundary, CurrencyDisplay, etc.
│   │   ├── pages/                 # 7 lazy-loaded page components
│   │   ├── hooks/                 # useAuth, useLoans, TanStack Query hooks
│   │   ├── lib/                   # api, firebase, format (INR), emi-math, i18n
│   │   ├── store/                 # Zustand: auth, language, ui stores
│   │   ├── locales/               # en.json, hi.json, te.json, es.json
│   │   └── types/                 # TypeScript interfaces
│   ├── Dockerfile                 # Node build + nginx serve
│   ├── .env.example               # Template for frontend env vars
│   ├── package.json
│   └── vite.config.ts             # Code-splitting + manual chunks
│
├── infra/
│   └── azure-deploy.sh            # Azure resource provisioning script
│
├── scripts/
│   └── smoke-test.sh              # Post-deployment health checks
│
├── docs/
│   ├── CTO_REVIEW.md              # Architecture review (8.2/10)
│   └── reference/                 # 9 original design PDFs
│
├── docker-compose.yml             # Local dev: PostgreSQL 16 + pgvector
├── docker-compose.prod.yml        # Production: full stack with nginx
└── README.md
```

---

## India-Specific Features

### Indian Number Formatting

```
Standard:  $100,000      ₹100,000     (WRONG for India)
Indian:    ₹1,00,000                  (CORRECT — last 3, then groups of 2)
Compact:   ₹1L  ₹1Cr  ₹5K            (Lakh, Crore, Thousand)
```

### Tax Deduction Support

| Section | Benefit | Cap | Loan Type |
|:--------|:--------|:----|:----------|
| **80C** | Principal repayment deduction | ₹1.5L/year | Home |
| **24(b)** | Home loan interest deduction | ₹2L/year (self-occupied) | Home |
| **80E** | Education loan interest | No cap (8-year window) | Education |
| **80EEA** | First-time buyer interest | ₹1.5L (2019-2022 loans) | Home |

### RBI Prepayment Rules

- **Floating rate loans**: 0% prepayment penalty (RBI circular 2014)
- **Fixed rate loans**: Bank-specific foreclosure charges (typically 2-4%)

### Supported Indian Banks

SBI, HDFC, ICICI, Axis, PNB, Kotak Mahindra, Bank of Baroda, Union Bank, Canara Bank, Indian Bank — with regex patterns for document field extraction.

### Indian TTS Voices

| Language | Voice | Region |
|:---------|:------|:-------|
| English | `en-IN-NeerjaNeural` | Central India |
| Hindi | `hi-IN-SwaraNeural` | Central India |
| Telugu | `te-IN-ShrutiNeural` | Central India |

---

## Production Readiness

### CTO Architecture Review: 8.2 / 10 — PASS (Conditional)

| Domain | Score | Weight |
|:-------|:------|:-------|
| Security & Auth | 9/10 | 25% |
| Financial Math Accuracy | **10/10** | 20% |
| Database Design | 9/10 | 15% |
| Azure Integration | 9/10 | 15% |
| Frontend Architecture | 8/10 | 10% |
| Infrastructure & DevOps | 7/10 | 10% |
| Code Quality & Patterns | 8/10 | 5% |

> Full report: [`docs/CTO_REVIEW.md`](docs/CTO_REVIEW.md)

### Build Stats

| Metric | Value |
|:-------|:------|
| Backend files | 49 Python files (3,525 lines) |
| Frontend files | 42 TS/TSX files (2,521 lines) |
| Test coverage | 1,822 lines of financial math tests |
| Critical-path JS | **94 KB** gzipped (target: <170 KB) |
| EMI verified against | SBI, HDFC bank calculators |
| Decimal precision | 28 digits, ROUND_HALF_UP to paisa |

---

## Azure Cost Estimate

100% Azure deployment at **~$138/month** for 10K users:

| Service | Config | Cost/Month |
|:--------|:-------|:-----------|
| Static Web Apps | Free tier (9 Indian CDN POPs) | $0 |
| App Service | B1 Linux, Central India (Pune) | ~$13 |
| PostgreSQL Flexible | B1ms, 1 vCore, 2GB, 32GB storage | ~$20 |
| Blob Storage | Standard LRS, 10GB | ~$1 |
| OpenAI GPT-4o-mini | ~500K tokens/month | ~$85 |
| Document Intelligence | Layout model, ~5K pages/month | ~$8 |
| Translator | Free tier (2M chars/month) | $0 |
| Neural TTS | Free tier (500K chars/month) | $0 |
| Miscellaneous | DNS, egress, logging | ~$11 |
| **Total** | | **~$138** |

> Budget headroom: **$862/month** remaining from $1,000 limit. Scales to 50K users at ~$555/month.

---

## DPDP Act 2023 Compliance

This application includes infrastructure for India's **Digital Personal Data Protection Act**:

- **Consent Manager** — Timestamped records before any data processing
- **Right to Erasure** — `DELETE /api/user/delete-account` cascades all user data
- **Data Export** — `POST /api/user/export-data` returns full JSON dump
- **Audit Trail** — All operations logged in `audit_logs` table
- **Data Residency** — All processing in Central India (Pune) Azure region
- **Purpose Limitation** — Consent specifies exact usage purpose

---

## Environment Variables

### Backend (`backend/.env`)

| Variable | Required | Description |
|:---------|:---------|:------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string (`postgresql+asyncpg://user:pass@host:5432/db?ssl=require` for Azure) |
| `FIREBASE_PROJECT_ID` | Yes | Firebase project ID for token verification |
| `AZURE_OPENAI_ENDPOINT` | For AI features | Azure OpenAI endpoint URL |
| `AZURE_OPENAI_KEY` | For AI features | Azure OpenAI API key |
| `AZURE_OPENAI_DEPLOYMENT` | For AI features | Deployment name (default: `gpt-4o-mini`) |
| `AZURE_DOC_INTEL_ENDPOINT` | For scanner | Azure Document Intelligence endpoint |
| `AZURE_DOC_INTEL_KEY` | For scanner | Azure Document Intelligence key |
| `AZURE_STORAGE_CONNECTION_STRING` | For scanner | Azure Blob Storage connection string |
| `AZURE_STORAGE_CONTAINER` | For scanner | Blob container name (default: `loan-documents`) |
| `AZURE_TRANSLATOR_KEY` | For translation | Azure Translator key |
| `AZURE_TRANSLATOR_REGION` | For translation | Azure region (default: `centralindia`) |
| `AZURE_TTS_KEY` | For TTS | Azure Speech Services key |
| `AZURE_TTS_REGION` | For TTS | Azure region (default: `centralindia`) |
| `ENVIRONMENT` | No | `development` or `production` (default: `development`) |
| `LOG_LEVEL` | No | Logging level (default: `INFO`) |
| `CORS_ORIGINS` | No | Comma-separated allowed origins |

### Frontend (`frontend/.env`)

| Variable | Required | Description |
|:---------|:---------|:------------|
| `VITE_API_BASE_URL` | No | Backend API URL (empty string = same-origin proxy in production) |
| `VITE_FIREBASE_API_KEY` | Yes | Firebase Web API key |
| `VITE_FIREBASE_AUTH_DOMAIN` | Yes | Firebase auth domain (`project.firebaseapp.com`) |
| `VITE_FIREBASE_PROJECT_ID` | Yes | Firebase project ID |
| `VITE_FIREBASE_STORAGE_BUCKET` | No | Firebase storage bucket |
| `VITE_FIREBASE_MESSAGING_SENDER_ID` | No | Firebase messaging sender ID |
| `VITE_FIREBASE_APP_ID` | No | Firebase app ID |

> **Note:** Frontend env vars are baked into the build at compile time via Vite. They are NOT secret — they are embedded in the JS bundle.

---

## CI/CD Pipeline

Automated via **GitHub Actions** (`.github/workflows/deploy.yml`). Triggers on every push to `main`.

```
push to main
     │
     ├── test-backend ────── pip install → pytest (409 tests)
     │
     ├── test-frontend ───── npm install → vitest (66 tests)
     │
     └── build-and-deploy ── (runs after both test jobs pass)
              │
              ├── Login to Azure (service principal)
              ├── Login to ACR (loanalyzeracr.azurecr.io)
              ├── Build + push backend Docker image
              ├── Build + push frontend Docker image (with VITE_FIREBASE_* build args)
              ├── Deploy backend to App Service (app-loan-analyzer-api)
              ├── Deploy frontend to App Service (app-loan-analyzer-web)
              ├── Smoke test backend (/api/health → 200)
              └── Smoke test frontend (/ → 200)
```

### Required GitHub Secrets

| Secret | Description |
|:-------|:------------|
| `AZURE_CREDENTIALS` | Service principal JSON (`az ad sp create-for-rbac --role Contributor`) |
| `VITE_FIREBASE_API_KEY` | Firebase Web API key |
| `VITE_FIREBASE_AUTH_DOMAIN` | Firebase auth domain |
| `VITE_FIREBASE_PROJECT_ID` | Firebase project ID |
| `VITE_FIREBASE_STORAGE_BUCKET` | Firebase storage bucket |
| `VITE_FIREBASE_MESSAGING_SENDER_ID` | Firebase messaging sender ID |
| `VITE_FIREBASE_APP_ID` | Firebase app ID |

### Azure Resources

| Resource | Name | Purpose |
|:---------|:-----|:--------|
| Resource Group | `rg-loan-analyzer` | All resources |
| Container Registry | `loanalyzeracr.azurecr.io` | Docker images (managed identity pull) |
| App Service (backend) | `app-loan-analyzer-api` | FastAPI on port 8000 |
| App Service (frontend) | `app-loan-analyzer-web` | nginx serving React build |
| PostgreSQL Flexible | `loan-analyzer-db.postgres.database.azure.com` | Database (`loan_analyzer`) |

---

## Testing

### Backend (pytest)

```bash
cd backend
pip install -r requirements.txt
pytest -v --tb=short
```

**409 tests** covering:

- `test_financial_math.py` — EMI calculation, amortization, reverse EMI, edge cases
- `test_strategies.py` — All 4 repayment strategies with freed-EMI rollover
- `test_indian_rules.py` — Tax deductions (80C, 24b, 80E, 80EEA), RBI prepayment rules
- `test_optimization.py` — Multi-loan optimizer integration
- `test_routes_*.py` — API endpoint request/response validation
- `test_services.py` — Azure AI service mocks
- `test_auth.py` — Firebase token verification
- `test_schemas.py` — Pydantic model validation

### Frontend (vitest)

```bash
cd frontend
npm install
npm test
```

**66 tests** covering:

- `format.test.ts` — Indian number formatting (INR ₹1,00,000), compact display (₹1L, ₹1Cr)
- `emi-math.test.ts` — Client-side EMI calculations
- `i18n.test.ts` — Translation keys for EN, HI, TE, ES locales
- `App.test.tsx` — Route rendering and lazy loading
- Component tests — ErrorBoundary, LoadingSpinner, CurrencyDisplay

### Production Build Check

```bash
cd frontend
npm run build    # Zero TypeScript errors required
```

---

## Development Workflow

### Local Development (recommended)

1. **Start the database** — `docker compose up -d` (PostgreSQL 16 + pgvector on port 5432)
2. **Start the backend** — `cd backend && uvicorn app.main:app --reload --port 8000` (hot-reload)
3. **Start the frontend** — `cd frontend && npm run dev` (Vite dev server on port 5173, proxies API calls)

The frontend Vite dev server runs on `http://localhost:5173`. Set `VITE_API_BASE_URL=http://localhost:8000` in `frontend/.env` for local development.

### Production (Docker Compose)

```bash
# Fill in environment variables
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env

# Build and run all services
docker compose -f docker-compose.prod.yml up --build
```

### Key Development Patterns

- **State management**: Zustand stores (`authStore`, `languageStore`, `uiStore`) — no Redux boilerplate
- **Server state**: TanStack Query with 5-minute stale time, 2 retries, no refetch-on-focus
- **API client**: Axios with auto-attached Firebase token (request interceptor) and global error handling (response interceptor)
- **Routing**: React Router v7 with lazy-loaded pages for code-splitting
- **i18n**: i18next with JSON locale files — add new languages by creating `locales/xx.json` and registering in `lib/i18n.ts`
- **Financial math**: All monetary calculations use Python `Decimal` with 28-digit precision, `ROUND_HALF_UP` to the paisa
- **Auth flow**: Firebase client SDK (frontend) → `getIdToken()` → Bearer header → `firebase_admin.auth.verify_id_token()` (backend)

---

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/amazing-feature`)
3. Commit your changes (`git commit -m 'feat: Add amazing feature'`)
4. Push to the branch (`git push origin feat/amazing-feature`)
5. Open a Pull Request

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

---

<div align="center">

**Built with [Claude Code](https://claude.ai/claude-code) using 50 AI agents organized as a software company**

*10 teams x 5 agents (1 leader + 4 developers) — Phase 0 scaffolding, Phase 1 parallel development, Phase 2 integration, Phase 3 QA + CTO review*

---

[Report Bug](https://github.com/DandaAkhilReddy/Claude_Loan_Management_Indian/issues) | [Request Feature](https://github.com/DandaAkhilReddy/Claude_Loan_Management_Indian/issues)

</div>
