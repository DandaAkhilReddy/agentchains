
# Project WebMCP: A Strategic Research Plan

This document provides a comprehensive blueprint for integrating the proposed "WebMCP" (Model Context Protocol for the Web) standard into the AgentChains platform. It is the result of a 20-point research plan covering architecture, security, user experience, and implementation strategy.

---

## Part 1: Core Architecture & Models (A01-A03)

This section outlines the foundational changes to the application's models, services, and API contracts.

### A01: Core Model Redefinition

- **`Tool` Model (`marketplace/models/tool.py`):** A new table to store definitions of discoverable WebMCP tools, including their domain, name, and a JSON schema for their parameters.
- **`ActionListing` Model (`marketplace/models/listing.py`):** A new marketplace listing type, parallel to `DataListing`. It represents an agent's capability to execute a `Tool` and has a `price_per_execution`.
- **`ActionExecution` Model (`marketplace/models/execution.py`):** A new table to log every instance of a purchased action. It stores the inputs, status (`pending`, `success`, `failed`), and the final `Proof of Execution`.

### A02: Marketplace Logic (Service Layer)

- **`tool_service.py`:** A new service to manage the registration and discovery of `Tools`.
- **`listing_service.py` (Modified):** Updated to handle the creation and searching of both `DataListing` and `ActionListing` types.
- **`execution_service.py`:** The core new engine. It handles the entire lifecycle of an action: creating a financial hold, invoking the agent, calling the verification service, and either capturing or releasing the funds based on the outcome.

### A03: API Contract Evolution (API v3)

- **`/api/v3/tools/`:** Endpoints to register and list `Tools`.
- **`/api/v3/listings/actions/`:** Endpoints for creators to publish and manage their `ActionListings`.
- **`/api/v3/execute/{listing_id}`:** The endpoint for a buyer to initiate an action.
- **`/api/v3/execute/status/{execution_id}`:** The endpoint for a buyer to poll for the status and retrieve the final `Proof of Execution`.

---

## Part 2: Frontend UI/UX (A04)

This section details the necessary changes to the React frontend to support the "Actions" marketplace.

- **Marketplace Discovery (`ListingsPage.tsx`):**
  - A new "Actions" tab to filter for this new listing type.
  - A distinct UI card for `ActionListings` with a "Configure & Run" call-to-action and the icon of the `Tool`'s domain.
- **New Page: `ActionDetailPage.tsx`:**
  - Displays details of the action and, crucially, a dynamically generated form based on the `Tool`'s JSON schema for user input.
- **New Component: `ExecutionStatusView.tsx`:**
  - A real-time view (perhaps a slide-out panel) that polls the status endpoint to show if the action is `pending`, `in_progress`, `successful`, or `failed`.
- **New Page: `ExecutionsPage.tsx`:**
  - A history page for the user, showing all their past executions. It acts as a "digital receipt book," allowing users to view the `Proof of Execution` for each successful action.

---

## Part 3: Agent SDK & Templates (A05)

This section defines the developer experience for creators building `ActionAgents`.

- **Core Technology:** Agents will use **Playwright** to control a headless browser instance from Python.
- **New SDK Class: `ActionExecutor` (`agents/common/action_executor.py`):**
  - This class abstracts away all browser automation.
  - Its primary method, `call_tool(url, tool_name, parameters)`, handles navigating to the page, executing the WebMCP JavaScript, and returning the `Proof of Execution`. It also manages all error handling.
- **`ActionAgent` Template:** A new boilerplate project in `agents/action_agent_template/` will be provided. It will demonstrate how a developer can import the `ActionExecutor` and create a functioning `ActionAgent` with just a few lines of code.

---

## Part 4: Trust & Reliability (A06-A08)

This section outlines the cornerstone of the feature: the system for verifying actions and handling failures.

### A07: Proof-of-Execution Standard

- **The Standard:** The `Proof of Execution` **MUST** be a **JSON Web Token (JWT)** signed asymmetrically (e.g., RS256) by the website hosting the WebMCP tool.
- **JWT Payload:** The JWT will contain standard claims (`iss`, `aud`, `iat`, `jti`) as well as custom claims like `params_hash` (a hash of the inputs) and a `result` object.

### A06: Trust Pipeline for Actions

- **`ActionVerificationService`:** A new service that verifies the `Proof of Execution` JWT.
- **Verification Steps:**
  1.  Verify the JWT's signature against the website's public key.
  2.  Validate the `aud`, `iat`, and `jti` claims to prevent misuse and replay attacks.
  3.  Compare the `params_hash` in the JWT against a hash of the parameters the user provided to ensure integrity.
  4.  Check that the `result.status` claim is `success`.

### A08: Failure & Rollback Logic

- **Financial Principle:** A buyer's funds are only **held** (authorized) at the start. They are only **captured** after a `Proof of Execution` has been successfully verified.
- **Rollback Scenarios:** The financial hold is **released immediately** if:
  - The agent crashes or times out.
  - The website returns a valid proof, but with a `failure` status.
  - The proof is invalid (e.g., bad signature), which also heavily penalizes the agent's trust score.

---

## Part 5: Security & Authorization (A09-A10)

This section details how to protect the user, the platform, and third-party websites.

### A09: Client-Side Security

- **Sandbox Environment:** The `ActionExecutor` SDK acts as a sandbox. It will enforce a **Domain Lock** (only allowing navigation to the tool's domain) and a **Tool Lock** (only allowing the specific tool to be called).
- **Execution Isolation:** Each agent execution will run in an ephemeral, single-use **Docker container** with a strict network policy.

### A10: Action Authorization Model

- **Explicit Consent:** Before every execution, the user is shown a **Consent Panel** that clearly states which agent is performing which action, on which website, with which parameters, and for what cost.
- **`AuthZ_Token`:** The user's final click on "Confirm & Execute" generates a short-lived JWT (`AuthZ_Token`). This token is sent to the backend and verified, ensuring that every API request to execute an action was directly authorized by a recent user interaction.

---

## Part 6: Ecosystem & Usability (A11-A14)

This section covers the user journeys and economic model for the marketplace.

- **Creator Experience:** A streamlined journey including `Tool` registration, a sandbox for testing, and a simple publishing process.
- **Buyer Experience:** An intuitive process for discovering, configuring, and monitoring actions, with a verifiable history of all executions.
- **Admin Dashboard:** New tools for admins to approve `Tools`, monitor live executions, and manage disputes.
- **Economic Model:** A "price per successful execution" model. Revenue is split between the `Creator` and the `Platform Fee`. A "no success, no fee" policy ensures buyers only pay for successful, verified outcomes.

---

## Part 7: Implementation & Rollout (A15-A20)

This section outlines the concrete steps for building and launching the feature.

- **Terminology (A20):** Establishes a clear glossary for `Tool`, `Action Listing`, `Execution`, and `Proof`.
- **Documentation (A15):** A plan to create new tutorials, guides, and API references.
- **Dependencies (A18):** `playwright` and `python-jose` for the backend; `react-jsonschema-form` for the frontend.
- **Database (A16):** Use **Alembic** to manage the creation of the new `tools`, `action_listings`, and `action_executions` tables.
- **Testing (A19):** Create a **Mock WebMCP Server** to enable reliable, dependency-free end-to-end testing of the entire action lifecycle.
- **Rollout (A17):** A four-phased rollout strategy: 1) Internal Alpha, 2) Closed Beta with trusted creators, 3) Public Beta, 4) General Availability.

