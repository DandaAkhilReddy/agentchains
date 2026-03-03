# AgentChains — Portfolio Showcase

> A USD-first AI agent marketplace with WebMCP, MCP, and A2A protocol support.
> Publish trusted agent outputs, get paid when others reuse them.

**GitHub**: [DandaAkhilReddy/agentchains](https://github.com/DandaAkhilReddy/agentchains)
**Live**: [agentchains-marketplace.orangemeadow-3bb536df.eastus.azurecontainerapps.io](https://agentchains-marketplace.orangemeadow-3bb536df.eastus.azurecontainerapps.io)

---

## By The Numbers

| Metric | Count |
|--------|-------|
| API endpoints | **247** (231 in `marketplace/api/` + 16 elsewhere) |
| A2A agents (registered) | **16** |
| Agent implementations | **117+** additional in `agents/` subdirectories |
| Chain templates | **5** pre-built DAG pipelines |
| DB models (SQLAlchemy) | **71 tables** |
| MCP tools | **11** |
| Protocols | **7** (MCP, A2A, WebMCP, A2UI, gRPC, GraphQL, OAuth2) |
| Bicep modules | **11** (1 root + 10 in `infra/modules/`) |
| Test files | **209** (204 backend + 5 agent) |
| Test functions | **~6,983** (6,607 backend + 376 agent) |
| Frontend pages | **25** |
| A2UI widgets | **12** |
| Trust pipeline stages | **5** |
| CDN tiers | **3** (hot/warm/cold) |

---

## Architecture & Skills

### Distributed Systems

LangGraph DAG orchestrator with Kahn's algorithm topological sort and concurrent layer execution. 3-tier CDN (hot = in-memory LFU, warm = TTL cache, cold = HashFS disk) with auto-promotion at 10 hits/min. Circuit breakers for external service resilience.

### AI/ML Engineering

16 A2A agents covering NER (regex-based entity extraction), TF-IDF text classification, extractive summarization (word-frequency scoring), keyword-based sentiment analysis, and Flesch-Kincaid readability scoring. LangGraph smart orchestrator with a 5-step pipeline for automated agent chaining.

### Backend Engineering

FastAPI async backend. SQLAlchemy async ORM with 71 models. Pydantic v2 for request/response validation. 100% async I/O throughout. 247 endpoints spanning API versions v1 through v5.

### Security & Auth

5-stage trust verification pipeline (provenance, integrity, safety, reproducibility, policy). RBAC with agent/creator/admin/user roles. JWT access tokens + OAuth2 flows. Scoped stream tokens for WebSocket authentication.

### Financial Engineering

USD-first billing and payouts. Stripe and Razorpay payment integration. Settlement engine for creator earnings. Automated invoicing. Token ledger for usage tracking and metering.

### Protocol Engineering

Seven protocols integrated into one platform:

- **A2A** — agent-to-agent communication
- **MCP** — 11 tools exposed for Claude Code integration
- **GraphQL** — flexible query layer
- **gRPC** — high-performance RPC
- **WebSocket** — real-time event streaming
- **A2UI** — agent-to-UI structured rendering
- **OAuth2** — third-party authorization

### Frontend

React 19 with TypeScript. 25 pages covering marketplace browsing, agent dashboards, creator tools, admin panels, and buyer flows. 12 A2UI widgets for structured agent output rendering.

### Cloud & DevOps

11 Bicep IaC modules: ACR, Container Apps, PostgreSQL Flexible Server, Redis Cache, Blob Storage, Key Vault, AI Search, Service Bus, Application Insights, OpenAI, and root orchestration. CI/CD via GitHub Actions. Docker containerization. OpenTelemetry instrumentation.

### Testing

~6,983 tests across 209 test files. Backend unit and integration tests, agent protocol tests, frontend component tests. SAST scanning and secret detection in CI.

---

## The 16 A2A Agents

| Agent | Skill | Category | Description |
|-------|-------|----------|-------------|
| Web Search | `web-search` | Data | Structured web search results with titles, URLs, snippets |
| Paper Finder | `find-papers` | Data | Academic paper search with titles, authors, DOIs, citation counts |
| Data Enricher | `enrich-data` | Data | URL parsing with domain metadata, categories, content-type guesses |
| Sentiment Analyzer | `analyze-sentiment` | Analysis | Keyword-based sentiment scoring ([-1, 1] range) with confidence |
| Text Classifier | `classify-text` | Analysis | TF-IDF keyword scoring, top-3 category matches with confidence |
| NER Extractor | `extract-entities` | Analysis | Regex NER for PERSON, ORG, DATE, EMAIL, PHONE, URL, MONEY, PERCENTAGE |
| Readability Scorer | `score-readability` | Analysis | Flesch Reading Ease + Flesch-Kincaid Grade Level with statistics |
| Document Summarizer | `summarize` | Transform | Extractive summarization via word-frequency scoring |
| Language Detector | `detect-language` | Transform | Trigram frequency + Unicode block detection, BCP-47 codes |
| JSON Normalizer | `normalize-json` | Transform | Nested JSON flattening to dot-notation with structural metadata |
| Message Translator | `translate` | Transform | Dictionary-based English-to-target translation for localization |
| PII Redactor | `redact-pii` | Compliance | Regex PII detection: emails, SSNs, credit cards, phones, IPs |
| Schema Validator | `validate-schema` | Compliance | Recursive JSON Schema validation with full error collection |
| Report Generator | `generate-report` | Output | Structured Markdown reports from upstream agent data |
| Tag Generator | `generate-tags` | Output | TF-IDF keyword + bigram extraction for content tagging |
| Headline Generator | `generate-headline` | Output | Extractive headline generation with news/academic/casual styles |

---

## Pre-built Chain Templates

Five DAG-based chain templates ready for one-click deployment:

### 1. Research Pipeline

```
paper_finder → doc_summarizer → sentiment_analyzer → report_generator
```

Find papers, summarize them, analyze sentiment, generate a structured report.

### 2. Content Localization

```
web_search → language_detector → message_translator → doc_summarizer
```

Search content, detect language, translate, and summarize for target audience.

### 3. Data Quality

```
data_enricher → json_normalizer → schema_validator → report_generator
```

Enrich raw data, normalize structure, validate against schema, report results.

### 4. Content Analysis

```
web_search → [ner_extractor, sentiment_analyzer, text_classifier] (parallel) → tag_generator → report_generator
```

Search content, run NER + sentiment + classification in parallel, tag and report.

### 5. Privacy Compliance

```
ner_extractor → pii_redactor → schema_validator → report_generator
```

Extract entities, redact PII, validate output schema, generate compliance report.

---

## Tech Stack

Python 3.11 | FastAPI | SQLAlchemy Async | Pydantic v2 | LangGraph | React 19 | TypeScript | Vite | Tailwind CSS | Azure Container Apps | PostgreSQL | Redis | Blob Storage | Key Vault | AI Search | Service Bus | Application Insights | Bicep IaC | Docker | GitHub Actions | OpenTelemetry | Stripe | Razorpay

---

## Live Demo

| Resource | URL |
|----------|-----|
| API Docs (Swagger) | [/docs](https://agentchains-marketplace.orangemeadow-3bb536df.eastus.azurecontainerapps.io/docs) |
| Frontend | [/](https://agentchains-marketplace.orangemeadow-3bb536df.eastus.azurecontainerapps.io) |
| Health Check | [/api/v1/health](https://agentchains-marketplace.orangemeadow-3bb536df.eastus.azurecontainerapps.io/api/v1/health) |
