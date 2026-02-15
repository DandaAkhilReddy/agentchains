"""Services for dual-layer developer builder and end-user buyer workflows."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.async_tasks import fire_and_forget
from marketplace.core.user_auth import create_user_token, hash_password, verify_password
from marketplace.models.agent import RegisteredAgent
from marketplace.models.creator import Creator
from marketplace.models.dual_layer import (
    BuilderProject,
    ConsumerOrder,
    DeveloperProfile,
    EndUser,
    PlatformFee,
)
from marketplace.models.listing import DataListing
from marketplace.models.redemption import RedemptionRequest
from marketplace.schemas.agent import AgentRegisterRequest
from marketplace.schemas.listing import ListingCreateRequest
from marketplace.services import express_service, listing_service, registry_service
from marketplace.services.token_service import create_account, ensure_platform_account

_FEE_RATE = Decimal("0.10")
_FEE_POLICY_VERSION = "dual-layer-fee-v1"
_LISTING_CATEGORIES = {
    "web_search",
    "code_analysis",
    "document_summary",
    "api_response",
    "computation",
}
_TRUST_VERIFIED = "verified_secure_data"

_BUILDER_TEMPLATES: list[dict[str, object]] = [
    {
        "key": "firecrawl-web-research",
        "name": "Firecrawl Web Research",
        "description": "Collect and summarize web research outputs for resale.",
        "default_category": "web_search",
        "suggested_price_usd": 0.35,
    },
    {
        "key": "api-monitoring-report",
        "name": "API Monitoring Report",
        "description": "Package stable API status summaries with trend snapshots.",
        "default_category": "api_response",
        "suggested_price_usd": 0.22,
    },
    {
        "key": "code-quality-audit",
        "name": "Code Quality Audit",
        "description": "Publish reusable lint/test/audit findings for repositories.",
        "default_category": "code_analysis",
        "suggested_price_usd": 0.40,
    },
    {
        "key": "doc-brief-pack",
        "name": "Document Brief Pack",
        "description": "Transform long docs into concise buyer-friendly briefs.",
        "default_category": "document_summary",
        "suggested_price_usd": 0.18,
    },
    {
        "key": "computation-snapshot",
        "name": "Computation Snapshot",
        "description": "Publish deterministic computation outputs and assumptions.",
        "default_category": "computation",
        "suggested_price_usd": 0.28,
    },
]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _to_decimal(value: float | int | str | Decimal) -> Decimal:
    if isinstance(value, Decimal):
        return value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    return Decimal(str(value)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def _to_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _load_json(value: str | None, fallback: object) -> object:
    if not value:
        return fallback
    try:
        parsed = json.loads(value)
    except Exception:
        return fallback
    return parsed


def _safe_listing_category(value: object) -> str:
    category = str(value or "api_response").strip()
    if category in _LISTING_CATEGORIES:
        return category
    return "api_response"


def _market_listing_payload(listing: DataListing, seller_name: str) -> dict:
    trust_status = listing.trust_status or "pending_verification"
    return {
        "id": listing.id,
        "title": listing.title,
        "description": listing.description,
        "category": listing.category,
        "seller_id": listing.seller_id,
        "seller_name": seller_name,
        "price_usd": _to_float(listing.price_usdc, default=0.0),
        "currency": listing.currency,
        "trust_status": trust_status,
        "trust_score": int(listing.trust_score or 0),
        "requires_unverified_confirmation": trust_status != _TRUST_VERIFIED,
        "freshness_at": listing.freshness_at,
        "created_at": listing.created_at,
    }


def _user_to_payload(user: EndUser) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "status": user.status,
        "managed_agent_id": user.managed_agent_id,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "last_login_at": user.last_login_at,
    }


async def register_end_user(db: AsyncSession, *, email: str, password: str) -> dict:
    normalized_email = email.lower().strip()
    existing = await db.execute(select(EndUser).where(EndUser.email == normalized_email))
    if existing.scalar_one_or_none():
        raise ValueError("Email already registered")

    local_part = normalized_email.split("@")[0][:16] or "buyer"
    managed_name = f"user-{local_part}-{uuid.uuid4().hex[:6]}-buyer"
    register_req = AgentRegisterRequest(
        name=managed_name,
        description="Managed buyer agent for end-user purchases",
        agent_type="buyer",
        public_key="managed-user-public-key-rotated-by-platform",
        wallet_address="",
        capabilities=["market.consume", "market.orders"],
        a2a_endpoint="",
    )
    managed = await registry_service.register_agent(db, register_req)
    await ensure_platform_account(db)
    await create_account(db, managed.id)

    user = EndUser(
        id=str(uuid.uuid4()),
        email=normalized_email,
        password_hash=hash_password(password),
        managed_agent_id=managed.id,
        status="active",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return {
        "user": _user_to_payload(user),
        "token": create_user_token(user.id, user.email),
    }


async def login_end_user(db: AsyncSession, *, email: str, password: str) -> dict:
    normalized_email = email.lower().strip()
    result = await db.execute(select(EndUser).where(EndUser.email == normalized_email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(password, user.password_hash):
        raise ValueError("Invalid email or password")
    if user.status != "active":
        raise ValueError("User account is not active")
    user.last_login_at = _utcnow()
    await db.commit()
    await db.refresh(user)
    return {
        "user": _user_to_payload(user),
        "token": create_user_token(user.id, user.email),
    }


async def get_end_user_by_id(db: AsyncSession, *, user_id: str) -> EndUser:
    result = await db.execute(select(EndUser).where(EndUser.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise ValueError(f"User {user_id} not found")
    return user


async def get_end_user_payload(db: AsyncSession, *, user_id: str) -> dict:
    user = await get_end_user_by_id(db, user_id=user_id)
    return _user_to_payload(user)


async def list_market_listings(
    db: AsyncSession,
    *,
    q: str | None = None,
    category: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    query = select(DataListing).where(DataListing.status == "active")
    count_query = select(func.count(DataListing.id)).where(DataListing.status == "active")

    if q:
        pattern = f"%{q}%"
        condition = (
            DataListing.title.ilike(pattern)
            | DataListing.description.ilike(pattern)
            | DataListing.tags.ilike(pattern)
        )
        query = query.where(condition)
        count_query = count_query.where(condition)

    if category:
        query = query.where(DataListing.category == category)
        count_query = count_query.where(DataListing.category == category)

    trust_rank = case(
        (DataListing.trust_status == "verified_secure_data", 0),
        (DataListing.trust_status == "pending_verification", 1),
        (DataListing.trust_status == "verification_failed", 2),
        else_=3,
    )
    query = query.order_by(trust_rank.asc(), DataListing.freshness_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    total = int((await db.execute(count_query)).scalar() or 0)
    listings = list((await db.execute(query)).scalars().all())
    seller_ids = {listing.seller_id for listing in listings}
    names_map: dict[str, str] = {}
    if seller_ids:
        sellers = await db.execute(
            select(RegisteredAgent.id, RegisteredAgent.name).where(
                RegisteredAgent.id.in_(seller_ids)
            )
        )
        names_map = {row[0]: row[1] for row in sellers.all()}

    payloads = [
        _market_listing_payload(listing, seller_name=names_map.get(listing.seller_id, "Unknown"))
        for listing in listings
    ]
    return payloads, total


async def get_market_listing(db: AsyncSession, *, listing_id: str) -> dict:
    listing = await listing_service.get_listing(db, listing_id)
    seller = await db.execute(
        select(RegisteredAgent.name).where(RegisteredAgent.id == listing.seller_id)
    )
    seller_name = seller.scalar_one_or_none() or "Unknown"
    return _market_listing_payload(listing, seller_name=seller_name)


def list_builder_templates() -> list[dict[str, object]]:
    return [dict(item) for item in _BUILDER_TEMPLATES]


async def get_or_create_developer_profile(db: AsyncSession, *, creator_id: str) -> DeveloperProfile:
    result = await db.execute(select(DeveloperProfile).where(DeveloperProfile.creator_id == creator_id))
    profile = result.scalar_one_or_none()
    if profile is None:
        profile = DeveloperProfile(creator_id=creator_id)
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
    return profile


def _developer_profile_payload(profile: DeveloperProfile) -> dict:
    links = _load_json(profile.links_json, [])
    if not isinstance(links, list):
        links = []
    specialties = _load_json(profile.specialties_json, [])
    if not isinstance(specialties, list):
        specialties = []
    return {
        "creator_id": profile.creator_id,
        "bio": profile.bio or "",
        "links": [str(item) for item in links],
        "specialties": [str(item) for item in specialties],
        "featured_flag": bool(profile.featured_flag),
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
    }


async def get_developer_profile_payload(db: AsyncSession, *, creator_id: str) -> dict:
    profile = await get_or_create_developer_profile(db, creator_id=creator_id)
    return _developer_profile_payload(profile)


async def update_developer_profile(
    db: AsyncSession,
    *,
    creator_id: str,
    bio: str,
    links: list[str],
    specialties: list[str],
    featured_flag: bool,
) -> dict:
    profile = await get_or_create_developer_profile(db, creator_id=creator_id)
    profile.bio = bio
    profile.links_json = json.dumps(list(links))
    profile.specialties_json = json.dumps(list(specialties))
    profile.featured_flag = featured_flag
    profile.updated_at = _utcnow()
    await db.commit()
    await db.refresh(profile)
    return _developer_profile_payload(profile)


def _builder_project_payload(project: BuilderProject) -> dict:
    return {
        "id": project.id,
        "creator_id": project.creator_id,
        "template_key": project.template_key,
        "title": project.title,
        "status": project.status,
        "published_listing_id": project.published_listing_id,
        "created_at": project.created_at,
        "updated_at": project.updated_at,
    }


async def create_builder_project(
    db: AsyncSession,
    *,
    creator_id: str,
    template_key: str,
    title: str,
    config: dict,
) -> dict:
    template_keys = {item["key"] for item in _BUILDER_TEMPLATES}
    if template_key not in template_keys:
        raise ValueError(f"Unknown template_key: {template_key}")

    creator_result = await db.execute(select(Creator.id).where(Creator.id == creator_id))
    if creator_result.scalar_one_or_none() is None:
        raise ValueError(f"Creator {creator_id} not found")

    project = BuilderProject(
        id=str(uuid.uuid4()),
        creator_id=creator_id,
        template_key=template_key,
        title=title.strip(),
        config_json=json.dumps(config or {}),
        status="draft",
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return _builder_project_payload(project)


async def list_builder_projects(db: AsyncSession, *, creator_id: str) -> list[dict]:
    rows = await db.execute(
        select(BuilderProject)
        .where(BuilderProject.creator_id == creator_id)
        .order_by(BuilderProject.created_at.desc())
    )
    return [_builder_project_payload(project) for project in rows.scalars().all()]


async def _get_or_create_creator_seller_agent(db: AsyncSession, *, creator_id: str) -> str:
    existing = await db.execute(
        select(RegisteredAgent)
        .where(
            RegisteredAgent.creator_id == creator_id,
            RegisteredAgent.status == "active",
            RegisteredAgent.agent_type.in_(["seller", "both"]),
        )
        .order_by(RegisteredAgent.created_at.asc())
    )
    row = existing.scalars().first()
    if row is not None:
        return row.id

    req = AgentRegisterRequest(
        name=f"creator-{creator_id[:8]}-publisher-{uuid.uuid4().hex[:6]}",
        description="Managed seller agent for builder project publishing",
        agent_type="both",
        public_key="managed-creator-seller-public-key",
        wallet_address="",
        capabilities=["market.publish", "builder.templates"],
        a2a_endpoint="",
    )
    registered = await registry_service.register_agent(db, req, creator_id=creator_id)
    await ensure_platform_account(db)
    await create_account(db, registered.id)
    return registered.id


def _build_listing_request(project: BuilderProject) -> ListingCreateRequest:
    cfg = _load_json(project.config_json, {})
    if not isinstance(cfg, dict):
        cfg = {}

    template = next(item for item in _BUILDER_TEMPLATES if item["key"] == project.template_key)
    category = _safe_listing_category(cfg.get("category", template["default_category"]))
    price = _to_float(cfg.get("price_usd", template["suggested_price_usd"]), default=0.2)
    if price <= 0:
        price = float(template["suggested_price_usd"])

    metadata = {
        "template_key": project.template_key,
        "builder_project_id": project.id,
        "estimated_fresh_cost_usd": _to_float(cfg.get("estimated_fresh_cost_usd"), default=max(price * 1.8, 0.05)),
    }
    metadata.update({k: v for k, v in cfg.items() if k not in {"sample_output", "price_usd", "category"}})

    content_payload = {
        "template_key": project.template_key,
        "project_id": project.id,
        "summary": cfg.get("summary", template["description"]),
        "sample_output": cfg.get(
            "sample_output",
            f"Generated output placeholder for {project.template_key}",
        ),
        "created_at": _utcnow().isoformat(),
    }
    tags = cfg.get("tags")
    if not isinstance(tags, list):
        tags = [project.template_key, "builder", "dual-layer"]

    return ListingCreateRequest(
        title=cfg.get("title", project.title),
        description=cfg.get("description", template["description"]),
        category=category,
        content=json.dumps(content_payload),
        price_usdc=price,
        price_usd=price,
        metadata=metadata,
        tags=[str(item) for item in tags],
        quality_score=max(0.0, min(1.0, _to_float(cfg.get("quality_score"), default=0.8))),
    )


async def publish_builder_project(db: AsyncSession, *, creator_id: str, project_id: str) -> dict:
    project_result = await db.execute(
        select(BuilderProject).where(
            BuilderProject.id == project_id,
            BuilderProject.creator_id == creator_id,
        )
    )
    project = project_result.scalar_one_or_none()
    if project is None:
        raise ValueError(f"Project {project_id} not found")

    if project.published_listing_id:
        return {
            "project": _builder_project_payload(project),
            "listing_id": project.published_listing_id,
        }

    seller_id = await _get_or_create_creator_seller_agent(db, creator_id=creator_id)
    listing_req = _build_listing_request(project)
    listing = await listing_service.create_listing(db, seller_id, listing_req)

    project.status = "published"
    project.published_listing_id = listing.id
    project.updated_at = _utcnow()
    await db.commit()
    await db.refresh(project)
    return {
        "project": _builder_project_payload(project),
        "listing_id": listing.id,
    }


def _order_payload(order: ConsumerOrder, *, include_content: str | None = None) -> dict:
    payload = {
        "id": order.id,
        "listing_id": order.listing_id,
        "tx_id": order.tx_id,
        "status": order.status,
        "amount_usd": _to_float(order.amount_usd, default=0.0),
        "fee_usd": _to_float(order.fee_usd, default=0.0),
        "payout_usd": _to_float(order.payout_usd, default=0.0),
        "trust_status": order.trust_status,
        "warning_acknowledged": bool(order.warning_acknowledged),
        "created_at": order.created_at,
        "content": include_content,
    }
    return payload


async def create_market_order(
    db: AsyncSession,
    *,
    user_id: str,
    listing_id: str,
    payment_method: str = "simulated",
    allow_unverified: bool = False,
) -> dict:
    user = await get_end_user_by_id(db, user_id=user_id)
    listing = await listing_service.get_listing(db, listing_id)

    if listing.trust_status != _TRUST_VERIFIED and not allow_unverified:
        raise ValueError(
            "Listing is not verified. Pass allow_unverified=true to acknowledge risk."
        )

    response = await express_service.express_buy(
        db, listing.id, user.managed_agent_id, payment_method
    )
    payload = json.loads(response.body.decode("utf-8"))

    gross = _to_decimal(payload.get("price_usdc", 0))
    fee = (gross * _FEE_RATE).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    payout = (gross - fee).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

    order = ConsumerOrder(
        id=str(uuid.uuid4()),
        end_user_id=user.id,
        listing_id=listing.id,
        tx_id=payload["transaction_id"],
        amount_usd=gross,
        fee_usd=fee,
        payout_usd=payout,
        status="completed",
        trust_status=listing.trust_status or "pending_verification",
        warning_acknowledged=allow_unverified,
    )
    db.add(order)
    await db.flush()

    db.add(
        PlatformFee(
            id=str(uuid.uuid4()),
            tx_id=order.tx_id,
            order_id=order.id,
            gross_usd=gross,
            fee_usd=fee,
            payout_usd=payout,
            policy_version=_FEE_POLICY_VERSION,
        )
    )
    await db.commit()
    await db.refresh(order)

    try:
        from marketplace.main import broadcast_event

        fire_and_forget(
            broadcast_event(
                "market.order.created",
                {
                    "order_id": order.id,
                    "user_id": user.id,
                    "listing_id": order.listing_id,
                    "tx_id": order.tx_id,
                    "amount_usd": float(gross),
                    "fee_usd": float(fee),
                    "payout_usd": float(payout),
                    "trust_status": order.trust_status,
                },
            ),
            task_name="broadcast_market_order_created",
        )
        fire_and_forget(
            broadcast_event(
                "market.order.public",
                {
                    "order_id": order.id,
                    "listing_id": order.listing_id,
                    "amount_usd": float(gross),
                    "category": listing.category,
                    "trust_status": order.trust_status,
                },
            ),
            task_name="broadcast_market_order_public",
        )
    except Exception:
        pass

    return _order_payload(order, include_content=payload.get("content"))


async def list_market_orders_for_user(
    db: AsyncSession, *, user_id: str, page: int = 1, page_size: int = 20
) -> tuple[list[dict], int]:
    stmt = select(ConsumerOrder).where(ConsumerOrder.end_user_id == user_id)
    count_stmt = select(func.count(ConsumerOrder.id)).where(ConsumerOrder.end_user_id == user_id)
    total = int((await db.execute(count_stmt)).scalar() or 0)
    stmt = (
        stmt.order_by(ConsumerOrder.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = list((await db.execute(stmt)).scalars().all())
    return [_order_payload(order) for order in rows], total


async def get_market_order_for_user(
    db: AsyncSession, *, user_id: str, order_id: str
) -> dict:
    result = await db.execute(
        select(ConsumerOrder).where(
            ConsumerOrder.id == order_id,
            ConsumerOrder.end_user_id == user_id,
        )
    )
    order = result.scalar_one_or_none()
    if order is None:
        raise ValueError(f"Order {order_id} not found")
    return _order_payload(order)


async def get_featured_collections(db: AsyncSession) -> list[dict]:
    names_result = await db.execute(select(RegisteredAgent.id, RegisteredAgent.name))
    name_map = {row[0]: row[1] for row in names_result.all()}

    verified_stmt = (
        select(DataListing)
        .where(
            DataListing.status == "active",
            DataListing.trust_status == _TRUST_VERIFIED,
        )
        .order_by(DataListing.access_count.desc(), DataListing.freshness_at.desc())
        .limit(10)
    )
    latest_stmt = (
        select(DataListing)
        .where(DataListing.status == "active")
        .order_by(DataListing.created_at.desc())
        .limit(10)
    )
    verified_rows = list((await db.execute(verified_stmt)).scalars().all())
    latest_rows = list((await db.execute(latest_stmt)).scalars().all())

    return [
        {
            "key": "verified_hot",
            "title": "Verified and Popular",
            "description": "High-trust listings with strong reuse demand.",
            "listings": [
                _market_listing_payload(row, seller_name=name_map.get(row.seller_id, "Unknown"))
                for row in verified_rows
            ],
        },
        {
            "key": "new_builder_releases",
            "title": "New Builder Releases",
            "description": "Recently published outputs from active developers.",
            "listings": [
                _market_listing_payload(row, seller_name=name_map.get(row.seller_id, "Unknown"))
                for row in latest_rows
            ],
        },
    ]


async def get_dual_layer_open_metrics(db: AsyncSession) -> dict:
    end_users_count = int((await db.execute(select(func.count(EndUser.id)))).scalar() or 0)
    consumer_orders_count = int((await db.execute(select(func.count(ConsumerOrder.id)))).scalar() or 0)
    developer_profiles_count = int(
        (await db.execute(select(func.count(DeveloperProfile.creator_id)))).scalar() or 0
    )
    fee_result = await db.execute(select(func.sum(PlatformFee.fee_usd)))
    platform_fee_volume_usd = _to_float(fee_result.scalar() or 0.0, default=0.0)
    return {
        "end_users_count": end_users_count,
        "consumer_orders_count": consumer_orders_count,
        "developer_profiles_count": developer_profiles_count,
        "platform_fee_volume_usd": round(platform_fee_volume_usd, 6),
    }


async def get_creator_dual_layer_metrics(db: AsyncSession, *, creator_id: str) -> dict:
    agent_rows = await db.execute(
        select(RegisteredAgent.id).where(RegisteredAgent.creator_id == creator_id)
    )
    agent_ids = [row[0] for row in agent_rows.all()]
    if not agent_ids:
        return {
            "creator_gross_revenue_usd": 0.0,
            "creator_platform_fees_usd": 0.0,
            "creator_net_revenue_usd": 0.0,
            "creator_pending_payout_usd": 0.0,
        }

    listing_rows = await db.execute(
        select(DataListing.id).where(DataListing.seller_id.in_(agent_ids))
    )
    listing_ids = [row[0] for row in listing_rows.all()]
    if not listing_ids:
        pending = await _pending_payout_for_creator(db, creator_id=creator_id)
        return {
            "creator_gross_revenue_usd": 0.0,
            "creator_platform_fees_usd": 0.0,
            "creator_net_revenue_usd": 0.0,
            "creator_pending_payout_usd": pending,
        }

    order_rows = await db.execute(
        select(ConsumerOrder).where(ConsumerOrder.listing_id.in_(listing_ids))
    )
    orders = list(order_rows.scalars().all())
    gross = sum(_to_float(order.amount_usd, default=0.0) for order in orders)
    fee = sum(_to_float(order.fee_usd, default=0.0) for order in orders)
    net = sum(_to_float(order.payout_usd, default=0.0) for order in orders)
    pending = await _pending_payout_for_creator(db, creator_id=creator_id)
    return {
        "creator_gross_revenue_usd": round(gross, 6),
        "creator_platform_fees_usd": round(fee, 6),
        "creator_net_revenue_usd": round(net, 6),
        "creator_pending_payout_usd": round(pending, 6),
    }


async def _pending_payout_for_creator(db: AsyncSession, *, creator_id: str) -> float:
    rows = await db.execute(
        select(func.sum(RedemptionRequest.amount_usd)).where(
            RedemptionRequest.creator_id == creator_id,
            RedemptionRequest.status.in_(["pending", "processing"]),
        )
    )
    return _to_float(rows.scalar() or 0.0, default=0.0)
