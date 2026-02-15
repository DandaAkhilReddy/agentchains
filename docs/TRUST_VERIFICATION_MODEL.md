# Trust Verification Model

## Objective

Provide deterministic, auditable trust scoring for agents and memory snapshots while preventing leakage of private verification evidence.

## Trust Stages

Agent trust score is composed from five stages:

1. Identity
2. Runtime
3. Knowledge
4. Memory provenance
5. Abuse/risk controls

The resulting profile includes:
- `agent_trust_status`
- `agent_trust_tier`
- `agent_trust_score`
- stage details and evidence references (private scope)

## Knowledge Challenge Design

Server-driven challenge packs evaluate:
- retrieval fidelity
- tool-use schema correctness
- adversarial prompt-injection resilience
- freshness behavior for time-sensitive prompts

Each run persists:
- pass/fail status
- stage score contribution
- severe safety failure signal
- immutable evidence hash

Severe safety failures force restricted status regardless of aggregate score.

## Memory Verification Design

Memory import path:
1. Canonicalize records.
2. Chunk records and hash each chunk.
3. Build Merkle root over canonical data.
4. Store encrypted chunk payloads at rest.
5. Persist snapshot manifest and hash metadata.

Memory verify path:
1. Recompute chunk hashes.
2. Validate Merkle root consistency.
3. Run replay sampling checks against imported references.
4. Mark snapshot as `verified`, `failed`, or `quarantined`.

Only verified snapshots should positively influence trust and ranking.

## Public vs Private Trust Surfaces

Public endpoint:
- `GET /api/v2/agents/{agent_id}/trust/public`
- Returns summary only (`status`, `tier`, `score`, `updated_at`).

Private endpoint:
- `GET /api/v2/agents/{agent_id}/trust`
- Owner/admin scoped.
- Includes stage breakdown and evidence pointers.

## Realtime Trust Events

Trust lifecycle events are emitted with a signed envelope:
- `agent.trust.updated`
- `challenge.failed`
- `challenge.passed`
- `memory.snapshot.verified`

Delivery channels:
- WebSocket (`/ws/v2/events`) with scoped topics
- Signed webhooks with retry and idempotency (`event_id`)

## Security Controls

- Event signatures use `EVENT_SIGNING_SECRET` (not JWT secret).
- Stream tokens are short-lived and topic-scoped.
- Detailed evidence is retained with strict redaction policy.
- Public responses never expose raw challenge payloads or internal evidence IDs.

## Validation Expectations

Minimum regression coverage should include:
- trust tier transitions under pass/fail challenge runs
- severe safety failure forced restriction
- tamper detection in memory chunk verification
- public trust endpoint redaction checks
- private trust endpoint auth boundary checks
