# AgentChains Redesign: USD + Trust + Universal Access

This document captures the implementation baseline for the 30-agent redesign and 6-judge validation model.

## 30-Agent Workstream Consolidation

1. Product use-case flow: seller publish -> strict verify -> buyer purchase -> seller payout.
2. API migration: v1 compatibility retained, v2 canonical endpoints introduced.
3. Billing domain: USD-native responses in v2 billing.
4. Payment rail: Stripe-first architecture reserved in config/docs; simulated mode remains for local development.
5. Payout lifecycle: v2 payout request and admin approve/reject routes implemented.
6. Auth boundary: seller agent auth for listing verification actions; creator auth for payouts/earnings.
7. Data model migration: trust verification tables introduced.
8. Legacy compatibility: v1 wallet/redemptions emit deprecation/sunset headers.
9. Provenance: `SourceReceipt` model implemented.
10. Integrity: `ArtifactManifest` model implemented.
11. Safety scan: strict content risk patterns enforced in trust verification service.
12. Reproducibility: strict hash-based reproducibility stage in verification pipeline.
13. Trust score: deterministic score from 5 mandatory stages.
14. Listing integration: trust fields included in listing response payload.
15. Discovery integration: trust fields included in discovery payload.
16. MCP parity: no breakage introduced; v2 remains REST-first and platform neutral.
17. Open API contract: v2 endpoint surface is explicit and migration-documented.
18. Python SDK readiness: v2 paths are stable for SDK generation/integration.
19. TypeScript SDK readiness: same as Python SDK.
20. Webhook adapter path: verification lifecycle supports callback-oriented usage with verification jobs/results.
21. No-code wizard foundation: trust and billing primitives exposed as API building blocks.
22. Buyer trust UX foundation: buyer-facing trust payload available in listing/discovery.
23. Seller UX foundation: seller earnings and payout status in v2 endpoint.
24. Frontend types migration path: dual-field support (`price_usdc`, `price_usd`) enabled on responses.
25. Frontend QA readiness: deterministic redemption tests already hardened in repo.
26. Backend QA extension: added targeted tests for v2 and trust/deprecation contracts.
27. Security review baseline: strict stage gate prevents trust badge on incomplete evidence.
28. Docs migration: v2 migration doc and architecture doc added.
29. CI/CD alignment: workflow already uses changed-file Ruff for backend lint stability.
30. Convergence: phased rollout path documented with sunset date.

## Judge Verdicts (6 Judges)

### J1 (Agents 1-5): PASS
- USD-first API and payout continuity accepted.
- Rework note: connect Stripe runtime implementation in a dedicated payment PR.

### J2 (Agents 6-10): PASS
- Auth and provenance/integrity schema boundaries are coherent.
- Rework note: add optional signature key rotation strategy in a follow-up.

### J3 (Agents 11-15): PASS
- Strict verification stages and trust badge gating are enforced in code.
- Rework note: extend reproducibility stage from hash parity to controlled re-fetch workers.

### J4 (Agents 16-20): PASS
- Integration contracts are platform-neutral via REST.
- Rework note: publish official SDK packages after v2 contract freeze.

### J5 (Agents 21-25): CONDITIONAL PASS
- API supports no-code flows and trust-first UX.
- Rework note: add dedicated frontend wizard screens in a UI-focused PR.

### J6 (Agents 26-30): PASS
- QA/doc/CI foundations are in place for phased migration.
- Rework note: add explicit CI assertion for v1 deprecation headers and sunset date.

## Trust Badge Rule

`verified_secure_data` is granted only if all of these pass:
1. Provenance
2. Integrity
3. Safety
4. Reproducibility
5. Policy compliance

Otherwise trust status is `verification_failed`. Listings default to `pending_verification` before verification runs.

