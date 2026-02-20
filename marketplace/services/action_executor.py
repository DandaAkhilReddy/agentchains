"""Action Executor Service: execute WebMCP actions with payment lifecycle."""

import json
import logging
import time
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.async_tasks import fire_and_forget
from marketplace.models.action_execution import ActionExecution
from marketplace.models.action_listing import ActionListing
from marketplace.models.webmcp_tool import WebMCPTool
from marketplace.services import webmcp_service
from marketplace.services.proof_of_execution_service import (
    _hash_params,
    generate_proof,
    verify_proof,
)

logger = logging.getLogger(__name__)


def _execution_to_dict(ex: ActionExecution) -> dict:
    """Convert ActionExecution ORM to response dict."""
    return {
        "id": ex.id,
        "action_listing_id": ex.action_listing_id,
        "buyer_id": ex.buyer_id,
        "tool_id": ex.tool_id,
        "parameters": json.loads(ex.parameters) if ex.parameters else {},
        "result": json.loads(ex.result) if ex.result else {},
        "status": ex.status,
        "error_message": ex.error_message,
        "execution_time_ms": ex.execution_time_ms,
        "proof_of_execution": ex.proof_of_execution,
        "proof_verified": ex.proof_verified,
        "amount_usdc": float(ex.amount_usdc) if ex.amount_usdc else 0.0,
        "payment_status": ex.payment_status,
        "started_at": ex.started_at.isoformat() if ex.started_at else None,
        "completed_at": ex.completed_at.isoformat() if ex.completed_at else None,
        "created_at": ex.created_at.isoformat() if ex.created_at else None,
    }


def _validate_domain_lock(listing: ActionListing, tool: WebMCPTool) -> None:
    """Verify tool domain matches allowed domains in listing."""
    domain_lock = json.loads(listing.domain_lock) if listing.domain_lock else []
    if not domain_lock:
        return  # No lock — all domains allowed
    if tool.domain not in domain_lock:
        raise ValueError(
            f"Tool domain '{tool.domain}' not in allowed domains: {domain_lock}"
        )


def _validate_tool_lock(tool: WebMCPTool, input_schema: dict) -> None:
    """Verify tool input_schema hasn't been tampered with since registration."""
    if not tool.schema_hash:
        return
    current_hash = _hash_params(input_schema)
    if current_hash != tool.schema_hash:
        raise ValueError("Tool input schema has been modified since registration (Tool Lock violation)")


async def execute_action(
    db: AsyncSession,
    listing_id: str,
    buyer_id: str,
    parameters: dict,
    consent: bool = False,
) -> dict:
    """Execute a WebMCP action through the marketplace.

    Lifecycle: hold funds → execute → verify proof → capture/release funds.
    """
    # 1. Load listing and tool
    listing = await webmcp_service.get_action_listing_orm(db, listing_id)
    if not listing:
        raise ValueError(f"Action listing {listing_id} not found")
    if listing.status != "active":
        raise ValueError(f"Listing {listing_id} is not active")

    tool = await webmcp_service.get_tool_orm(db, listing.tool_id)
    if not tool:
        raise ValueError(f"Tool {listing.tool_id} not found")

    # 2. Security checks
    if listing.requires_consent and not consent:
        raise ValueError("User consent required for this action")

    _validate_domain_lock(listing, tool)

    tool_input_schema = json.loads(tool.input_schema) if tool.input_schema else {}
    _validate_tool_lock(tool, tool_input_schema)

    # 3. Create execution record with funds held
    execution = ActionExecution(
        action_listing_id=listing_id,
        buyer_id=buyer_id,
        tool_id=tool.id,
        parameters=json.dumps(parameters),
        status="pending",
        amount_usdc=float(listing.price_per_execution),
        payment_status="held",
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)

    # 4. Execute the tool (simulated for now)
    start_time = time.monotonic()
    execution.status = "executing"
    execution.started_at = datetime.now(timezone.utc)
    await db.commit()

    try:
        # Simulated execution — returns mock result
        result = _simulate_tool_execution(tool, parameters)
        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        # 5. Generate proof-of-execution
        proof_jwt = generate_proof(
            execution_id=execution.id,
            tool_id=tool.id,
            parameters=parameters,
            result=result,
            status="success",
        )

        # 6. Verify the proof
        verification = verify_proof(proof_jwt, expected_params_hash=_hash_params(parameters))

        # 7. Update execution record
        execution.result = json.dumps(result)
        execution.status = "completed"
        execution.execution_time_ms = elapsed_ms
        execution.proof_of_execution = proof_jwt
        execution.proof_verified = verification["valid"]
        execution.payment_status = "captured" if verification["valid"] else "released"
        execution.completed_at = datetime.now(timezone.utc)

        # 8. Update tool stats
        tool.execution_count += 1
        if tool.avg_execution_time_ms == 0:
            tool.avg_execution_time_ms = elapsed_ms
        else:
            tool.avg_execution_time_ms = (tool.avg_execution_time_ms + elapsed_ms) // 2

        # Update listing access count
        listing.access_count += 1

        await db.commit()
        await db.refresh(execution)

        # 9. Broadcast event
        _broadcast_execution_event("action_executed", execution)

        logger.info(
            "Action executed: %s (tool=%s, time=%dms, verified=%s)",
            execution.id, tool.id, elapsed_ms, verification["valid"],
        )

    except Exception as e:
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        execution.status = "failed"
        execution.error_message = str(e)
        execution.execution_time_ms = elapsed_ms
        execution.payment_status = "released"
        execution.completed_at = datetime.now(timezone.utc)

        # Update tool success rate
        if tool.execution_count > 0:
            successes = float(tool.success_rate) * tool.execution_count
            tool.execution_count += 1
            tool.success_rate = successes / tool.execution_count

        await db.commit()
        await db.refresh(execution)
        logger.error("Action execution failed: %s — %s", execution.id, e)

    return _execution_to_dict(execution)


