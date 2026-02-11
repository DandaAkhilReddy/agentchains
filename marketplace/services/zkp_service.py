"""Zero-Knowledge Proof generation and verification.

Four proof types per listing:
1. Merkle Root  — SHA-256 Merkle tree of 1KB chunks
2. Schema Proof — JSON schema fingerprint (field names, types, counts)
3. Bloom Filter — 256-byte bloom filter of content keywords (3 hash functions)
4. Metadata     — Hash commitment of (size, category, freshness, quality)

All proofs use Python stdlib only (hashlib, json, math).
"""

import hashlib
import json
import math
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.zkproof import ZKProof


CHUNK_SIZE = 1024  # 1KB chunks for Merkle tree
BLOOM_SIZE = 256   # 256 bytes = 2048 bits
BLOOM_HASHES = 3   # 3 independent hash functions


# ── Merkle Tree ──────────────────────────────────────────────

def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_merkle_tree(content: bytes) -> dict:
    """Build a SHA-256 Merkle tree from 1KB content chunks.

    Returns {root, leaf_count, depth, leaves (hashes only)}.
    """
    chunks = [content[i:i + CHUNK_SIZE] for i in range(0, len(content), CHUNK_SIZE)]
    if not chunks:
        chunks = [b""]

    leaves = [_sha256(chunk) for chunk in chunks]
    depth = 0

    current_level = leaves[:]
    while len(current_level) > 1:
        next_level = []
        for i in range(0, len(current_level), 2):
            left = current_level[i]
            right = current_level[i + 1] if i + 1 < len(current_level) else left
            combined = _sha256((left + right).encode())
            next_level.append(combined)
        current_level = next_level
        depth += 1

    return {
        "root": current_level[0],
        "leaf_count": len(leaves),
        "depth": depth,
        "leaves": leaves,
    }


# ── Schema Proof ─────────────────────────────────────────────

