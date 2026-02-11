<div align="center">

# Indian Loan Analyzer

### AI-Powered Multi-Loan Optimizer with Tax-Aware Repayment Strategies

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.7-3178C6?style=for-the-badge&logo=typescript&logoColor=white)](https://typescriptlang.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16+pgvector-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://postgresql.org)
[![Tests](https://img.shields.io/badge/Tests-717_Passing-brightgreen?style=for-the-badge&logo=testcafe&logoColor=white)](#testing)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)

**Scan loan documents with AI | Optimize repayment across multiple loans | Save lakhs in interest**

[Getting Started](#quick-start) | [Features](#features) | [Architecture](#architecture) | [API Docs](#api-endpoints) | [Contributing](#contributing)

---

</div>

## Highlights

<table>
<tr>
<td>

**4 Smart Strategies** with freed-EMI relay race cascade — when one loan finishes, its EMI snowballs into the next

</td>
<td>

**AI Document Scanner** with GPT-4o Vision + pdfplumber — auto-detects INR/USD currency and creates loans instantly

</td>
<td>

**Visual Payoff Dashboard** with timeline bars, before/after comparison, and personalized action plan

</td>
</tr>
</table>

---

## Features

<table>
<tr>
<td width="25%" align="center">

**Smart Optimizer**

4 repayment strategies with freed-EMI relay race cascade + payoff timeline visualization
</td>
<td width="25%" align="center">

**Document Scanner**

GPT-4o Vision + pdfplumber — auto-detect currency (INR/USD), cross-field validation
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

**Payoff Timeline**

Visual horizontal bars per loan — color-coded by type, months saved highlighted
</td>
<td align="center">

**Action Plan**

Auto-generated next steps: focus order, freed EMI rollover, rate lock warnings
</td>
<td align="center">

**Multi-Currency**

Auto-detect INR/USD from scanned documents — switches country context automatically
</td>
<td align="center">

**Trilingual**

English, Hindi, Telugu — UI + AI output
</td>
</tr>
<tr>
<td align="center">

**Firebase Auth**

Phone OTP (India-first) + Google Sign-In
</td>
<td align="center">

**Tax Optimization**

Old vs New regime: 80C, 24(b), 80E, 80EEA (India) + mortgage/student deductions (US)
</td>
<td align="center">

**Admin Dashboard**

Usage metrics, API cost tracking, user & review management
</td>
<td align="center">

**DPDP Compliant**

Consent records, data export, right to erasure, audit logs
</td>
</tr>
</table>

---

## Optimizer Dashboard Preview

The optimizer wizard walks you through 4 steps and produces a rich results dashboard:

```
Step 1: Select Loans → Step 2: Set Budget → Step 3: Choose Strategy → Step 4: Results
```

### Results Dashboard Layout

```
┌──────────────────────────────────────────────────────────────────┐
│                     You save 2,50,000 in interest!              │
│  ┌─────────────────────┐   ┌──────────────────────┐            │
│  │   Without Plan      │   │    With Plan         │            │
│  │   8,50,000 interest │   │   6,00,000 interest  │            │
│  │   240 months        │   │   180 months         │            │
│  └─────────────────────┘   └──────────────────────┘            │
│                  Debt-free 60 months earlier                    │
├──────────────────────────────────────────────────────────────────┤
│  Loan Payoff Timeline                                           │
│  SBI Home Loan    ████████████████████░░░░ Month 180 (60 saved) │
│  HDFC Personal    ████████░░░░░░░░░░░░░░░ Month 84  (36 saved) │
│  ICICI Car        ████░░░░░░░░░░░░░░░░░░░ Month 36  (12 saved) │
├──────────────────────────────────────────────────────────────────┤
│  Your Action Plan                                               │
│  1. Focus extra payments on HDFC Personal — highest priority    │
│  2. HDFC will be paid off by month 84 — 36 months early!       │
│  3. Once HDFC is paid, its 21K/mo EMI rolls into remaining     │
│  4. Consider rate lock — 1% increase costs 45K more            │
├──────────────────────────────────────────────────────────────────┤
│  ┌─ Avalanche ──────┐   ┌─ Smart Hybrid (Best) ─┐             │
│  │ Saved: 2.1L      │   │ Saved: 2.5L           │             │
│  │ 55 mo earlier    │   │ 60 mo earlier          │             │
│  │ Per-loan:        │   │ Per-loan:              │             │
│  │ • SBI → mo 185   │   │ • SBI → mo 180        │             │
│  │ • HDFC → mo 90   │   │ • HDFC → mo 84        │             │
│  └──────────────────┘   └────────────────────────┘             │
├──────────────────────────────────────────────────────────────────┤
│  Rate Sensitivity Analysis                                      │
│  -1%  │  5,20,000  │ 170 mo │ Saved: 3,30,000                 │
│   0%  │  6,00,000  │ 180 mo │ Saved: 2,50,000  ← current     │
│  +1%  │  6,90,000  │ 192 mo │ Saved: 1,60,000                 │
│  +2%  │  7,85,000  │ 205 mo │ Saved: 65,000                   │
└──────────────────────────────────────────────────────────────────┘
```

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

## AI Document Scanner

The scanner uses a **2-strategy cascade** for maximum extraction accuracy:

```
Strategy 1: GPT-4o Vision (images) / GPT-4o text analysis (PDFs via pdfplumber)
     │
     ▼ (if fails)
Strategy 2: pdfplumber text extraction → regex pattern matching
```

### Key Scanner Features

| Feature | Description |
|:--------|:------------|
| **Auto Currency Detection** | Detects INR (₹, Rs, lakh) or USD ($, dollars) from document content |
| **Auto Country Switch** | Switches app context (IN/US) based on detected currency |
| **Cross-Field Validation** | EMI > principal? Swap. Rate > 50%? Cap. Principal < 3x EMI? Flag. |
| **Smart Prompt Engineering** | Distinguishes Amount Financed from Finance Charge on US TILA documents |
| **Dual Pattern Sets** | Indian patterns (lakh notation, SBI/HDFC banks) + US patterns (standard notation, Chase/Wells Fargo) |
| **Auto EMI Calculation** | If EMI missing but principal found, calculates from rate + tenure |

### Supported Banks

**India:** SBI, HDFC, ICICI, Axis, PNB, Kotak Mahindra, Bank of Baroda, Union Bank, Canara Bank, Indian Bank

**US:** Chase, Wells Fargo, Bank of America, Citi, US Bank, Capital One

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                 React 19 + TypeScript PWA                    │
│              Vite + Tailwind CSS + Lucide Icons              │
│  ┌──────────┐ ┌───────────┐ ┌────────┐ ┌────────────────┐  │
│  │Dashboard │ │ Optimizer │ │Scanner │ │ EMI Calculator │  │
│  │          │ │  Wizard   │ │  OCR   │ │   (public)     │  │
│  └──────────┘ └───────────┘ └────────┘ └────────────────┘  │
│  ┌──────────┐ ┌───────────┐ ┌──────────┐ ┌─────────────┐  │
│  │  Loans   │ │ Settings  │ │ Feedback │ │Admin Dashboard│  │
│  └──────────┘ └───────────┘ └──────────┘ └─────────────┘  │
│  ┌────────────────────────────────────────────────────────┐  │
│  │              i18n: EN / HI / TE                        │  │
│  └────────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTPS + Firebase Auth Token
┌────────────────────────▼────────────────────────────────────┐
│                   Python FastAPI (async)                      │
│                                                              │
│  ┌─── API Layer ──────────────────────────────────────────┐  │
│  │ /auth /loans /optimizer /scanner /emi /ai /admin /reviews│  │
│  └────────────────────────┬───────────────────────────────┘  │
│  ┌─── Service Layer ──────▼───────────────────────────────┐  │
│  │ AuthSvc · ScannerSvc · AISvc · TranslatorSvc           │  │
│  │ UsageTracker (cost estimation + logging)                │  │
│  └────────────────────────┬───────────────────────────────┘  │
│  ┌─── Core Engine ────────▼───────────────────────────────┐  │
│  │ FinancialMath · Strategies · Optimizer · IndianRules    │  │
│  │          (Decimal precision to the paisa)               │  │
│  └────────────────────────────────────────────────────────┘  │
└───────┬──────────────┬────────────────────┬─────────────────┘
        │              │                    │
┌───────▼──────┐ ┌─────▼────────────┐ ┌────▼──────────────────┐
│ Local File   │ │ PostgreSQL 16    │ │ OpenAI API            │
│ Storage      │ │ + pgvector       │ │                       │
│              │ │                  │ │ • GPT-4o-mini         │
│ ./uploads/   │ │ • users          │ │   (Vision + Text)     │
│              │ │ • loans          │ │ • text-embedding-3-   │
│              │ │ • scan_jobs      │ │   small (RAG)         │
│              │ │ • repayment_plans│ │ • Translation via     │
│              │ │ • doc_embeddings │ │   chat completions    │
│              │ │ • consent_records│ │                       │
│              │ │ • audit_logs     │ │                       │
│              │ │ • reviews        │ │                       │
│              │ │ • api_usage_logs │ │                       │
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
| PDF Extraction | pdfplumber | 0.11.4 |
| AI/LLM | OpenAI SDK | 1.58.1 |
| Auth | Firebase Admin | 6.6.0 |
| File Storage | Local filesystem (pathlib) | built-in |
| Translation | OpenAI chat completions | — |
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
| i18n | i18next + react-i18next | 25.8.4 |
| Auth | Firebase | 12.9.0 |
| Validation | Zod | 4.3.6 |
| File Upload | React Dropzone | 14.4.0 |
| Icons | Lucide React | 0.563.0 |
| PWA | Vite Plugin PWA | 1.2.0 |

---

## Database Schema

9 tables on **PostgreSQL 16 + pgvector** for unified relational + vector storage:

```
┌──────────────────┐       ┌──────────────────┐
│      users       │       │   audit_logs     │
│──────────────────│       │──────────────────│
│ id (PK, UUID)    │──┐    │ id (PK)          │
│ firebase_uid     │  │    │ user_id (FK)     │
│ email            │  │    │ action           │
│ phone            │  │    │ details (JSONB)  │
│ preferred_lang   │  │    └──────────────────┘
│ country (IN/US)  │  │
│ tax_regime       │  │    ┌──────────────────┐
│ annual_income    │  │    │ consent_records  │
└──────────────────┘  │    │──────────────────│
                      │    │ id (PK)          │
    ┌─────────────────┤    │ user_id (FK)     │
    │                 ├───>│ purpose          │
    │                 │    │ consent_text     │
    │                 │    └──────────────────┘
    ▼                 │
┌──────────────────┐  │    ┌──────────────────────┐
│      loans       │  │    │ document_embeddings  │
│──────────────────│  │    │──────────────────────│
│ id (PK, UUID)    │  │    │ id (PK)              │
│ user_id (FK)     │  │    │ embedding Vector(1536)│ ◄── pgvector
│ bank_name        │  │    │ chunk_text           │
│ loan_type        │  │    │ source_type          │
│ principal_amount │  │    │ metadata (JSONB)     │
│ outstanding_     │  │    └──────────────────────┘
│   principal      │  │
│ interest_rate    │  │    ┌──────────────────┐
│ emi_amount       │  └───>│ repayment_plans  │
│ eligible_80c     │       │──────────────────│
│ eligible_24b     │       │ id (PK)          │
│ eligible_80e     │       │ user_id (FK)     │
│ eligible_80eea   │       │ strategy         │
│ status           │       │ config (JSONB)   │
└──────────────────┘       │ results (JSONB)  │
        │                  │ is_active        │
        ▼                  └──────────────────┘
┌──────────────────┐
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

┌──────────────────┐       ┌──────────────────────┐
│     reviews      │       │   api_usage_logs     │
│──────────────────│       │──────────────────────│
│ id (PK, UUID)    │       │ id (PK, UUID)        │
│ user_id (FK)     │       │ user_id (FK, nullable)│
│ review_type      │       │ service              │
│ rating (1-5)     │       │ operation            │
│ title            │       │ tokens_input         │
│ content          │       │ tokens_output        │
│ status           │       │ estimated_cost       │
│ admin_response   │       │   (Numeric 10,6)     │
│ is_public        │       │ metadata_json (JSONB)│
│ created_at       │       │ created_at           │
│ updated_at       │       └──────────────────────┘
└──────────────────┘
```

---

## API Endpoints

### Authentication

| Method | Endpoint | Auth | Description |
|:-------|:---------|:-----|:------------|
| `POST` | `/api/auth/verify-token` | - | Firebase token exchange + user upsert |
| `GET` | `/api/auth/me` | Required | Current user profile |
| `PUT` | `/api/auth/me` | Required | Update profile (language, tax regime, country) |

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
| `POST` | `/api/scanner/upload` | Required | Upload PDF/PNG/JPG — auto-detect currency, create loan |
| `GET` | `/api/scanner/status/{id}` | Required | Poll OCR processing status |
| `POST` | `/api/scanner/{id}/confirm` | Required | Confirm extracted fields, create loan |

### Multi-Loan Optimizer

| Method | Endpoint | Auth | Description |
|:-------|:---------|:-----|:------------|
| `POST` | `/api/optimizer/analyze` | Required | Full optimization (all 4 strategies) |
| `POST` | `/api/optimizer/quick-compare` | Required | Quick savings preview |
| `POST` | `/api/optimizer/what-if` | Required | Single loan scenario analysis |
| `POST` | `/api/optimizer/tax-impact` | Required | Old vs New tax regime comparison |
| `POST` | `/api/optimizer/sensitivity` | Required | Rate sensitivity analysis |
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
| `POST` | `/api/ai/tts` | Required | Text-to-Speech (browser Web Speech API) |

### Reviews & Feedback

| Method | Endpoint | Auth | Description |
|:-------|:---------|:-----|:------------|
| `POST` | `/api/reviews` | Required | Submit feedback, testimonial, or feature request |
| `GET` | `/api/reviews/mine` | Required | List current user's submissions |
| `GET` | `/api/reviews/public` | - | Approved public testimonials |

### Admin Dashboard

| Method | Endpoint | Auth | Description |
|:-------|:---------|:-----|:------------|
| `GET` | `/api/admin/stats` | Admin | Dashboard metrics (users, loans, scans, reviews) |
| `GET` | `/api/admin/users` | Admin | User list with loan counts |
| `GET` | `/api/admin/usage` | Admin | API usage summary + cost estimates (30-day) |
| `GET` | `/api/admin/reviews` | Admin | All reviews (filterable by type/status) |
| `PUT` | `/api/admin/reviews/{id}` | Admin | Update review status / admin response |
| `DELETE` | `/api/admin/reviews/{id}` | Admin | Delete a review |

---

## Quick Start

### Prerequisites

- **Python** 3.11+
- **Node.js** 20+ and **npm**
- **Docker** (for PostgreSQL + pgvector)
- **OpenAI API key** (for AI features — EMI calculator works without it)

### 1. Clone the repo

```bash
git clone https://github.com/DandaAkhilReddy/Claude_Loan_Management_Indian.git
cd Claude_Loan_Management_Indian
```

### 2. Start the database

```bash
# Create a .env file with your Postgres password
echo "POSTGRES_PASSWORD=localdev123" > .env

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

# Configure environment
cp .env.example .env
# Edit .env — add your OPENAI_API_KEY (required for AI features)

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
# Default config points to http://localhost:8000 with auth bypass enabled

# Start the dev server
npm run dev
```

Open **http://localhost:5173** and you're ready to go!

> **Note:** Set `VITE_BYPASS_AUTH=true` in `frontend/.env` to skip Firebase authentication during local development.

---

## Project Structure

```
Indian_Loan_Analyzer_Claude/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes/           # auth, loans, optimizer, scanner, emi, ai, admin, reviews
│   │   │   ├── deps.py           # Firebase auth + admin auth dependencies
│   │   │   └── middleware.py     # Logging, rate limiting, error handler
│   │   ├── core/
│   │   │   ├── financial_math.py    # EMI, amortization, reverse EMI
│   │   │   ├── strategies.py        # Avalanche, Snowball, SmartHybrid, Proportional
│   │   │   ├── optimization.py      # Multi-loan simulator + freed-EMI rollover
│   │   │   ├── indian_rules.py      # Tax 80C/24b/80E/80EEA, RBI rules
│   │   │   └── usa_rules.py         # Federal brackets, mortgage/student deductions
│   │   ├── db/
│   │   │   ├── models.py           # 9 SQLAlchemy models + pgvector
│   │   │   ├── session.py          # Async engine + session factory
│   │   │   └── repositories/      # user, loan, scan, plan, embedding, review, usage repos
│   │   ├── schemas/               # Pydantic v2 request/response models
│   │   ├── services/              # OpenAI AI, auth, file storage, translator, usage tracker
│   │   └── config.py              # Environment config (pydantic-settings)
│   ├── tests/                     # 717+ tests across 30 test files
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
│   │   │   ├── optimizer/         # 4-step wizard: SelectLoans, SetBudget, ChooseStrategy, Results
│   │   │   ├── loans/             # LoanForm
│   │   │   └── shared/            # ErrorBoundary, CurrencyDisplay, etc.
│   │   ├── pages/                 # 9 lazy-loaded page components
│   │   ├── hooks/                 # useAuth, useLoans, useCountryConfig
│   │   ├── lib/                   # api, firebase, format (INR/USD), emi-math, i18n
│   │   ├── store/                 # Zustand: auth, language, country, ui stores
│   │   ├── locales/               # en.json, hi.json, te.json
│   │   └── types/                 # TypeScript interfaces
│   ├── Dockerfile                 # Node build + nginx serve
│   ├── .env.example               # Template for frontend env vars
│   ├── package.json
│   └── vite.config.ts             # Code-splitting + manual chunks
│
├── scripts/
│   └── smoke-test.sh              # Post-start health checks
│
├── docs/
│   └── CTO_REVIEW.md              # Architecture review (8.2/10)
│
├── docker-compose.yml             # Local dev: PostgreSQL 16 + pgvector
└── README.md
```

---

## Environment Variables

### Backend (`backend/.env`)

| Variable | Required | Description |
|:---------|:---------|:------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string (`postgresql+asyncpg://user:pass@host:5432/db`) |
| `OPENAI_API_KEY` | For AI features | OpenAI API key (`sk-...`) |
| `OPENAI_MODEL` | No | Model name (default: `gpt-4o-mini`) |
| `OPENAI_EMBEDDING_MODEL` | No | Embedding model (default: `text-embedding-3-small`) |
| `UPLOAD_DIR` | No | File upload directory (default: `./uploads`) |
| `FIREBASE_PROJECT_ID` | For auth | Firebase project ID for token verification |
| `FIREBASE_SERVICE_ACCOUNT_BASE64` | For auth | Base64-encoded service account JSON |
| `ENVIRONMENT` | No | `development` or `production` (default: `development`) |
| `LOG_LEVEL` | No | Logging level (default: `INFO`) |
| `CORS_ORIGINS` | No | Comma-separated allowed origins (default: `http://localhost:5173`) |

### Frontend (`frontend/.env`)

| Variable | Required | Description |
|:---------|:---------|:------------|
| `VITE_API_BASE_URL` | No | Backend API URL (default: `http://localhost:8000`) |
| `VITE_BYPASS_AUTH` | No | Set to `true` to skip Firebase auth in development |
| `VITE_FIREBASE_API_KEY` | For auth | Firebase Web API key |
| `VITE_FIREBASE_AUTH_DOMAIN` | For auth | Firebase auth domain |
| `VITE_FIREBASE_PROJECT_ID` | For auth | Firebase project ID |

> **Note:** Frontend env vars are baked into the build at compile time via Vite. They are NOT secret.

---

## Admin Dashboard & Feedback System

### Admin Dashboard (`/admin` — restricted to admin emails)

- **Metric Cards** — Total users, total loans by type, documents scanned, estimated API cost (30 days)
- **Usage by Service** — Table showing call counts, token usage, and cost per service
- **User Management** — Full user list with email, join date, and loan count
- **Review Moderation** — Approve/reject testimonials, respond to feedback
- **Feature Requests** — Track status: New → Acknowledged → Planned → Done

### API Usage Tracking

Every OpenAI API call is automatically logged with cost estimates:

| Service | Cost Model | Tracking |
|:--------|:-----------|:---------|
| OpenAI GPT-4o-mini | $0.15/1M input + $0.60/1M output tokens | Per-call token counts |
| OpenAI Embeddings | $0.02/1M tokens | Per-call token counts |
| File Storage | Local filesystem | Per-upload logging |
| Translation | OpenAI chat completions | Call count only |

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

### US Tax Support

| Deduction | Benefit | Loan Type |
|:----------|:--------|:----------|
| **Mortgage Interest** | Deductible on first $750K of debt | Home |
| **Student Loan Interest** | Up to $2,500/year | Education |

### RBI Prepayment Rules

- **Floating rate loans**: 0% prepayment penalty (RBI circular 2014)
- **Fixed rate loans**: Bank-specific foreclosure charges (typically 2-4%)

---

## Production Readiness

### CTO Architecture Review: 8.2 / 10 — PASS (Conditional)

| Domain | Score | Weight |
|:-------|:------|:-------|
| Security & Auth | 9/10 | 25% |
| Financial Math Accuracy | **10/10** | 20% |
| Database Design | 9/10 | 15% |
| Service Integration | 9/10 | 15% |
| Frontend Architecture | 8/10 | 10% |
| Infrastructure & DevOps | 7/10 | 10% |
| Code Quality & Patterns | 8/10 | 5% |

> Full report: [`docs/CTO_REVIEW.md`](docs/CTO_REVIEW.md)

### Build Stats

| Metric | Value |
|:-------|:------|
| Backend tests | **717** passing across 30 files |
| Frontend tests | **163** passing across 12 files |
| Critical-path JS | **94 KB** gzipped (target: <170 KB) |
| EMI verified against | SBI, HDFC bank calculators |
| Decimal precision | 28 digits, ROUND_HALF_UP to paisa |
| Scanner strategies | 2-cascade (GPT-4o Vision → pdfplumber + Regex) |
| Supported currencies | INR, USD (auto-detected) |

---

## DPDP Act 2023 Compliance

This application includes infrastructure for India's **Digital Personal Data Protection Act**:

- **Consent Manager** — Timestamped records before any data processing
- **Right to Erasure** — `DELETE /api/user/delete-account` cascades all user data
- **Data Export** — `POST /api/user/export-data` returns full JSON dump
- **Audit Trail** — All operations logged in `audit_logs` table
- **Purpose Limitation** — Consent specifies exact usage purpose

---

## Testing

### Backend (pytest)

```bash
cd backend
pip install -r requirements.txt
pytest -v --tb=short
```

**717+ tests** across 30 files covering:

- `test_financial_math.py` — EMI calculation, amortization, reverse EMI, edge cases
- `test_strategies.py` — All 4 repayment strategies with freed-EMI rollover
- `test_indian_rules.py` — Tax deductions (80C, 24b, 80E, 80EEA), RBI prepayment rules
- `test_optimization.py` — Multi-loan optimizer integration
- `test_scanner_service.py` — Scanner extraction, currency detection, dual-pattern matching
- `test_*_routes.py` — API endpoint request/response validation
- `test_*_integration.py` — End-to-end integration tests
- `test_*_service.py` — AI, auth, blob, translator, TTS service mocks
- `test_schemas.py` — Pydantic model validation
- `test_country_rules.py`, `test_usa_rules.py` — Multi-country tax rules

### Frontend (vitest)

```bash
cd frontend
npm install
npm test
```

**163+ tests** across 12 files.

---

## Development Workflow

### Local Development (recommended)

1. **Start the database** — `docker compose up -d` (PostgreSQL 16 + pgvector on port 5432)
2. **Start the backend** — `cd backend && uvicorn app.main:app --reload --port 8000`
3. **Start the frontend** — `cd frontend && npm run dev` (Vite dev server on port 5173)

### Key Development Patterns

- **State management**: Zustand stores — no Redux boilerplate
- **Server state**: TanStack Query with 5-minute stale time, 2 retries
- **API client**: Axios with auto-attached Firebase token and global error handling
- **Routing**: React Router v7 with lazy-loaded pages for code-splitting
- **i18n**: i18next with JSON locale files — add languages by creating `locales/xx.json`
- **Financial math**: All monetary calculations use Python `Decimal` with 28-digit precision
- **Auth flow**: Firebase client SDK → `getIdToken()` → Bearer header → server verification
- **Currency detection**: Auto-detect INR/USD from scanned documents, switch country context

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

**Built with [Claude Code](https://claude.ai/claude-code)**

---

[Report Bug](https://github.com/DandaAkhilReddy/Claude_Loan_Management_Indian/issues) | [Request Feature](https://github.com/DandaAkhilReddy/Claude_Loan_Management_Indian/issues)

</div>
