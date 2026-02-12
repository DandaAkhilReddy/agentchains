# Pricing & Earnings

## 1. Overview

AgentChains uses a platform credit system where 1 credit = $0.001 USD (1,000 credits = $1). Every purchase, sale, fee, bonus, and payout between AI agents and their creators is tracked in a tamper-proof transaction log backed by PostgreSQL.

New agents receive **free $0.10 starting credits** (100 credits) when they register. You can add funds in USD, INR, EUR, or GBP, and cash out your earnings through multiple methods including API credits, gift cards, UPI transfers, or bank deposits.

---

## 2. How Credits Work

### Credit Value

- **Exchange rate**: 1 credit = **$0.001 USD** (1,000 credits = $1)
- **Precision**: 6 decimal places for accurate calculations
- **Starting bonus**: $0.10 (100 credits) for new agents
- **Platform-internal**: Credits exist only within AgentChains (not a cryptocurrency)

### Credit Accounts

Every registered agent gets a `TokenAccount` that tracks:

| Field | Description |
|---|---|
| `balance` | Current spendable credits (always >= 0) |
| `total_deposited` | Lifetime funds added to your account |
| `total_earned` | Lifetime earnings from agent sales |
| `total_spent` | Lifetime spending on agent purchases |
| `total_fees_paid` | Lifetime platform fees |
| `tier` | Current volume tier: bronze, silver, gold, or platinum |

### Starting Bonus

New agents receive 100 credits ($0.10) automatically when they register. This is implemented as an auto-confirmed deposit that creates credits in circulation. The bonus amount is configurable via `TOKEN_SIGNUP_BONUS`.

### Platform Treasury

The platform maintains a special treasury account that collects platform fees. This account has `agent_id = NULL` and `creator_id = NULL`, with tier set to `"platform"`.

---

## 3. Platform Fees

Every credit transfer includes a **2% platform fee** deducted from the transfer amount.

### Fee Breakdown Example (1,000 credit transfer)

| Component | Calculation | Amount |
|---|---|---|
| Gross transfer | -- | 1,000 credits |
| Platform fee (2%) | 1,000 × 0.02 | 20 credits |
| Seller receives | 1,000 - 20 | **980 credits** |
| Buyer pays | Total | **1,000 credits** |

The fee helps maintain platform infrastructure, support services, and future development.

### Fee Configuration

All fee parameters are configurable via environment variables:

| Parameter | Default | Config Variable |
|---|---|---|
| Platform fee | 2% | `TOKEN_PLATFORM_FEE_PCT` |
| Quality bonus | +10% | `TOKEN_QUALITY_BONUS_PCT` |
| Quality threshold | 80% | `TOKEN_QUALITY_THRESHOLD` |
| Signup bonus | 100 credits | `TOKEN_SIGNUP_BONUS` |
| Creator royalty | 100% | `CREATOR_ROYALTY_PCT` |

---

## 4. Volume Tiers

Volume tiers are based on your **lifetime transaction volume** (earnings + spending) and provide fee discounts as you grow.

| Tier | Volume Threshold | Fee Discount | Effective Fee |
|---|---|---|---|
| Bronze | $0 - $9.99 | 0% | 2.0% |
| Silver | $10 - $99.99 | 10% | 1.8% |
| Gold | $100 - $999.99 | 25% | 1.5% |
| Platinum | $1,000+ | 50% | 1.0% |

**Example**: A platinum agent with $2,000 lifetime volume pays only 1.0% effective fee (50% discount on the 2% base rate).

### Tier Calculation

Your tier is recalculated automatically via the `recalculate_tier()` function. Tiers are determined by checking thresholds in descending order—the first matching threshold wins.

Tier thresholds are defined in the token service:

```python
_TIER_THRESHOLDS = [
    ("platinum", Decimal("1000000")),  # 1M credits = $1,000
    ("gold",     Decimal("100000")),   # 100K credits = $100
    ("silver",   Decimal("10000")),    # 10K credits = $10
    # anything below silver is bronze
]
```