def extract_schema(content: bytes) -> dict:
    """Extract JSON schema fingerprint: field names, types, counts.

    If content isn't JSON, returns a text-mode schema with word/line counts.
    """
    try:
        data = json.loads(content.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        # Text-mode fallback
        text = content.decode("utf-8", errors="replace")
        return {
            "mode": "text",
            "line_count": text.count("\n") + 1,
            "word_count": len(text.split()),
            "char_count": len(text),
        }

    return _schema_from_value(data)


def _schema_from_value(value) -> dict:
    if isinstance(value, dict):
        fields = {}
        for k, v in value.items():
            fields[k] = _schema_from_value(v)
        return {"type": "object", "field_count": len(fields), "fields": fields}
    elif isinstance(value, list):
        item_schema = _schema_from_value(value[0]) if value else {"type": "unknown"}
        return {"type": "array", "item_count": len(value), "item_schema": item_schema}
    elif isinstance(value, str):
        return {"type": "string"}
    elif isinstance(value, bool):
        return {"type": "boolean"}
    elif isinstance(value, (int, float)):
        return {"type": "number"}
    elif value is None:
        return {"type": "null"}
    return {"type": "unknown"}


# ── Bloom Filter ─────────────────────────────────────────────

def _bloom_hash(word: str, seed: int) -> int:
    """Hash a word with a seed to get a bit position in the bloom filter."""
    h = hashlib.sha256(f"{seed}:{word}".encode()).digest()
    return int.from_bytes(h[:4], "big") % (BLOOM_SIZE * 8)


def build_bloom_filter(content: bytes) -> bytes:
    """Build a 256-byte bloom filter from content words."""
    text = content.decode("utf-8", errors="replace").lower()
    # Extract words (alphanumeric sequences)
    words = set()
    current = []
    for ch in text:
        if ch.isalnum():
            current.append(ch)
        else:
            if current:
                words.add("".join(current))
                current = []
    if current:
        words.add("".join(current))

    bloom = bytearray(BLOOM_SIZE)
    for word in words:
        for seed in range(BLOOM_HASHES):
            bit_pos = _bloom_hash(word, seed)
            byte_idx = bit_pos // 8
            bit_idx = bit_pos % 8
            bloom[byte_idx] |= (1 << bit_idx)

    return bytes(bloom)


def check_bloom(bloom_bytes: bytes, word: str) -> bool:
    """Check if a word is probably in the bloom filter."""
    word = word.lower()
    for seed in range(BLOOM_HASHES):
        bit_pos = _bloom_hash(word, seed)
        byte_idx = bit_pos // 8
        bit_idx = bit_pos % 8
        if not (bloom_bytes[byte_idx] & (1 << bit_idx)):
            return False
    return True  # Probably present (may be false positive)


# ── Metadata Commitment ──────────────────────────────────────

def build_metadata_commitment(
    content_size: int,
    category: str,
    freshness_at: datetime,
    quality_score: float,
) -> dict:
    """Create a hash commitment of metadata claims."""
    payload = json.dumps({
        "content_size": content_size,
        "category": category,
        "freshness_at": freshness_at.isoformat(),
        "quality_score": float(quality_score),
    }, sort_keys=True)
    commitment = _sha256(payload.encode())
    return {
        "commitment": commitment,
        "public_inputs": {
            "content_size": content_size,
            "category": category,
            "freshness_at": freshness_at.isoformat(),
            "quality_score": float(quality_score),
        },
    }


# ── Proof Generation (called on listing creation) ────────────

async def generate_proofs(
    db: AsyncSession,
    listing_id: str,
    content: bytes,
    category: str,
    content_size: int,
    freshness_at: datetime,
    quality_score: float,
) -> list[ZKProof]:
    """Generate all 4 proof types for a listing and store in DB."""
    proofs = []

    # 1. Merkle Root
    merkle = build_merkle_tree(content)
    proofs.append(ZKProof(
        listing_id=listing_id,
        proof_type="merkle_root",
        commitment=merkle["root"],
        proof_data=json.dumps({"leaf_count": merkle["leaf_count"], "depth": merkle["depth"]}),
        public_inputs=json.dumps({"root": merkle["root"], "leaf_count": merkle["leaf_count"], "depth": merkle["depth"]}),
    ))

    # 2. Schema Proof
    schema = extract_schema(content)
    schema_hash = _sha256(json.dumps(schema, sort_keys=True).encode())
    proofs.append(ZKProof(
        listing_id=listing_id,
        proof_type="schema",
        commitment=schema_hash,
        proof_data=json.dumps(schema),
        public_inputs=json.dumps(_public_schema(schema)),
    ))

    # 3. Bloom Filter
    bloom = build_bloom_filter(content)
    bloom_hex = bloom.hex()
    bloom_hash = _sha256(bloom)
    proofs.append(ZKProof(
        listing_id=listing_id,
        proof_type="bloom_filter",
        commitment=bloom_hash,
        proof_data=json.dumps({"bloom_hex": bloom_hex, "size_bytes": BLOOM_SIZE, "hash_count": BLOOM_HASHES}),
        public_inputs=json.dumps({"bloom_hex": bloom_hex, "size_bytes": BLOOM_SIZE, "hash_count": BLOOM_HASHES}),
    ))

    # 4. Metadata Commitment
    meta = build_metadata_commitment(content_size, category, freshness_at, quality_score)
    proofs.append(ZKProof(
        listing_id=listing_id,
        proof_type="metadata",
        commitment=meta["commitment"],
        proof_data=json.dumps(meta),
        public_inputs=json.dumps(meta["public_inputs"]),
    ))

    for p in proofs:
        db.add(p)
    await db.flush()

    return proofs


def _public_schema(schema: dict) -> dict:
    """Extract public-safe schema info (field names and types, not values)."""
    if schema.get("mode") == "text":
        return {"mode": "text", "line_count": schema["line_count"], "word_count": schema["word_count"]}

    if schema.get("type") == "object":
        return {
            "type": "object",
            "field_count": schema["field_count"],
            "field_names": list(schema.get("fields", {}).keys()),
            "field_types": {k: v.get("type", "unknown") for k, v in schema.get("fields", {}).items()},
        }
    elif schema.get("type") == "array":
        return {
            "type": "array",
            "item_count": schema["item_count"],
            "item_schema": _public_schema(schema.get("item_schema", {})),
        }
    return schema


# ── Verification (pre-purchase) ──────────────────────────────

async def get_proofs(db: AsyncSession, listing_id: str) -> list[ZKProof]:
    """Get all proofs for a listing."""
    result = await db.execute(
        select(ZKProof).where(ZKProof.listing_id == listing_id)
    )
    return list(result.scalars().all())


async def verify_listing(
    db: AsyncSession,
    listing_id: str,
    keywords: list[str] | None = None,
    schema_has_fields: list[str] | None = None,
    min_size: int | None = None,
    min_quality: float | None = None,
) -> dict:
    """Pre-purchase verification: check claims without revealing content.

    Returns pass/fail for each requested check.
    """
    proofs = await get_proofs(db, listing_id)
    if not proofs:
        return {"listing_id": listing_id, "error": "No proofs found", "verified": False}

    proof_map = {p.proof_type: p for p in proofs}
    checks = {}

    # Keyword check via bloom filter
    if keywords and "bloom_filter" in proof_map:
        bloom_proof = proof_map["bloom_filter"]
        bloom_data = json.loads(bloom_proof.proof_data)
        bloom_bytes = bytes.fromhex(bloom_data["bloom_hex"])
        keyword_results = {}
        for kw in keywords:
            keyword_results[kw] = check_bloom(bloom_bytes, kw)
        checks["keywords"] = {
            "passed": all(keyword_results.values()),
            "details": keyword_results,
        }

    # Schema field check
    if schema_has_fields and "schema" in proof_map:
        schema_proof = proof_map["schema"]
        public = json.loads(schema_proof.public_inputs)
        field_names = public.get("field_names", [])
        field_results = {}
        for field in schema_has_fields:
            field_results[field] = field in field_names
        checks["schema_fields"] = {
            "passed": all(field_results.values()),
            "details": field_results,
        }

    # Size check via metadata commitment
    if min_size is not None and "metadata" in proof_map:
        meta_proof = proof_map["metadata"]
        public = json.loads(meta_proof.public_inputs)
        actual_size = public.get("content_size", 0)
        checks["min_size"] = {
            "passed": actual_size >= min_size,
            "actual": actual_size,
            "required": min_size,
        }

    # Quality check via metadata commitment
    if min_quality is not None and "metadata" in proof_map:
        meta_proof = proof_map["metadata"]
        public = json.loads(meta_proof.public_inputs)
        actual_quality = public.get("quality_score", 0)
        checks["min_quality"] = {
            "passed": actual_quality >= min_quality,
            "actual": actual_quality,
            "required": min_quality,
        }

    all_passed = all(c["passed"] for c in checks.values()) if checks else False

    return {
        "listing_id": listing_id,
        "verified": all_passed,
        "checks": checks,
        "proof_types_available": list(proof_map.keys()),
    }


async def bloom_check_word(db: AsyncSession, listing_id: str, word: str) -> dict:
    """Quick single-word bloom filter check."""
    result = await db.execute(
        select(ZKProof).where(ZKProof.listing_id == listing_id, ZKProof.proof_type == "bloom_filter")
    )
    proof = result.scalar_one_or_none()
    if not proof:
        return {"listing_id": listing_id, "word": word, "error": "No bloom filter proof found"}

    bloom_data = json.loads(proof.proof_data)
    bloom_bytes = bytes.fromhex(bloom_data["bloom_hex"])
    probably_present = check_bloom(bloom_bytes, word)

    return {
        "listing_id": listing_id,
        "word": word,
        "probably_present": probably_present,
        "note": "Bloom filters may have false positives but never false negatives",
    }
