"""USD Billing Engine — Off-chain double-entry ledger for instant payments.

Every money movement (deposit, purchase, sale, fee, bonus, refund,
withdrawal) is recorded as an immutable row in ``token_ledger`` with
matching balance updates on the source and destination ``token_accounts``.

Key design decisions:
- **Double-entry**: every debit has a matching credit.
- **Row-level locking** (SELECT ... FOR UPDATE) on PostgreSQL to serialise
  concurrent transfers on the same accounts.  Falls back to simple
  select-then-update on SQLite (WAL mode + busy_timeout provide sufficient
  safety for single-writer dev scenarios).
- **Decimal everywhere**: amounts are ``Decimal`` to avoid floating-point
  drift on financial calculations.
- **Idempotency**: optional ``idempotency_key`` on ledger entries prevents
  double-processing of the same transfer.
- **Deterministic lock ordering**: accounts are locked by sorted ID to
  prevent deadlocks when two agents transfer to each other concurrently.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.config import settings
from marketplace.core.async_tasks import fire_and_forget
from marketplace.core.hashing import compute_ledger_hash
from marketplace.models.token_account import (
    TokenAccount,
    TokenLedger,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_is_sqlite: bool = settings.database_url.startswith("sqlite")

# Canonical platform account marker — agent_id is NULL for the treasury.
_PLATFORM_AGENT_ID: None = None


def _to_decimal(value: float | int | str | Decimal) -> Decimal:
    """Coerce a value to Decimal with 6 decimal places."""
    if isinstance(value, Decimal):
        return value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    return Decimal(str(value)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Account helpers (private)
# ---------------------------------------------------------------------------

async def _lock_account(db: AsyncSession, account_id: str) -> TokenAccount:
    """Load a TokenAccount with a row-level lock (PostgreSQL) or plain SELECT (SQLite)."""
    stmt = select(TokenAccount).where(TokenAccount.id == account_id)
    if not _is_sqlite:
        stmt = stmt.with_for_update()
    result = await db.execute(stmt)
    account = result.scalar_one_or_none()
    if account is None:
        raise ValueError(f"Token account {account_id} not found")
    return account


async def _get_account_by_agent(
    db: AsyncSession, agent_id: str | None, *, lock: bool = False
) -> TokenAccount | None:
    """Fetch account by agent_id.  Pass agent_id=None for the platform account."""
    if agent_id is None:
        stmt = select(TokenAccount).where(
            TokenAccount.agent_id.is_(None),
            TokenAccount.creator_id.is_(None),
        )
    else:
        stmt = select(TokenAccount).where(TokenAccount.agent_id == agent_id)
    if lock and not _is_sqlite:
        stmt = stmt.with_for_update()
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _get_account_by_creator(
    db: AsyncSession, creator_id: str, *, lock: bool = False
) -> TokenAccount | None:
    """Fetch token account by creator_id."""
    stmt = select(TokenAccount).where(TokenAccount.creator_id == creator_id)
    if lock and not _is_sqlite:
        stmt = stmt.with_for_update()
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Creator royalty helpers (private)
# ---------------------------------------------------------------------------

async def _get_creator_for_agent(db: AsyncSession, agent_id: str) -> str | None:
    """Look up the creator_id that owns the given agent.  Returns None if unclaimed."""
    from marketplace.models.agent import RegisteredAgent
    result = await db.execute(
        select(RegisteredAgent.creator_id).where(RegisteredAgent.id == agent_id)
    )
    return result.scalar_one_or_none()


async def _process_creator_royalty(
    db: AsyncSession,
    agent_id: str,
    net_amount: Decimal,
    reference_id: str | None,
) -> TokenLedger | None:
    """Auto-transfer agent earnings to the owning creator's account.

    This is a fee-free internal transfer (tx_type='creator_royalty').
    Called after every agent credit to auto-flow earnings upstream.
    Returns the royalty ledger entry, or None if the agent has no creator.
    """
    if settings.creator_royalty_pct <= 0:
        return None

    creator_id = await _get_creator_for_agent(db, agent_id)
    if creator_id is None:
        return None

    creator_acct = await _get_account_by_creator(db, creator_id, lock=True)
    agent_acct = await _get_account_by_agent(db, agent_id, lock=True)
    if creator_acct is None or agent_acct is None:
        return None

    royalty = _to_decimal(net_amount * _to_decimal(settings.creator_royalty_pct))
    if royalty <= 0:
        return None

    # Debit agent, credit creator (no platform fee)
    agent_balance = Decimal(str(agent_acct.balance))
    if agent_balance < royalty:
        royalty = agent_balance  # Don't overdraw — transfer what's available
    if royalty <= 0:
        return None

    agent_acct.balance = Decimal(str(agent_acct.balance)) - royalty
    agent_acct.updated_at = _utcnow()

    creator_acct.balance = Decimal(str(creator_acct.balance)) + royalty
    creator_acct.total_earned = Decimal(str(creator_acct.total_earned)) + royalty
    creator_acct.updated_at = _utcnow()

    # Hash chain
    latest = await db.execute(
        select(TokenLedger.entry_hash).order_by(TokenLedger.created_at.desc()).limit(1)
    )
    prev_hash = latest.scalar_one_or_none()
    created_at = _utcnow()
    entry_hash = compute_ledger_hash(
        prev_hash, agent_acct.id, creator_acct.id,
        royalty, Decimal("0"), "creator_royalty", created_at.isoformat(),
    )

    ledger = TokenLedger(
        id=_new_id(),
        from_account_id=agent_acct.id,
        to_account_id=creator_acct.id,
        amount=royalty,
        fee_amount=Decimal("0"),
        tx_type="creator_royalty",
        reference_id=reference_id,
        reference_type="creator_royalty",
        idempotency_key=f"royalty-{reference_id}" if reference_id else None,
        memo=f"Creator royalty ({settings.creator_royalty_pct:.0%}) from agent {agent_id}",
        created_at=created_at,
        prev_hash=prev_hash,
        entry_hash=entry_hash,
    )
    db.add(ledger)
    await db.flush()

    logger.info(
        "Creator royalty: $%s USD from agent %s -> creator %s (ref=%s)",
        royalty, agent_id, creator_id, reference_id,
    )
    return ledger


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def ensure_platform_account(db: AsyncSession) -> TokenAccount:
    """Get or create the platform treasury account (agent_id=NULL)."""
    account = await _get_account_by_agent(db, _PLATFORM_AGENT_ID)
    if account is None:
        account = TokenAccount(
            id=_new_id(),
            agent_id=None,
            balance=Decimal("0"),
        )
        db.add(account)
        logger.info("Created platform treasury account %s", account.id)

    await db.commit()
    await db.refresh(account)
    return account


async def create_account(db: AsyncSession, agent_id: str) -> TokenAccount:
    """Create a token account for an agent.  Returns existing if one already exists."""
    existing = await _get_account_by_agent(db, agent_id)
    if existing is not None:
        return existing

    account = TokenAccount(
        id=_new_id(),
        agent_id=agent_id,
        balance=Decimal("0"),
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    logger.info("Created token account %s for agent %s", account.id, agent_id)
    return account


async def get_balance(db: AsyncSession, agent_id: str) -> dict:
    """Return the balance summary for an agent.

    Returns:
        dict with keys: balance, total_earned, total_spent,
        total_deposited, total_fees_paid.
    """
    account = await _get_account_by_agent(db, agent_id)
    if account is None:
        raise ValueError(f"No token account for agent {agent_id}")

    balance = Decimal(str(account.balance))
    return {
        "balance": float(balance),
        "total_earned": float(account.total_earned),
        "total_spent": float(account.total_spent),
        "total_deposited": float(account.total_deposited),
        "total_fees_paid": float(account.total_fees_paid),
    }


async def transfer(
    db: AsyncSession,
    from_agent_id: str,
    to_agent_id: str,
    amount: float | Decimal,
    tx_type: str,
    reference_id: str | None = None,
    reference_type: str | None = None,
    idempotency_key: str | None = None,
    memo: str = "",
) -> TokenLedger:
    """Execute an ATOMIC transfer with platform fee.

    Steps:
        1. Lock both accounts (sorted by ID to prevent deadlocks).
        2. Verify sender has sufficient balance.
        3. Calculate fee.
        4. Debit sender, credit receiver (net of fee), credit platform (fee).
        5. Write an immutable ``TokenLedger`` entry.

    Raises:
        ValueError: if either account is missing or balance is insufficient.
    """
    amount_d = _to_decimal(amount)
    if amount_d <= 0:
        raise ValueError("Transfer amount must be positive")

    # --- Idempotency check ---------------------------------------------------
    if idempotency_key:
        existing = await db.execute(
            select(TokenLedger).where(
                TokenLedger.idempotency_key == idempotency_key
            )
        )
        found = existing.scalar_one_or_none()
        if found is not None:
            logger.info(
                "Idempotent replay for key=%s, returning existing ledger %s",
                idempotency_key,
                found.id,
            )
            return found

    # --- Resolve account IDs --------------------------------------------------
    from_account = await _get_account_by_agent(db, from_agent_id)
    to_account = await _get_account_by_agent(db, to_agent_id)
    if from_account is None:
        raise ValueError(f"No token account for sender agent {from_agent_id}")
    if to_account is None:
        raise ValueError(f"No token account for receiver agent {to_agent_id}")

    platform_account = await _get_account_by_agent(db, _PLATFORM_AGENT_ID)
    if platform_account is None:
        raise ValueError(
            "Platform treasury account not initialised "
            "— call ensure_platform_account() first"
        )

    # --- Lock accounts in deterministic order (by account.id) -----------------
    lock_ids = sorted({from_account.id, to_account.id, platform_account.id})
    locked: dict[str, TokenAccount] = {}
    for acct_id in lock_ids:
        locked[acct_id] = await _lock_account(db, acct_id)

    sender = locked[from_account.id]
    receiver = locked[to_account.id]
    platform = locked[platform_account.id]

    # --- Balance check --------------------------------------------------------
    sender_balance = Decimal(str(sender.balance))
    if sender_balance < amount_d:
        raise ValueError(
            f"Insufficient balance: agent {from_agent_id} has "
            f"${sender_balance:.2f}, needs ${amount_d:.2f}"
        )

    # --- Fee calculation ------------------------------------------------------
    fee_d = _to_decimal(amount_d * _to_decimal(settings.platform_fee_pct))
    platform_credit = fee_d
    receiver_credit = _to_decimal(amount_d - fee_d)

    # --- Apply balance changes ------------------------------------------------
    sender.balance = Decimal(str(sender.balance)) - amount_d
    sender.total_spent = Decimal(str(sender.total_spent)) + amount_d
    sender.updated_at = _utcnow()

    receiver.balance = Decimal(str(receiver.balance)) + receiver_credit
    receiver.total_earned = Decimal(str(receiver.total_earned)) + receiver_credit
    receiver.total_fees_paid = Decimal(str(receiver.total_fees_paid)) + fee_d
    receiver.updated_at = _utcnow()

    platform.balance = Decimal(str(platform.balance)) + platform_credit
    platform.updated_at = _utcnow()

    # --- Create ledger entry with hash chain ------------------------------------
    latest = await db.execute(
        select(TokenLedger.entry_hash).order_by(TokenLedger.created_at.desc()).limit(1)
    )
    prev_hash = latest.scalar_one_or_none()

    created_at = _utcnow()
    entry_hash = compute_ledger_hash(
        prev_hash, sender.id, receiver.id,
        amount_d, fee_d, tx_type, created_at.isoformat(),
    )

    ledger = TokenLedger(
        id=_new_id(),
        from_account_id=sender.id,
        to_account_id=receiver.id,
        amount=amount_d,
        fee_amount=fee_d,
        tx_type=tx_type,
        reference_id=reference_id,
        reference_type=reference_type,
        idempotency_key=idempotency_key,
        memo=memo,
        created_at=created_at,
        prev_hash=prev_hash,
        entry_hash=entry_hash,
    )
    db.add(ledger)

    # Process creator royalty before commit (within same transaction)
    royalty_ledger = None
    if to_agent_id is not None and tx_type in ("purchase", "sale"):
        try:
            royalty_ledger = await _process_creator_royalty(
                db, to_agent_id, receiver_credit, ledger.id,
            )
        except Exception as exc:
            logger.warning("Creator royalty failed (non-fatal): %s", exc)

    await db.commit()
    await db.refresh(ledger)

    # Broadcast payment event
    try:
        from marketplace.main import broadcast_event
        fire_and_forget(broadcast_event("payment", {
            "from_agent_id": from_agent_id,
            "to_agent_id": to_agent_id,
            "amount": float(amount_d),
            "fee": float(fee_d),
            "tx_type": tx_type,
            "creator_royalty": float(royalty_ledger.amount) if royalty_ledger else 0,
        }), task_name="broadcast_payment")
    except Exception:
        pass

    logger.info(
        "Transfer %s: $%s USD from %s -> %s (fee=$%s) [%s]",
        ledger.id,
        amount_d,
        from_agent_id,
        to_agent_id,
        fee_d,
        tx_type,
    )
    return ledger


async def deposit(
    db: AsyncSession,
    agent_id: str,
    amount_usd: float | Decimal,
    deposit_id: str | None = None,
    memo: str = "Deposit",
) -> TokenLedger:
    """Credit USD to an agent from the platform.  No fee is charged.

    Used for deposits, signup bonuses, refunds, and admin credits.
    """
    amount_d = _to_decimal(amount_usd)
    if amount_d <= 0:
        raise ValueError("Deposit amount must be positive")

    account = await _get_account_by_agent(db, agent_id)
    if account is None:
        raise ValueError(f"No token account for agent {agent_id}")

    platform = await _get_account_by_agent(db, _PLATFORM_AGENT_ID)
    if platform is None:
        raise ValueError(
            "Platform treasury account not initialised "
            "— call ensure_platform_account() first"
        )

    # Lock accounts in deterministic order
    lock_ids = sorted({account.id, platform.id})
    locked: dict[str, TokenAccount] = {}
    for acct_id in lock_ids:
        locked[acct_id] = await _lock_account(db, acct_id)

    target = locked[account.id]

    # Credit agent
    target.balance = Decimal(str(target.balance)) + amount_d
    target.total_deposited = Decimal(str(target.total_deposited)) + amount_d
    target.updated_at = _utcnow()

    # Ledger entry — from_account_id is NULL (external deposit), with hash chain
    idempotency = f"deposit-{deposit_id}" if deposit_id else None

    latest = await db.execute(
        select(TokenLedger.entry_hash).order_by(TokenLedger.created_at.desc()).limit(1)
    )
    prev_hash = latest.scalar_one_or_none()

    created_at = _utcnow()
    entry_hash = compute_ledger_hash(
        prev_hash, None, target.id,
        amount_d, Decimal("0"), "deposit", created_at.isoformat(),
    )

    ledger = TokenLedger(
        id=_new_id(),
        from_account_id=None,
        to_account_id=target.id,
        amount=amount_d,
        fee_amount=Decimal("0"),
        tx_type="deposit",
        reference_id=deposit_id,
        reference_type="deposit",
        idempotency_key=idempotency,
        memo=memo,
        created_at=created_at,
        prev_hash=prev_hash,
        entry_hash=entry_hash,
    )
    db.add(ledger)

    await db.commit()
    await db.refresh(ledger)

    # Broadcast deposit event
    try:
        from marketplace.main import broadcast_event
        fire_and_forget(broadcast_event("deposit", {
            "agent_id": agent_id,
            "amount_usd": float(amount_d),
        }), task_name="broadcast_deposit")
    except Exception:
        pass

    logger.info(
        "Deposit %s: +$%s USD to agent %s (%s)",
        ledger.id,
        amount_d,
        agent_id,
        memo,
    )
    return ledger


async def debit_for_purchase(
    db: AsyncSession,
    buyer_id: str,
    seller_id: str,
    amount_usdc: float | Decimal,
    tx_id: str,
) -> dict:
    """Execute the full purchase flow: transfer USD with platform fee.

    Args:
        buyer_id:  Agent ID of the buyer.
        seller_id: Agent ID of the seller.
        amount_usdc: Purchase price in USD.
        tx_id: Transaction ID for reference / idempotency.

    Returns:
        dict with keys: ledger_id, amount_usd, fee_usd,
        buyer_balance, seller_balance.
    """
    amount_d = _to_decimal(amount_usdc)

    # Main transfer
    ledger = await transfer(
        db=db,
        from_agent_id=buyer_id,
        to_agent_id=seller_id,
        amount=amount_d,
        tx_type="purchase",
        reference_id=tx_id,
        reference_type="transaction",
        idempotency_key=f"purchase-{tx_id}",
        memo=f"Purchase for transaction {tx_id}",
    )

    fee_usd = Decimal(str(ledger.fee_amount))

    # Fetch updated balances
    buyer_balance = await get_balance(db, buyer_id)
    seller_balance = await get_balance(db, seller_id)

    return {
        "ledger_id": ledger.id,
        "amount_usd": float(amount_d),
        "fee_usd": float(fee_usd),
        "buyer_balance": buyer_balance["balance"],
        "seller_balance": seller_balance["balance"],
    }


async def get_history(
    db: AsyncSession,
    agent_id: str,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    """Return paginated ledger entries for an agent (as sender or receiver).

    Returns:
        Tuple of (list of ledger dicts, total count).
    """
    account = await _get_account_by_agent(db, agent_id)
    if account is None:
        return [], 0

    condition = or_(
        TokenLedger.from_account_id == account.id,
        TokenLedger.to_account_id == account.id,
    )

    # Total count
    count_result = await db.execute(
        select(func.count(TokenLedger.id)).where(condition)
    )
    total = count_result.scalar() or 0

    # Paginated results
    stmt = (
        select(TokenLedger)
        .where(condition)
        .order_by(TokenLedger.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    entries = result.scalars().all()

    items = []
    for entry in entries:
        direction = "credit" if entry.to_account_id == account.id else "debit"
        items.append(
            {
                "id": entry.id,
                "direction": direction,
                "amount": float(entry.amount),
                "fee_amount": float(entry.fee_amount),
                "tx_type": entry.tx_type,
                "reference_id": entry.reference_id,
                "reference_type": entry.reference_type,
                "memo": entry.memo,
                "created_at": (
                    entry.created_at.isoformat() if entry.created_at else None
                ),
            }
        )

    return items, total


async def get_creator_balance(db: AsyncSession, creator_id: str) -> dict:
    """Return the balance summary for a creator account."""
    account = await _get_account_by_creator(db, creator_id)
    if account is None:
        raise ValueError(f"No token account for creator {creator_id}")

    balance = Decimal(str(account.balance))
    return {
        "balance": float(balance),
        "total_earned": float(account.total_earned),
        "total_spent": float(account.total_spent),
        "total_deposited": float(account.total_deposited),
        "total_fees_paid": float(account.total_fees_paid),
    }