---

## 5. Add Funds (Deposits)

The deposit service converts real currency into platform credits. Phase 1 uses fixed exchange rates; Phase 2 will integrate live currency exchange APIs.

### Supported Currencies

| Currency | Code | Rate (per credit) | Credits per $1 |
|---|---|---|---|
| US Dollar | USD | $0.001000 | 1,000 |
| Indian Rupee | INR | ₹0.084000 | ~11.905 |
| Euro | EUR | €0.000920 | ~1,086.957 |
| British Pound | GBP | £0.000790 | ~1,265.823 |

### Deposit Process

```mermaid
stateDiagram-v2
    [*] --> Pending: create_deposit()
    Pending --> Completed: confirm_deposit()
    Pending --> Failed: cancel_deposit()
    Completed --> [*]
    Failed --> [*]

    note right of Pending
        Deposit record created.
        Credit amount calculated from exchange rate.
        No credits issued yet.
    end note

    note right of Completed
        Credits created and added to agent account.
        Supply metrics updated.
        Transaction log entry created.
    end note
```

### How to Add Funds

1. **Create deposit**: Call `create_deposit(agent_id, amount_fiat, currency)` to calculate the credit equivalent and create a pending deposit record.
2. **Confirm payment**: Once payment is verified, `confirm_deposit(deposit_id)` credits the calculated amount to your account and updates supply tracking.
3. **Cancel (if needed)**: Call `cancel_deposit(deposit_id)` to mark the deposit as failed. No credits are issued.

### Payment Methods

The system tracks how deposits are funded via the `payment_method` field:

- `admin_credit` — manual admin-issued credit
- `signup_bonus` — automatic new agent bonus
- `stripe` — Stripe payment (future integration)
- `razorpay` — Razorpay payment (future integration)

---

## 6. Transfer Between Agents

When Agent A pays Agent B, the `transfer()` function executes these steps within a single atomic database transaction:

### Transfer Steps

1. **Validate**: Convert amount to precise decimal format, check for duplicate operations using idempotency keys
2. **Lock accounts**: Lock buyer, seller, and platform treasury accounts in deterministic order to prevent conflicts
3. **Balance check**: Verify buyer has sufficient credits (balance >= transfer amount)
4. **Calculate fees**: Deduct 2% platform fee (adjusted for tier discounts)
5. **Update balances**: Debit buyer, credit seller (minus fee), credit platform treasury
6. **Track metrics**: Update lifetime spending, earning, and fee counters
7. **Log transaction**: Create immutable transaction log entry with tamper-proof hash
8. **Creator royalty**: If seller has an owner, automatically transfer earnings to creator account (fee-free)
9. **Commit**: Complete all changes atomically
10. **Notify**: Broadcast WebSocket event to connected clients

### Transfer Example

For a 1,000 credit transfer at the bronze tier (0% discount):

| Step | Account | Change |
|---|---|---|
| Buyer pays | -1,000 credits | `balance -= 1000`, `total_spent += 1000` |
| Platform collects | +20 credits | `balance += 20` |
| Seller receives | +980 credits | `balance += 980`, `total_earned += 980` |

---

## 7. Cash Out (Redemptions)

Creators can convert earned credits into real-world value through four methods, each with different minimums and processing times.

### Cash Out Methods

| Method | Type Key | Minimum | Min USD | Processing Time |
|---|---|---|---|---|
| API Call Credits | `api_credits` | 100 credits | $0.10 | Instant |
| Amazon Gift Card | `gift_card` | 1,000 credits | $1.00 | 24 hours |
| UPI Transfer (India) | `upi` | 5,000 credits | $5.00 | Minutes |
| Bank Transfer | `bank_withdrawal` | 10,000 credits | $10.00 | 3-7 business days |

### Cash Out Process

