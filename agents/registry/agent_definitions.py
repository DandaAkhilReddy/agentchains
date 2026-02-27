"""Agent definition registry for all 100 AgentChains agents.

Defines the frozen dataclass AgentDefinition and the canonical list of all
agents across 10 categories (10 per category, 100 total).  Five of these are
real agents (``is_stub=False``); the remaining 95 are scaffold stubs.

Provides helper functions for lookup by slug and category.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentDefinition:
    """Immutable description of a single agent in the registry.

    Args:
        slug: URL-safe kebab-case identifier (e.g. ``sentiment-analyzer``).
        name: Human-readable display name.
        category: One of the 10 top-level categories.
        description: One-sentence description of what the agent does.
        skills: Tuple of skill dicts, each with ``id``, ``name``, ``description``.
        is_stub: True if the agent body is a placeholder (not yet implemented).
        port: Port the agent's A2A server listens on.
    """

    slug: str
    name: str
    category: str
    description: str
    skills: tuple[dict, ...]
    is_stub: bool
    port: int


# ---------------------------------------------------------------------------
# Canonical list of all 100 agents (10 categories × 10 agents)
# ---------------------------------------------------------------------------

AGENT_DEFINITIONS: list[AgentDefinition] = [
    # ── AI/ML (10 agents: ports 9100-9108 stubs + port 9005 real) ───────────
    AgentDefinition(
        slug="knowledge-broker-agent",
        name="Knowledge Broker Agent",
        category="AI/ML",
        description="Coordinates supply and demand on the marketplace without producing data itself.",
        skills=(
            {
                "id": "knowledge-broker-agent/analyze-market",
                "name": "Analyze Market",
                "description": "Provide a full market analysis combining trending, gaps, and opportunities.",
            },
            {
                "id": "knowledge-broker-agent/match-supply",
                "name": "Match Supply to Demand",
                "description": "Check if existing marketplace supply can fill a demand query.",
            },
        ),
        is_stub=False,
        port=9005,
    ),
    AgentDefinition(
        slug="sentiment-analyzer",
        name="Sentiment Analyzer",
        category="AI/ML",
        description="Analyzes text to determine sentiment polarity and intensity.",
        skills=(
            {
                "id": "sentiment-analyzer/analyze",
                "name": "Analyze Sentiment",
                "description": "Return sentiment score and label for a given text input.",
            },
        ),
        is_stub=True,
        port=9100,
    ),
    AgentDefinition(
        slug="text-classifier",
        name="Text Classifier",
        category="AI/ML",
        description="Classifies text into predefined categories using ML models.",
        skills=(
            {
                "id": "text-classifier/classify",
                "name": "Classify Text",
                "description": "Assign one or more labels to a block of text.",
            },
        ),
        is_stub=True,
        port=9101,
    ),
    AgentDefinition(
        slug="ner-extractor",
        name="NER Extractor",
        category="AI/ML",
        description="Extracts named entities (people, places, organisations) from text.",
        skills=(
            {
                "id": "ner-extractor/extract",
                "name": "Extract Entities",
                "description": "Identify and label named entities in the provided text.",
            },
        ),
        is_stub=True,
        port=9102,
    ),
    AgentDefinition(
        slug="embeddings-generator",
        name="Embeddings Generator",
        category="AI/ML",
        description="Generates dense vector embeddings for text using transformer models.",
        skills=(
            {
                "id": "embeddings-generator/embed",
                "name": "Generate Embeddings",
                "description": "Produce a float vector embedding for the given text.",
            },
        ),
        is_stub=True,
        port=9103,
    ),
    AgentDefinition(
        slug="topic-modeler",
        name="Topic Modeler",
        category="AI/ML",
        description="Discovers latent topics within a collection of documents.",
        skills=(
            {
                "id": "topic-modeler/model",
                "name": "Model Topics",
                "description": "Return top topics and their representative keywords.",
            },
        ),
        is_stub=True,
        port=9104,
    ),
    AgentDefinition(
        slug="language-detector",
        name="Language Detector",
        category="AI/ML",
        description="Detects the natural language of an input text string.",
        skills=(
            {
                "id": "language-detector/detect",
                "name": "Detect Language",
                "description": "Return BCP-47 language tag and confidence for the input.",
            },
        ),
        is_stub=True,
        port=9105,
    ),
    AgentDefinition(
        slug="summarizer-v2",
        name="Summarizer v2",
        category="AI/ML",
        description="Produces abstractive summaries of long documents using LLMs.",
        skills=(
            {
                "id": "summarizer-v2/summarize",
                "name": "Summarize Document",
                "description": "Generate a concise summary of the supplied document.",
            },
        ),
        is_stub=True,
        port=9106,
    ),
    AgentDefinition(
        slug="image-captioner",
        name="Image Captioner",
        category="AI/ML",
        description="Generates natural-language captions for images from URLs or base64.",
        skills=(
            {
                "id": "image-captioner/caption",
                "name": "Caption Image",
                "description": "Produce a descriptive caption for the provided image.",
            },
        ),
        is_stub=True,
        port=9107,
    ),
    AgentDefinition(
        slug="intent-recognizer",
        name="Intent Recognizer",
        category="AI/ML",
        description="Recognizes user intent and extracts slots from conversational input.",
        skills=(
            {
                "id": "intent-recognizer/recognize",
                "name": "Recognize Intent",
                "description": "Return the top intent and extracted slot values for the utterance.",
            },
        ),
        is_stub=True,
        port=9108,
    ),
    # ── Data Processing (10 agents: ports 9110-9119) ─────────────────────────
    AgentDefinition(
        slug="csv-transformer",
        name="CSV Transformer",
        category="Data Processing",
        description="Transforms, filters, and reshapes CSV data with declarative rules.",
        skills=(
            {
                "id": "csv-transformer/transform",
                "name": "Transform CSV",
                "description": "Apply column mappings, filters, and aggregations to CSV data.",
            },
        ),
        is_stub=True,
        port=9110,
    ),
    AgentDefinition(
        slug="json-normalizer",
        name="JSON Normalizer",
        category="Data Processing",
        description="Normalises nested JSON structures into flat tabular representations.",
        skills=(
            {
                "id": "json-normalizer/normalize",
                "name": "Normalize JSON",
                "description": "Flatten nested JSON into a consistent key-value structure.",
            },
        ),
        is_stub=True,
        port=9111,
    ),
    AgentDefinition(
        slug="data-deduplicator",
        name="Data Deduplicator",
        category="Data Processing",
        description="Identifies and removes duplicate records from structured datasets.",
        skills=(
            {
                "id": "data-deduplicator/deduplicate",
                "name": "Deduplicate Records",
                "description": "Return a deduplicated version of the supplied dataset.",
            },
        ),
        is_stub=True,
        port=9112,
    ),
    AgentDefinition(
        slug="schema-validator",
        name="Schema Validator",
        category="Data Processing",
        description="Validates data payloads against JSON Schema or Pydantic models.",
        skills=(
            {
                "id": "schema-validator/validate",
                "name": "Validate Schema",
                "description": "Check whether the data conforms to the provided schema.",
            },
        ),
        is_stub=True,
        port=9113,
    ),
    AgentDefinition(
        slug="xml-parser",
        name="XML Parser",
        category="Data Processing",
        description="Parses XML documents and converts them to JSON or structured objects.",
        skills=(
            {
                "id": "xml-parser/parse",
                "name": "Parse XML",
                "description": "Convert an XML document into a structured JSON representation.",
            },
        ),
        is_stub=True,
        port=9114,
    ),
    AgentDefinition(
        slug="data-enricher",
        name="Data Enricher",
        category="Data Processing",
        description="Enriches records with external lookup data from configured sources.",
        skills=(
            {
                "id": "data-enricher/enrich",
                "name": "Enrich Record",
                "description": "Augment each record with additional fields from external sources.",
            },
        ),
        is_stub=True,
        port=9115,
    ),
    AgentDefinition(
        slug="batch-processor",
        name="Batch Processor",
        category="Data Processing",
        description="Executes configurable transformation pipelines over large data batches.",
        skills=(
            {
                "id": "batch-processor/process",
                "name": "Process Batch",
                "description": "Run a named pipeline over the supplied batch of records.",
            },
        ),
        is_stub=True,
        port=9116,
    ),
    AgentDefinition(
        slug="stream-processor",
        name="Stream Processor",
        category="Data Processing",
        description="Applies real-time transformations to streaming event data.",
        skills=(
            {
                "id": "stream-processor/process",
                "name": "Process Stream",
                "description": "Apply filter and transform rules to a live event stream.",
            },
        ),
        is_stub=True,
        port=9117,
    ),
    AgentDefinition(
        slug="data-sampler",
        name="Data Sampler",
        category="Data Processing",
        description="Produces statistically representative samples from large datasets.",
        skills=(
            {
                "id": "data-sampler/sample",
                "name": "Sample Dataset",
                "description": "Return a random or stratified sample from the input data.",
            },
        ),
        is_stub=True,
        port=9118,
    ),
    AgentDefinition(
        slug="format-converter",
        name="Format Converter",
        category="Data Processing",
        description="Converts data between formats such as CSV, JSON, Parquet, and YAML.",
        skills=(
            {
                "id": "format-converter/convert",
                "name": "Convert Format",
                "description": "Transcode data from a source format into the requested target format.",
            },
        ),
        is_stub=True,
        port=9119,
    ),
    # ── Communication (10 agents: ports 9120-9129) ───────────────────────────
    AgentDefinition(
        slug="email-sender",
        name="Email Sender",
        category="Communication",
        description="Sends transactional and bulk emails via configured SMTP or API providers.",
        skills=(
            {
                "id": "email-sender/send",
                "name": "Send Email",
                "description": "Deliver an email message to one or more recipients.",
            },
        ),
        is_stub=True,
        port=9120,
    ),
    AgentDefinition(
        slug="slack-notifier",
        name="Slack Notifier",
        category="Communication",
        description="Posts messages and rich attachments to Slack channels or users.",
        skills=(
            {
                "id": "slack-notifier/notify",
                "name": "Notify Slack",
                "description": "Send a structured notification to the specified Slack channel.",
            },
        ),
        is_stub=True,
        port=9121,
    ),
    AgentDefinition(
        slug="webhook-dispatcher",
        name="Webhook Dispatcher",
        category="Communication",
        description="Dispatches HTTP webhook events to configured downstream endpoints.",
        skills=(
            {
                "id": "webhook-dispatcher/dispatch",
                "name": "Dispatch Webhook",
                "description": "POST a signed event payload to the registered webhook URL.",
            },
        ),
        is_stub=True,
        port=9122,
    ),
    AgentDefinition(
        slug="chat-router",
        name="Chat Router",
        category="Communication",
        description="Routes incoming chat messages to the appropriate agent or queue.",
        skills=(
            {
                "id": "chat-router/route",
                "name": "Route Message",
                "description": "Classify and route the message to the correct downstream handler.",
            },
        ),
        is_stub=True,
        port=9123,
    ),
    AgentDefinition(
        slug="sms-gateway",
        name="SMS Gateway",
        category="Communication",
        description="Sends SMS messages via Twilio, Vonage, or other configured providers.",
        skills=(
            {
                "id": "sms-gateway/send",
                "name": "Send SMS",
                "description": "Deliver an SMS message to the specified phone number.",
            },
        ),
        is_stub=True,
        port=9124,
    ),
    AgentDefinition(
        slug="push-notifier",
        name="Push Notifier",
        category="Communication",
        description="Sends mobile push notifications via APNs and FCM.",
        skills=(
            {
                "id": "push-notifier/push",
                "name": "Send Push",
                "description": "Deliver a push notification to the specified device token.",
            },
        ),
        is_stub=True,
        port=9125,
    ),
    AgentDefinition(
        slug="notification-aggregator",
        name="Notification Aggregator",
        category="Communication",
        description="Aggregates and deduplicates notifications before delivering to end users.",
        skills=(
            {
                "id": "notification-aggregator/aggregate",
                "name": "Aggregate Notifications",
                "description": "Collect and batch notifications for a user within a time window.",
            },
        ),
        is_stub=True,
        port=9126,
    ),
    AgentDefinition(
        slug="message-translator",
        name="Message Translator",
        category="Communication",
        description="Translates messages between human languages in real time.",
        skills=(
            {
                "id": "message-translator/translate",
                "name": "Translate Message",
                "description": "Return the message translated into the requested target language.",
            },
        ),
        is_stub=True,
        port=9127,
    ),
    AgentDefinition(
        slug="broadcast-manager",
        name="Broadcast Manager",
        category="Communication",
        description="Manages broadcast lists and schedules mass communications across channels.",
        skills=(
            {
                "id": "broadcast-manager/broadcast",
                "name": "Send Broadcast",
                "description": "Distribute a message to all subscribers in a named list.",
            },
        ),
        is_stub=True,
        port=9128,
    ),
    AgentDefinition(
        slug="alert-escalator",
        name="Alert Escalator",
        category="Communication",
        description="Escalates alerts through on-call rotation policies when initial responders are unavailable.",
        skills=(
            {
                "id": "alert-escalator/escalate",
                "name": "Escalate Alert",
                "description": "Page the next available on-call responder for the given alert.",
            },
        ),
        is_stub=True,
        port=9129,
    ),
    # ── Security (10 agents: ports 9130-9139) ────────────────────────────────
    AgentDefinition(
        slug="vulnerability-scanner",
        name="Vulnerability Scanner",
        category="Security",
        description="Scans codebases and container images for known CVEs and misconfigurations.",
        skills=(
            {
                "id": "vulnerability-scanner/scan",
                "name": "Scan Vulnerabilities",
                "description": "Return a ranked list of vulnerabilities found in the target.",
            },
        ),
        is_stub=True,
        port=9130,
    ),
    AgentDefinition(
        slug="secret-detector",
        name="Secret Detector",
        category="Security",
        description="Detects accidentally committed secrets, API keys, and credentials in code.",
        skills=(
            {
                "id": "secret-detector/detect",
                "name": "Detect Secrets",
                "description": "Scan the provided content and report any detected secrets.",
            },
        ),
        is_stub=True,
        port=9131,
    ),
    AgentDefinition(
        slug="pii-redactor",
        name="PII Redactor",
        category="Security",
        description="Identifies and redacts personally identifiable information from text.",
        skills=(
            {
                "id": "pii-redactor/redact",
                "name": "Redact PII",
                "description": "Replace PII entities in the text with anonymised placeholders.",
            },
        ),
        is_stub=True,
        port=9132,
    ),
    AgentDefinition(
        slug="access-auditor",
        name="Access Auditor",
        category="Security",
        description="Audits access logs and permission grants for anomalous behaviour.",
        skills=(
            {
                "id": "access-auditor/audit",
                "name": "Audit Access",
                "description": "Analyse access logs and return a report of suspicious events.",
            },
        ),
        is_stub=True,
        port=9133,
    ),
    AgentDefinition(
        slug="threat-analyzer",
        name="Threat Analyzer",
        category="Security",
        description="Analyses threat intelligence feeds and correlates indicators of compromise.",
        skills=(
            {
                "id": "threat-analyzer/analyze",
                "name": "Analyze Threats",
                "description": "Correlate IOCs against threat intel feeds and score severity.",
            },
        ),
        is_stub=True,
        port=9134,
    ),
    AgentDefinition(
        slug="compliance-checker",
        name="Compliance Checker",
        category="Security",
        description="Checks system configurations against GDPR, SOC 2, and other compliance frameworks.",
        skills=(
            {
                "id": "compliance-checker/check",
                "name": "Check Compliance",
                "description": "Evaluate the configuration against the specified compliance framework.",
            },
        ),
        is_stub=True,
        port=9135,
    ),
    AgentDefinition(
        slug="encryption-helper",
        name="Encryption Helper",
        category="Security",
        description="Provides encryption, decryption, and key management utilities.",
        skills=(
            {
                "id": "encryption-helper/encrypt",
                "name": "Encrypt Data",
                "description": "Encrypt the payload using the specified algorithm and key reference.",
            },
        ),
        is_stub=True,
        port=9136,
    ),
    AgentDefinition(
        slug="token-rotator",
        name="Token Rotator",
        category="Security",
        description="Automates rotation of API tokens and secrets on a configurable schedule.",
        skills=(
            {
                "id": "token-rotator/rotate",
                "name": "Rotate Token",
                "description": "Revoke the current token and issue a fresh one for the target service.",
            },
        ),
        is_stub=True,
        port=9137,
    ),
    AgentDefinition(
        slug="firewall-advisor",
        name="Firewall Advisor",
        category="Security",
        description="Recommends firewall rule changes based on traffic patterns and policy.",
        skills=(
            {
                "id": "firewall-advisor/advise",
                "name": "Advise Firewall Rules",
                "description": "Suggest rule additions or removals based on observed traffic.",
            },
        ),
        is_stub=True,
        port=9138,
    ),
    AgentDefinition(
        slug="incident-reporter",
        name="Incident Reporter",
        category="Security",
        description="Compiles and distributes structured security incident reports.",
        skills=(
            {
                "id": "incident-reporter/report",
                "name": "Report Incident",
                "description": "Generate a structured incident report from the provided event data.",
            },
        ),
        is_stub=True,
        port=9139,
    ),
    # ── Analytics (10 agents: ports 9140-9149) ───────────────────────────────
    AgentDefinition(
        slug="trend-analyzer",
        name="Trend Analyzer",
        category="Analytics",
        description="Identifies temporal trends in time-series data and forecasts direction.",
        skills=(
            {
                "id": "trend-analyzer/analyze",
                "name": "Analyze Trends",
                "description": "Return trend direction, slope, and seasonal decomposition.",
            },
        ),
        is_stub=True,
        port=9140,
    ),
    AgentDefinition(
        slug="cohort-builder",
        name="Cohort Builder",
        category="Analytics",
        description="Builds user cohorts based on behaviour, attributes, and time windows.",
        skills=(
            {
                "id": "cohort-builder/build",
                "name": "Build Cohort",
                "description": "Define and materialise a user cohort from the supplied criteria.",
            },
        ),
        is_stub=True,
        port=9141,
    ),
    AgentDefinition(
        slug="forecast-engine",
        name="Forecast Engine",
        category="Analytics",
        description="Generates time-series forecasts using statistical and ML models.",
        skills=(
            {
                "id": "forecast-engine/forecast",
                "name": "Forecast Metric",
                "description": "Produce a forward-looking forecast with confidence intervals.",
            },
        ),
        is_stub=True,
        port=9142,
    ),
    AgentDefinition(
        slug="anomaly-detector",
        name="Anomaly Detector",
        category="Analytics",
        description="Detects statistical anomalies in metrics and time-series streams.",
        skills=(
            {
                "id": "anomaly-detector/detect",
                "name": "Detect Anomalies",
                "description": "Flag data points that deviate significantly from expected patterns.",
            },
        ),
        is_stub=True,
        port=9143,
    ),
    AgentDefinition(
        slug="funnel-tracker",
        name="Funnel Tracker",
        category="Analytics",
        description="Tracks conversion funnels and identifies drop-off points.",
        skills=(
            {
                "id": "funnel-tracker/track",
                "name": "Track Funnel",
                "description": "Compute conversion rates and drop-off for each funnel stage.",
            },
        ),
        is_stub=True,
        port=9144,
    ),
    AgentDefinition(
        slug="retention-analyzer",
        name="Retention Analyzer",
        category="Analytics",
        description="Computes retention curves and churn metrics from user event data.",
        skills=(
            {
                "id": "retention-analyzer/analyze",
                "name": "Analyze Retention",
                "description": "Return day-N retention rates and churn probability estimates.",
            },
        ),
        is_stub=True,
        port=9145,
    ),
    AgentDefinition(
        slug="ab-test-evaluator",
        name="A/B Test Evaluator",
        category="Analytics",
        description="Evaluates A/B experiments for statistical significance and effect size.",
        skills=(
            {
                "id": "ab-test-evaluator/evaluate",
                "name": "Evaluate A/B Test",
                "description": "Compute p-value, confidence intervals, and recommended winner.",
            },
        ),
        is_stub=True,
        port=9146,
    ),
    AgentDefinition(
        slug="metric-aggregator",
        name="Metric Aggregator",
        category="Analytics",
        description="Aggregates raw event data into named metrics with configurable windows.",
        skills=(
            {
                "id": "metric-aggregator/aggregate",
                "name": "Aggregate Metrics",
                "description": "Compute sum, mean, p99, and other aggregations over events.",
            },
        ),
        is_stub=True,
        port=9147,
    ),
    AgentDefinition(
        slug="report-generator",
        name="Report Generator",
        category="Analytics",
        description="Generates formatted analytics reports from query results and templates.",
        skills=(
            {
                "id": "report-generator/generate",
                "name": "Generate Report",
                "description": "Produce a formatted report from the supplied metrics and template.",
            },
        ),
        is_stub=True,
        port=9148,
    ),
    AgentDefinition(
        slug="dashboard-builder",
        name="Dashboard Builder",
        category="Analytics",
        description="Constructs dashboard configurations from metric definitions.",
        skills=(
            {
                "id": "dashboard-builder/build",
                "name": "Build Dashboard",
                "description": "Generate a dashboard layout JSON from the provided metric specs.",
            },
        ),
        is_stub=True,
        port=9149,
    ),
    # ── Utilities (10 agents: ports 9150-9159) ───────────────────────────────
    AgentDefinition(
        slug="cron-scheduler",
        name="Cron Scheduler",
        category="Utilities",
        description="Manages cron-style scheduled jobs and triggers downstream agents.",
        skills=(
            {
                "id": "cron-scheduler/schedule",
                "name": "Schedule Job",
                "description": "Register a cron expression and target to invoke on schedule.",
            },
        ),
        is_stub=True,
        port=9150,
    ),
    AgentDefinition(
        slug="file-converter",
        name="File Converter",
        category="Utilities",
        description="Converts files between common formats such as DOCX, PDF, and Markdown.",
        skills=(
            {
                "id": "file-converter/convert",
                "name": "Convert File",
                "description": "Return the file converted into the requested output format.",
            },
        ),
        is_stub=True,
        port=9151,
    ),
    AgentDefinition(
        slug="pdf-generator",
        name="PDF Generator",
        category="Utilities",
        description="Generates PDF documents from HTML templates and structured data.",
        skills=(
            {
                "id": "pdf-generator/generate",
                "name": "Generate PDF",
                "description": "Render the supplied HTML or template into a downloadable PDF.",
            },
        ),
        is_stub=True,
        port=9152,
    ),
    AgentDefinition(
        slug="currency-converter",
        name="Currency Converter",
        category="Utilities",
        description="Converts amounts between currencies using live or cached exchange rates.",
        skills=(
            {
                "id": "currency-converter/convert",
                "name": "Convert Currency",
                "description": "Return the converted amount using the latest exchange rate.",
            },
        ),
        is_stub=True,
        port=9153,
    ),
    AgentDefinition(
        slug="url-shortener",
        name="URL Shortener",
        category="Utilities",
        description="Creates and manages short URLs with click-tracking analytics.",
        skills=(
            {
                "id": "url-shortener/shorten",
                "name": "Shorten URL",
                "description": "Create a short alias for the provided long URL.",
            },
        ),
        is_stub=True,
        port=9154,
    ),
    AgentDefinition(
        slug="qr-generator",
        name="QR Generator",
        category="Utilities",
        description="Generates QR codes for URLs, vCards, and structured payloads.",
        skills=(
            {
                "id": "qr-generator/generate",
                "name": "Generate QR Code",
                "description": "Return a QR code image encoded in the requested format.",
            },
        ),
        is_stub=True,
        port=9155,
    ),
    AgentDefinition(
        slug="hash-calculator",
        name="Hash Calculator",
        category="Utilities",
        description="Computes cryptographic hashes (MD5, SHA-256, SHA-512, BLAKE2) for data.",
        skills=(
            {
                "id": "hash-calculator/calculate",
                "name": "Calculate Hash",
                "description": "Return the hash of the input using the specified algorithm.",
            },
        ),
        is_stub=True,
        port=9156,
    ),
    AgentDefinition(
        slug="regex-tester",
        name="Regex Tester",
        category="Utilities",
        description="Tests regular expressions against sample inputs and explains matches.",
        skills=(
            {
                "id": "regex-tester/test",
                "name": "Test Regex",
                "description": "Apply the regex to the input and return all match groups.",
            },
        ),
        is_stub=True,
        port=9157,
    ),
    AgentDefinition(
        slug="timezone-converter",
        name="Timezone Converter",
        category="Utilities",
        description="Converts datetimes between IANA timezones with DST awareness.",
        skills=(
            {
                "id": "timezone-converter/convert",
                "name": "Convert Timezone",
                "description": "Return the datetime expressed in the target IANA timezone.",
            },
        ),
        is_stub=True,
        port=9158,
    ),
    AgentDefinition(
        slug="unit-converter",
        name="Unit Converter",
        category="Utilities",
        description="Converts measurements between SI and imperial units across domains.",
        skills=(
            {
                "id": "unit-converter/convert",
                "name": "Convert Units",
                "description": "Return the value converted from the source unit to the target unit.",
            },
        ),
        is_stub=True,
        port=9159,
    ),
    # ── Finance (10 agents: ports 9160-9168 stubs + port 9001 real) ─────────
    AgentDefinition(
        slug="buyer-agent",
        name="Buyer Agent",
        category="Finance",
        description="Discovers and purchases data from the marketplace on behalf of users.",
        skills=(
            {
                "id": "buyer-agent/find-and-buy",
                "name": "Find and Buy",
                "description": "Search the marketplace and purchase the best matching listing.",
            },
            {
                "id": "buyer-agent/browse",
                "name": "Browse Marketplace",
                "description": "Browse available listings on the marketplace.",
            },
        ),
        is_stub=False,
        port=9001,
    ),
    AgentDefinition(
        slug="invoice-generator",
        name="Invoice Generator",
        category="Finance",
        description="Generates professional invoices from line items and client details.",
        skills=(
            {
                "id": "invoice-generator/generate",
                "name": "Generate Invoice",
                "description": "Produce a formatted invoice PDF from the supplied billing data.",
            },
        ),
        is_stub=True,
        port=9160,
    ),
    AgentDefinition(
        slug="expense-tracker",
        name="Expense Tracker",
        category="Finance",
        description="Tracks and categorises business expenses from receipts and transactions.",
        skills=(
            {
                "id": "expense-tracker/track",
                "name": "Track Expense",
                "description": "Classify and record an expense entry in the ledger.",
            },
        ),
        is_stub=True,
        port=9161,
    ),
    AgentDefinition(
        slug="fraud-scorer",
        name="Fraud Scorer",
        category="Finance",
        description="Scores transactions for fraud risk using behavioural and graph features.",
        skills=(
            {
                "id": "fraud-scorer/score",
                "name": "Score Transaction",
                "description": "Return a fraud risk score and contributing feature explanations.",
            },
        ),
        is_stub=True,
        port=9162,
    ),
    AgentDefinition(
        slug="price-optimizer",
        name="Price Optimizer",
        category="Finance",
        description="Recommends optimal pricing based on demand elasticity and competition.",
        skills=(
            {
                "id": "price-optimizer/optimize",
                "name": "Optimize Price",
                "description": "Return the recommended price point for the given product context.",
            },
        ),
        is_stub=True,
        port=9163,
    ),
    AgentDefinition(
        slug="tax-calculator",
        name="Tax Calculator",
        category="Finance",
        description="Calculates tax obligations across jurisdictions for transactions.",
        skills=(
            {
                "id": "tax-calculator/calculate",
                "name": "Calculate Tax",
                "description": "Return applicable taxes for the transaction in the given jurisdiction.",
            },
        ),
        is_stub=True,
        port=9164,
    ),
    AgentDefinition(
        slug="payment-reconciler",
        name="Payment Reconciler",
        category="Finance",
        description="Reconciles payment records against bank statements and invoices.",
        skills=(
            {
                "id": "payment-reconciler/reconcile",
                "name": "Reconcile Payments",
                "description": "Match payment records to statements and flag discrepancies.",
            },
        ),
        is_stub=True,
        port=9165,
    ),
    AgentDefinition(
        slug="budget-planner",
        name="Budget Planner",
        category="Finance",
        description="Creates and monitors budgets with variance tracking and alerts.",
        skills=(
            {
                "id": "budget-planner/plan",
                "name": "Plan Budget",
                "description": "Generate a budget allocation plan from the supplied constraints.",
            },
        ),
        is_stub=True,
        port=9166,
    ),
    AgentDefinition(
        slug="revenue-forecaster",
        name="Revenue Forecaster",
        category="Finance",
        description="Forecasts revenue using historical data, seasonality, and growth drivers.",
        skills=(
            {
                "id": "revenue-forecaster/forecast",
                "name": "Forecast Revenue",
                "description": "Produce a revenue forecast for the requested period.",
            },
        ),
        is_stub=True,
        port=9167,
    ),
    AgentDefinition(
        slug="risk-assessor",
        name="Risk Assessor",
        category="Finance",
        description="Assesses financial and operational risk for projects and counterparties.",
        skills=(
            {
                "id": "risk-assessor/assess",
                "name": "Assess Risk",
                "description": "Return a structured risk assessment with likelihood and impact scores.",
            },
        ),
        is_stub=True,
        port=9168,
    ),
    # ── DevOps (10 agents: ports 9170-9178 stubs + port 9003 real) ──────────
    AgentDefinition(
        slug="code-analyzer-agent",
        name="Code Analyzer Agent",
        category="DevOps",
        description="Analyses source code for quality, complexity, and potential issues.",
        skills=(
            {
                "id": "code-analyzer-agent/analyze",
                "name": "Analyze Code",
                "description": "Return a quality and complexity analysis of the provided code.",
            },
        ),
        is_stub=False,
        port=9003,
    ),
    AgentDefinition(
        slug="ci-monitor",
        name="CI Monitor",
        category="DevOps",
        description="Monitors CI pipeline runs and reports build status and failures.",
        skills=(
            {
                "id": "ci-monitor/monitor",
                "name": "Monitor CI",
                "description": "Return the current status of the specified CI pipeline.",
            },
        ),
        is_stub=True,
        port=9170,
    ),
    AgentDefinition(
        slug="deployment-tracker",
        name="Deployment Tracker",
        category="DevOps",
        description="Tracks deployments across environments and surfaces rollback candidates.",
        skills=(
            {
                "id": "deployment-tracker/track",
                "name": "Track Deployment",
                "description": "Record and retrieve deployment history for the service.",
            },
        ),
        is_stub=True,
        port=9171,
    ),
    AgentDefinition(
        slug="uptime-checker",
        name="Uptime Checker",
        category="DevOps",
        description="Checks endpoint availability and measures response latency from multiple regions.",
        skills=(
            {
                "id": "uptime-checker/check",
                "name": "Check Uptime",
                "description": "Probe the URL and return availability and latency metrics.",
            },
        ),
        is_stub=True,
        port=9172,
    ),
    AgentDefinition(
        slug="dependency-updater",
        name="Dependency Updater",
        category="DevOps",
        description="Scans projects for outdated dependencies and opens update pull requests.",
        skills=(
            {
                "id": "dependency-updater/update",
                "name": "Update Dependencies",
                "description": "Identify outdated packages and propose upgrade diffs.",
            },
        ),
        is_stub=True,
        port=9173,
    ),
    AgentDefinition(
        slug="log-analyzer",
        name="Log Analyzer",
        category="DevOps",
        description="Parses and analyses application logs to surface errors and patterns.",
        skills=(
            {
                "id": "log-analyzer/analyze",
                "name": "Analyze Logs",
                "description": "Parse logs and return a summary of errors and anomalies.",
            },
        ),
        is_stub=True,
        port=9174,
    ),
    AgentDefinition(
        slug="config-manager",
        name="Config Manager",
        category="DevOps",
        description="Manages environment-specific configuration files with versioning and diff.",
        skills=(
            {
                "id": "config-manager/manage",
                "name": "Manage Config",
                "description": "Read, write, and diff configuration for the specified environment.",
            },
        ),
        is_stub=True,
        port=9175,
    ),
    AgentDefinition(
        slug="container-inspector",
        name="Container Inspector",
        category="DevOps",
        description="Inspects running containers for resource usage, layers, and security issues.",
        skills=(
            {
                "id": "container-inspector/inspect",
                "name": "Inspect Container",
                "description": "Return metadata, layer info, and resource stats for a container.",
            },
        ),
        is_stub=True,
        port=9176,
    ),
    AgentDefinition(
        slug="dns-resolver",
        name="DNS Resolver",
        category="DevOps",
        description="Resolves DNS records and diagnoses propagation issues.",
        skills=(
            {
                "id": "dns-resolver/resolve",
                "name": "Resolve DNS",
                "description": "Return all DNS records for the given domain from multiple resolvers.",
            },
        ),
        is_stub=True,
        port=9177,
    ),
    AgentDefinition(
        slug="ssl-checker",
        name="SSL Checker",
        category="DevOps",
        description="Inspects TLS certificates for validity, expiry, and cipher suite strength.",
        skills=(
            {
                "id": "ssl-checker/check",
                "name": "Check SSL",
                "description": "Return certificate chain, expiry, and cipher suite details.",
            },
        ),
        is_stub=True,
        port=9178,
    ),
    # ── Content (10 agents: ports 9180-9188 stubs + port 9004 real) ─────────
    AgentDefinition(
        slug="doc-summarizer-agent",
        name="Doc Summarizer Agent",
        category="Content",
        description="Summarises documents and lists the summaries for sale on the marketplace.",
        skills=(
            {
                "id": "doc-summarizer-agent/summarize",
                "name": "Summarize Document",
                "description": "Generate a concise summary of the supplied document.",
            },
        ),
        is_stub=False,
        port=9004,
    ),
    AgentDefinition(
        slug="article-writer",
        name="Article Writer",
        category="Content",
        description="Drafts long-form articles from outlines and keyword briefs.",
        skills=(
            {
                "id": "article-writer/write",
                "name": "Write Article",
                "description": "Generate a structured article from the provided brief.",
            },
        ),
        is_stub=True,
        port=9180,
    ),
    AgentDefinition(
        slug="tag-generator",
        name="Tag Generator",
        category="Content",
        description="Generates relevant tags and keywords for articles and media.",
        skills=(
            {
                "id": "tag-generator/generate",
                "name": "Generate Tags",
                "description": "Return a ranked list of tags for the supplied content.",
            },
        ),
        is_stub=True,
        port=9181,
    ),
    AgentDefinition(
        slug="seo-optimizer",
        name="SEO Optimizer",
        category="Content",
        description="Optimises content for search engines with keyword and metadata recommendations.",
        skills=(
            {
                "id": "seo-optimizer/optimize",
                "name": "Optimize SEO",
                "description": "Return SEO improvements for titles, meta tags, and body content.",
            },
        ),
        is_stub=True,
        port=9182,
    ),
    AgentDefinition(
        slug="readability-scorer",
        name="Readability Scorer",
        category="Content",
        description="Measures text readability using Flesch-Kincaid and other indices.",
        skills=(
            {
                "id": "readability-scorer/score",
                "name": "Score Readability",
                "description": "Return readability scores and grade-level estimates for the text.",
            },
        ),
        is_stub=True,
        port=9183,
    ),
    AgentDefinition(
        slug="plagiarism-checker",
        name="Plagiarism Checker",
        category="Content",
        description="Checks content originality by comparing against web and document corpora.",
        skills=(
            {
                "id": "plagiarism-checker/check",
                "name": "Check Plagiarism",
                "description": "Return a similarity report and source URLs for matching content.",
            },
        ),
        is_stub=True,
        port=9184,
    ),
    AgentDefinition(
        slug="headline-generator",
        name="Headline Generator",
        category="Content",
        description="Generates compelling headlines and titles optimised for click-through rates.",
        skills=(
            {
                "id": "headline-generator/generate",
                "name": "Generate Headlines",
                "description": "Produce multiple headline variants for the supplied article draft.",
            },
        ),
        is_stub=True,
        port=9185,
    ),
    AgentDefinition(
        slug="content-calendar",
        name="Content Calendar",
        category="Content",
        description="Plans and schedules content publication across multiple channels.",
        skills=(
            {
                "id": "content-calendar/plan",
                "name": "Plan Content Calendar",
                "description": "Generate a publication schedule from topics and channel constraints.",
            },
        ),
        is_stub=True,
        port=9186,
    ),
    AgentDefinition(
        slug="social-formatter",
        name="Social Formatter",
        category="Content",
        description="Formats content for specific social media platforms with character limits.",
        skills=(
            {
                "id": "social-formatter/format",
                "name": "Format for Social",
                "description": "Adapt the content for the specified social media platform.",
            },
        ),
        is_stub=True,
        port=9187,
    ),
    AgentDefinition(
        slug="translation-helper",
        name="Translation Helper",
        category="Content",
        description="Translates marketing and editorial content with domain-aware quality.",
        skills=(
            {
                "id": "translation-helper/translate",
                "name": "Translate Content",
                "description": "Return a domain-aware translation of the supplied content.",
            },
        ),
        is_stub=True,
        port=9188,
    ),
    # ── Research (10 agents: ports 9190-9198 stubs + port 9002 real) ────────
    AgentDefinition(
        slug="web-search-agent",
        name="Web Search Agent",
        category="Research",
        description="Searches the web, caches results, and sells them on the marketplace.",
        skills=(
            {
                "id": "web-search-agent/search",
                "name": "Web Search",
                "description": "Execute a web search and return structured results.",
            },
            {
                "id": "web-search-agent/search-and-list",
                "name": "Search and List",
                "description": "Search the web and list the results for sale on the marketplace.",
            },
        ),
        is_stub=False,
        port=9002,
    ),
    AgentDefinition(
        slug="paper-finder",
        name="Paper Finder",
        category="Research",
        description="Finds relevant academic papers from arXiv, Semantic Scholar, and PubMed.",
        skills=(
            {
                "id": "paper-finder/find",
                "name": "Find Papers",
                "description": "Return a ranked list of papers matching the research query.",
            },
        ),
        is_stub=True,
        port=9190,
    ),
    AgentDefinition(
        slug="citation-tracker",
        name="Citation Tracker",
        category="Research",
        description="Tracks citations and builds citation graphs for academic papers.",
        skills=(
            {
                "id": "citation-tracker/track",
                "name": "Track Citations",
                "description": "Return the citation network for the specified paper DOI.",
            },
        ),
        is_stub=True,
        port=9191,
    ),
    AgentDefinition(
        slug="benchmark-runner",
        name="Benchmark Runner",
        category="Research",
        description="Runs reproducible benchmarks for ML models and computes standard metrics.",
        skills=(
            {
                "id": "benchmark-runner/run",
                "name": "Run Benchmark",
                "description": "Execute the benchmark suite and return performance metrics.",
            },
        ),
        is_stub=True,
        port=9192,
    ),
    AgentDefinition(
        slug="knowledge-grapher",
        name="Knowledge Grapher",
        category="Research",
        description="Constructs knowledge graphs from documents and entity relationships.",
        skills=(
            {
                "id": "knowledge-grapher/graph",
                "name": "Build Knowledge Graph",
                "description": "Extract entities and relations and return a graph structure.",
            },
        ),
        is_stub=True,
        port=9193,
    ),
    AgentDefinition(
        slug="dataset-curator",
        name="Dataset Curator",
        category="Research",
        description="Curates, cleans, and documents datasets for ML training and evaluation.",
        skills=(
            {
                "id": "dataset-curator/curate",
                "name": "Curate Dataset",
                "description": "Clean, document, and return metadata for the supplied dataset.",
            },
        ),
        is_stub=True,
        port=9194,
    ),
    AgentDefinition(
        slug="experiment-logger",
        name="Experiment Logger",
        category="Research",
        description="Logs ML experiment parameters, metrics, and artefacts for reproducibility.",
        skills=(
            {
                "id": "experiment-logger/log",
                "name": "Log Experiment",
                "description": "Record experiment configuration and results in the experiment store.",
            },
        ),
        is_stub=True,
        port=9195,
    ),
    AgentDefinition(
        slug="hypothesis-tester",
        name="Hypothesis Tester",
        category="Research",
        description="Applies statistical hypothesis tests to experimental data.",
        skills=(
            {
                "id": "hypothesis-tester/test",
                "name": "Test Hypothesis",
                "description": "Run the specified statistical test and return results and interpretation.",
            },
        ),
        is_stub=True,
        port=9196,
    ),
    AgentDefinition(
        slug="literature-reviewer",
        name="Literature Reviewer",
        category="Research",
        description="Synthesises literature reviews from a corpus of academic papers.",
        skills=(
            {
                "id": "literature-reviewer/review",
                "name": "Review Literature",
                "description": "Generate a structured literature review for the given topic.",
            },
        ),
        is_stub=True,
        port=9197,
    ),
    AgentDefinition(
        slug="survey-builder",
        name="Survey Builder",
        category="Research",
        description="Designs and deploys surveys with branching logic and response analysis.",
        skills=(
            {
                "id": "survey-builder/build",
                "name": "Build Survey",
                "description": "Generate a survey with questions from the research objectives.",
            },
        ),
        is_stub=True,
        port=9198,
    ),
]

# ---------------------------------------------------------------------------
# Derived constants
# ---------------------------------------------------------------------------

CATEGORIES: list[str] = sorted({a.category for a in AGENT_DEFINITIONS})
STUB_AGENTS: list[AgentDefinition] = [a for a in AGENT_DEFINITIONS if a.is_stub]
REAL_AGENTS: list[AgentDefinition] = [a for a in AGENT_DEFINITIONS if not a.is_stub]


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def get_agent_by_slug(slug: str) -> AgentDefinition | None:
    """Return the agent definition matching ``slug``, or None if not found.

    Args:
        slug: Kebab-case agent identifier.

    Returns:
        Matching ``AgentDefinition``, or ``None``.
    """
    for agent in AGENT_DEFINITIONS:
        if agent.slug == slug:
            return agent
    return None


def get_agents_by_category(category: str) -> list[AgentDefinition]:
    """Return all agents belonging to the given category.

    Args:
        category: Case-sensitive category name (e.g. ``"AI/ML"``).

    Returns:
        List of ``AgentDefinition`` objects in the category.
    """
    return [a for a in AGENT_DEFINITIONS if a.category == category]