def _simulate_tool_execution(tool: WebMCPTool, parameters: dict) -> dict:
    """Simulated tool execution for development.

    In production, this would use Playwright for browser automation
    or direct HTTP calls to the WebMCP endpoint.
    """
    return {
        "tool_name": tool.name,
        "domain": tool.domain,
        "status": "success",
        "data": {
            "message": f"Simulated execution of {tool.name}",
            "parameters_received": parameters,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }


async def get_execution(db: AsyncSession, execution_id: str) -> dict | None:
    """Get a single execution by ID."""
    result = await db.execute(
        select(ActionExecution).where(ActionExecution.id == execution_id)
    )
    ex = result.scalar_one_or_none()
    if not ex:
        return None
    return _execution_to_dict(ex)


async def list_executions(
    db: AsyncSession,
    buyer_id: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    """List executions with optional filters."""
    query = select(ActionExecution)
    count_query = select(func.count(ActionExecution.id))

    if buyer_id:
        query = query.where(ActionExecution.buyer_id == buyer_id)
        count_query = count_query.where(ActionExecution.buyer_id == buyer_id)

    if status:
        query = query.where(ActionExecution.status == status)
        count_query = count_query.where(ActionExecution.status == status)

    total = (await db.execute(count_query)).scalar() or 0
    query = query.order_by(ActionExecution.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    executions = [_execution_to_dict(ex) for ex in result.scalars().all()]

    return executions, total


async def cancel_execution(
    db: AsyncSession,
    execution_id: str,
    buyer_id: str,
) -> dict | None:
    """Cancel a pending execution and release held funds."""
    result = await db.execute(
        select(ActionExecution).where(ActionExecution.id == execution_id)
    )
    ex = result.scalar_one_or_none()
    if not ex:
        return None
    if ex.buyer_id != buyer_id:
        raise ValueError("Not authorized to cancel this execution")
    if ex.status not in ("pending",):
        raise ValueError(f"Cannot cancel execution in status '{ex.status}'")

    ex.status = "failed"
    ex.error_message = "Cancelled by buyer"
    ex.payment_status = "released"
    ex.completed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(ex)

    logger.info("Execution cancelled: %s by buyer %s", execution_id, buyer_id)
    return _execution_to_dict(ex)


def _broadcast_execution_event(event_type: str, execution: ActionExecution) -> None:
    """Fire-and-forget WebSocket broadcast for execution events."""
    try:
        from marketplace.main import broadcast_event
        fire_and_forget(
            broadcast_event(event_type, {
                "execution_id": execution.id,
                "action_listing_id": execution.action_listing_id,
                "buyer_id": execution.buyer_id,
                "tool_id": execution.tool_id,
                "status": execution.status,
                "amount_usdc": float(execution.amount_usdc),
            }),
            task_name=f"broadcast_{event_type}",
        )
    except Exception:
        pass