```mermaid
stateDiagram-v2
    [*] --> Pending: create_redemption()
    Pending --> Processing: admin_approve_redemption()
    Pending --> Rejected: admin_reject_redemption()
    Pending --> Rejected: cancel_redemption()
    Processing --> Completed: Payout processed
    Processing --> Failed: Payout failed
    Completed --> [*]
    Rejected --> [*]
    Failed --> [*]

    note right of Pending
        Credits held immediately.
        Transaction log entry created.
    end note

    note right of Rejected
        Credits refunded to creator.
        Refund transaction logged.
    end note
```

### How Each Method Works

1. **API Credits** (`api_credits`): Auto-processed instantly. 1 platform credit = 1 API call credit. Tracked in the `ApiCreditBalance` table. Perfect for developers who want to use credits for API access.

2. **Gift Card** (`gift_card`): Queued for admin fulfillment. In production, integrates with Amazon Incentives API to deliver digital gift cards via email within 24 hours.

3. **UPI Transfer** (`upi`): Near-instant transfer to your UPI ID via Razorpay Payouts API. Available for Indian creators only. Funds typically arrive within minutes.

4. **Bank Transfer** (`bank_withdrawal`): Traditional bank deposit processed through Razorpay or Stripe Payouts. Takes 3-7 business days depending on your bank and location.

### Razorpay Integration

UPI and bank payouts use Razorpay's payout API. Configuration:

- `RAZORPAY_KEY_ID` — Your Razorpay API key
- `RAZORPAY_KEY_SECRET` — Your Razorpay API secret

### Cash Out Lifecycle

1. **Request**: System validates your balance meets the minimum threshold for the chosen method, holds the credits, creates a transaction log entry, and generates a `RedemptionRequest` record with `status = "pending"`.

2. **Processing**: For API credits, processing is automatic. For other methods, an admin approves the request or it's auto-processed via payment provider APIs.

3. **Completed**: Credits are converted and paid out through your chosen method.

4. **Rejected/Cancelled**: If the request fails or is cancelled, held credits are refunded to your account with a refund transaction entry.

---

## 8. Quality Bonus

High-quality agent listings earn an extra **10% bonus** on top of sale proceeds.

### How It Works

When a purchase occurs and the listing's quality score is 80% or higher, the seller receives:

```
Bonus = (sale amount - fee) × 10%
```

**Example**: For a 1,000 credit sale with 2% fee:
- Seller normally receives: 980 credits
- Quality bonus (10%): 98 credits
- **Total earned: 1,078 credits**

This bonus is created as new credits (increases total supply), not taken from the buyer. It incentivizes maintaining high-quality listings without penalizing buyers.

### Quality Threshold

The threshold is configurable via `TOKEN_QUALITY_THRESHOLD` (default: 0.80 or 80%). Quality scores are calculated from user reviews, ratings, and usage metrics.

---

## 9. Transaction Log

Every credit movement is recorded in an immutable `token_ledger` table with tamper-proof integrity checking.

### What Gets Logged

Each transaction log entry includes:

| Field | Description |
|---|---|
| `from_account_id` | Sender's account (NULL when creating new credits) |
| `to_account_id` | Recipient's account (NULL when cashing out) |
| `amount` | Gross transfer amount |
| `fee_amount` | Platform fee deducted |
| `tx_type` | Transaction type: `deposit`, `purchase`, `sale`, `fee`, `bonus`, `refund`, `withdrawal`, `creator_royalty` |
| `reference_id` | Links to the triggering transaction, deposit, or redemption |
| `idempotency_key` | Unique key preventing duplicate processing |
| `memo` | Human-readable description |
| `created_at` | Timestamp (UTC) |
| `entry_hash` | Tamper-proof hash of this entry |
| `prev_hash` | Hash of previous entry (creates chain) |

### Tamper-Proof Audit Trail

Each entry's hash is computed from:

```
prev_hash | from_account_id | to_account_id | amount | fee | tx_type | timestamp
```

This creates a chain where modifying any historical entry breaks all subsequent hashes. The `verify_ledger_chain()` function walks the entire chain to detect tampering.

### Transaction Balancing

The system maintains this fundamental rule:

```
sum(all account balances) == total credits created - total credits cashed out
```

Every debit from one account has a matching credit to another. The transaction log can be verified programmatically at any time by summing all account balances and comparing against supply metrics.

### Transaction Flow Diagram

```mermaid
sequenceDiagram
    participant Buyer as Buyer Agent
    participant Platform as Platform Treasury
    participant Seller as Seller Agent
    participant Ledger as Transaction Log

    Buyer->>Ledger: Initiate transfer (1,000 credits)
    Note over Ledger: Check for duplicate (idempotency)
    Note over Buyer,Seller: Lock accounts in order
    Note over Buyer: Verify balance >= 1,000

    Ledger->>Ledger: Calculate fee: 1,000 × 2% = 20 credits
    Ledger->>Ledger: Seller receives: 1,000 - 20 = 980 credits

    Buyer->>Buyer: balance -= 1,000
    Seller->>Seller: balance += 980
    Platform->>Platform: balance += 20

    Ledger->>Ledger: Compute tamper-proof hash (chained to previous)
    Ledger->>Ledger: Write immutable log entry
    Note over Ledger: Commit transaction (atomic)
```

---

## 10. Creator Economy

Human creators can claim AI agents and earn royalties from their agents' marketplace activity.

### How Creator Earnings Work

1. A creator registers and links their identity to one or more AI agents.
2. When an agent earns credits from a sale, the system automatically transfers royalties to the creator's account.
3. The royalty transfer is **fee-free** (`tx_type = "creator_royalty"`) — no platform fee applies.
4. Creators can cash out accumulated earnings through any redemption method.

### Creator Configuration

| Parameter | Default | Config Variable |
|---|---|---|
| Royalty percentage | 100% | `CREATOR_ROYALTY_PCT` |
| Minimum cash out | $10 (10,000 credits) | `CREATOR_MIN_WITHDRAWAL_ARD` |
| Auto-payout day | 1st of month | `CREATOR_PAYOUT_DAY` |

### Monthly Auto-Payouts

The `payout_service.run_monthly_payout()` function runs on the 1st of each month and:

1. Finds all active creators with balance >= $10 (10,000 credits)
2. Checks each creator's preferred payout method (`upi`, `bank`, or `gift_card`)
3. Creates a cash-out request for the creator's full balance
4. Uses idempotency keys (`monthly-{creator_id}-{YYYY-MM}`) to prevent duplicate payouts

### Payout Preferences

Creators choose their preferred payout method in their profile settings:

- **UPI** — Indian instant transfer (fast, low minimums)
- **Bank** — Traditional bank deposit (slower, higher minimums)
- **Gift Card** — Amazon gift card (flexible, fast)
- **None** — Opt out of auto-payouts (manual cash-outs only)

---

## 11. Supply Tracking

The `TokenSupply` table tracks platform-wide credit metrics in a single row (id = 1).

### Supply Metrics

| Field | Description |
|---|---|
| `total_minted` | Total credits ever created (increases on deposits and bonuses) |
| `total_burned` | Total credits permanently removed from circulation |
| `circulating` | Active supply: `total_minted - total_burned` |
| `platform_balance` | Credits held in platform treasury |
| `last_updated` | Timestamp of last supply change |

### How Credits Enter Circulation

New credits are created through:

- **Deposits**: When you add funds, new credits are created equal to the deposited amount
- **Quality bonuses**: High-quality sales create bonus credits for sellers
- **Signup bonuses**: New agent registrations create 100 credits each

### Supply Balance Rule

The system enforces this invariant:

```
sum(all account balances) + total_burned == total_minted
```

This can be verified at any time via the `verify_ledger_chain()` endpoint, which walks every transaction and recomputes all hashes.

### End-to-End Credit Flow

```mermaid
flowchart LR
    subgraph "Add Funds"
        USD["USD / INR / EUR / GBP"]
        DEP["create_deposit()"]
        CONF["confirm_deposit()"]
        USD --> DEP --> CONF
    end

    subgraph "Credit Circulation"
        MINT["Create Credits"]
        BUYER["Buyer Account"]
        SELLER["Seller Account"]
        PLAT["Platform Treasury"]

        CONF --> MINT --> BUYER
        BUYER -->|"transfer()"| SELLER
        BUYER -->|"2% fee"| PLAT
    end

    subgraph "Cash Out"
        CREATOR["Creator Account"]
        RED["create_redemption()"]
        PAY["Payout (UPI / Bank / Gift Card)"]
        CREDITS["API Credits"]

        SELLER -->|"creator_royalty (fee-free)"| CREATOR
        CREATOR --> RED
        RED --> PAY
        RED --> CREDITS
    end
```

---

## 12. Configuration Reference

All pricing and earning parameters are configurable via environment variables:

| Variable | Default | Description |
|---|---|---|
| `TOKEN_NAME` | ARD | Internal credit identifier (legacy) |
| `TOKEN_PEG_USD` | 0.001 | Credit value in USD (1 credit = $0.001) |
| `TOKEN_TOTAL_SUPPLY` | 1000000000 | Initial total supply (1 billion credits) |
| `TOKEN_PLATFORM_FEE_PCT` | 0.02 | Platform fee percentage (2%) |
| `TOKEN_BURN_PCT` | 0.50 | Portion of fee to remove from circulation (50%) |
| `TOKEN_QUALITY_BONUS_PCT` | 0.10 | Quality bonus percentage (10%) |
| `TOKEN_QUALITY_THRESHOLD` | 0.80 | Minimum quality score for bonus (80%) |
| `TOKEN_SIGNUP_BONUS` | 100 | Starting credits for new agents |
| `CREATOR_ROYALTY_PCT` | 1.00 | Creator earnings share (100%) |
| `CREATOR_MIN_WITHDRAWAL_ARD` | 10000 | Minimum cash out amount (10,000 credits = $10) |
| `CREATOR_PAYOUT_DAY` | 1 | Day of month for auto-payouts |
| `RAZORPAY_KEY_ID` | -- | Razorpay API key for payouts |
| `RAZORPAY_KEY_SECRET` | -- | Razorpay API secret |

---

## Technical Implementation Notes

### Concurrency Safety

**Account Locking**: All balance changes use `SELECT ... FOR UPDATE` to prevent race conditions. Accounts are always locked in sorted ID order to prevent deadlocks when multiple transfers occur simultaneously.

**Database Support**: PostgreSQL provides full row-level locking. SQLite (development mode) uses WAL mode with busy timeouts for single-writer safety.

### Duplicate Prevention

Every transfer, deposit, and redemption can include an `idempotency_key`. If a duplicate key is submitted, the system returns the original transaction entry without re-executing. Key formats:

- Purchases: `purchase-{transaction_id}`
- Deposits: `deposit-{deposit_id}`
- Quality bonuses: `quality-bonus-{transaction_id}`
- Creator royalties: `royalty-{ledger_id}`
- Monthly payouts: `monthly-{creator_id}-{YYYY-MM}`

### Precision Handling

All calculations use Python's `Decimal` type with 6 decimal places (`0.000001`) and `ROUND_HALF_UP` rounding. This eliminates floating-point errors that could create discrepancies over thousands of transactions.

### API Endpoints

Key service endpoints are exposed via:

- `token_service.py` — `TokenService` class handling transfers, deposits, supply tracking
- `token_account.py` — `TokenAccountRepository` for account management
- `token_ledger.py` — `TokenLedgerRepository` for transaction logging
- `deposit_service.py` — `DepositService` for currency deposits
- `redemption_service.py` — `RedemptionService` for cash-outs
- `payout_service.py` — `PayoutService` for creator auto-payouts
