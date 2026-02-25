"""Tests for marketplace.services.chain_settlement_service — multi-party
chain settlement, cost estimation, and settlement reports.

Uses in-memory SQLite via conftest fixtures.  asyncio_mode = "auto".
External dependencies (token_service.transfer, orchestration_service) are
mocked where necessary to isolate settlement logic.
"""

from __future__ import annotations

import json
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.chain_template import ChainExecution, ChainTemplate
from marketplace.models.listing import DataListing
from marketplace.models.token_account import TokenLedger
from marketplace.models.workflow import WorkflowDefinition, WorkflowExecution, WorkflowNodeExecution
from marketplace.services import chain_settlement_service as svc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _uid() -> str:
    return str(uuid.uuid4())


async def _create_workflow(db: AsyncSession, owner_id: str, graph: dict | None = None) -> WorkflowDefinition:
    wf = WorkflowDefinition(
        id=_uid(),
        name="test-workflow",
        graph_json=json.dumps(graph or {}),
        owner_id=owner_id,
    )
    db.add(wf)
    await db.flush()
    return wf


async def _create_workflow_execution(
    db: AsyncSession, workflow_id: str, initiated_by: str, status: str = "completed",
) -> WorkflowExecution:
    we = WorkflowExecution(
        id=_uid(),
        workflow_id=workflow_id,
        initiated_by=initiated_by,
        status=status,
    )
    db.add(we)
    await db.flush()
    return we


async def _create_node_execution(
    db: AsyncSession,
    execution_id: str,
    node_id: str,
    node_type: str = "agent_call",
    status: str = "completed",
    input_json: str = "{}",
) -> WorkflowNodeExecution:
    ne = WorkflowNodeExecution(
        id=_uid(),
        execution_id=execution_id,
        node_id=node_id,
        node_type=node_type,
        status=status,
        input_json=input_json,
    )
    db.add(ne)
    await db.flush()
    return ne


async def _create_chain_template(
    db: AsyncSession,
    author_id: str,
    graph: dict | None = None,
    workflow_id: str | None = None,
) -> ChainTemplate:
    ct = ChainTemplate(
        id=_uid(),
        name="test-chain",
        graph_json=json.dumps(graph or {"nodes": {}}),
        author_id=author_id,
        workflow_id=workflow_id,
        status="active",
    )
    db.add(ct)
    await db.flush()
    return ct


async def _create_chain_execution(
    db: AsyncSession,
    template_id: str,
    initiated_by: str,
    workflow_execution_id: str | None = None,
    status: str = "completed",
    total_cost_usd: float = 0,
) -> ChainExecution:
    ce = ChainExecution(
        id=_uid(),
        chain_template_id=template_id,
        workflow_execution_id=workflow_execution_id,
        initiated_by=initiated_by,
        status=status,
        total_cost_usd=Decimal(str(total_cost_usd)),
    )
    db.add(ce)
    await db.flush()
    return ce


# ---------------------------------------------------------------------------
# _get_platform_price
# ---------------------------------------------------------------------------


async def test_get_platform_price_from_data_listing(db: AsyncSession, make_agent, make_listing):
    """_get_platform_price prefers DataListing price."""
    seller, _ = await make_agent()
    await make_listing(seller.id, price_usdc=2.50)

    price = await svc._get_platform_price(db, seller.id)
    assert price == Decimal("2.5")


async def test_get_platform_price_fallback_zero(db: AsyncSession, make_agent):
    """_get_platform_price returns Decimal('0') when no listings exist."""
    agent, _ = await make_agent()
    price = await svc._get_platform_price(db, agent.id)
    assert price == Decimal("0")


async def test_get_platform_price_from_catalog_entry(db: AsyncSession, make_agent, make_catalog_entry):
    """_get_platform_price falls back to DataCatalogEntry price_range_min."""
    agent, _ = await make_agent()
    await make_catalog_entry(agent.id, price_range_min=0.005)

    price = await svc._get_platform_price(db, agent.id)
    assert price == Decimal("0.005")


# ---------------------------------------------------------------------------
# settle_chain_execution
# ---------------------------------------------------------------------------


async def test_settle_chain_execution_not_found(db: AsyncSession):
    """settle_chain_execution raises ValueError for non-existent execution."""
    with pytest.raises(ValueError, match="Chain execution not found"):
        await svc.settle_chain_execution(db, "nonexistent-id")


async def test_settle_chain_execution_wrong_status(db: AsyncSession, make_agent):
    """settle_chain_execution raises ValueError for non-completed execution."""
    agent, _ = await make_agent()
    wf = await _create_workflow(db, agent.id)
    we = await _create_workflow_execution(db, wf.id, agent.id)
    ct = await _create_chain_template(db, agent.id, workflow_id=wf.id)
    ce = await _create_chain_execution(
        db, ct.id, agent.id, workflow_execution_id=we.id, status="running",
    )
    await db.commit()

    with pytest.raises(ValueError, match="Cannot settle execution with status 'running'"):
        await svc.settle_chain_execution(db, ce.id)


async def test_settle_chain_execution_no_workflow_exec(db: AsyncSession, make_agent):
    """settle_chain_execution raises ValueError when no workflow_execution_id."""
    agent, _ = await make_agent()
    ct = await _create_chain_template(db, agent.id)
    ce = await _create_chain_execution(
        db, ct.id, agent.id, workflow_execution_id=None, status="completed",
    )
    await db.commit()

    with pytest.raises(ValueError, match="no associated workflow execution"):
        await svc.settle_chain_execution(db, ce.id)


async def test_settle_chain_execution_no_agent_nodes(db: AsyncSession, make_agent):
    """Settlement with no agent_call nodes returns zero total."""
    agent, _ = await make_agent()
    wf = await _create_workflow(db, agent.id)
    we = await _create_workflow_execution(db, wf.id, agent.id)
    ct = await _create_chain_template(db, agent.id, workflow_id=wf.id)
    ce = await _create_chain_execution(db, ct.id, agent.id, workflow_execution_id=we.id)
    # Create a non-agent node
    await _create_node_execution(db, we.id, "transform-1", node_type="transform")
    await db.commit()

    result = await svc.settle_chain_execution(db, ce.id)

    assert result["status"] == "settled"
    assert result["total_settled_usd"] == 0
    assert result["transfers"] == []
    assert result["errors"] == []


async def test_settle_chain_execution_skips_zero_price(db: AsyncSession, make_agent):
    """Nodes with zero platform price are skipped (no transfer attempted)."""
    buyer, _ = await make_agent()
    seller, _ = await make_agent()
    # No listing created for seller, so price = 0

    wf = await _create_workflow(db, buyer.id)
    we = await _create_workflow_execution(db, wf.id, buyer.id)
    ct = await _create_chain_template(db, buyer.id, workflow_id=wf.id)
    ce = await _create_chain_execution(db, ct.id, buyer.id, workflow_execution_id=we.id)

    input_data = json.dumps({"agent_id": seller.id})
    await _create_node_execution(db, we.id, "agent-node-1", input_json=input_data)
    await db.commit()

    result = await svc.settle_chain_execution(db, ce.id)

    assert result["total_settled_usd"] == 0
    assert result["transfers"] == []


@patch("marketplace.services.chain_settlement_service.transfer", new_callable=AsyncMock)
async def test_settle_chain_execution_success(
    mock_transfer: AsyncMock, db: AsyncSession, make_agent, make_listing,
):
    """Successful settlement creates transfers for each priced agent node."""
    buyer, _ = await make_agent()
    seller, _ = await make_agent()
    await make_listing(seller.id, price_usdc=1.50)

    wf = await _create_workflow(db, buyer.id)
    we = await _create_workflow_execution(db, wf.id, buyer.id)
    ct = await _create_chain_template(db, buyer.id, workflow_id=wf.id)
    ce = await _create_chain_execution(db, ct.id, buyer.id, workflow_execution_id=we.id)

    input_data = json.dumps({"agent_id": seller.id})
    await _create_node_execution(db, we.id, "node-A", input_json=input_data)
    await db.commit()

    mock_ledger = MagicMock()
    mock_ledger.id = "ledger-123"
    mock_transfer.return_value = mock_ledger

    result = await svc.settle_chain_execution(db, ce.id)

    assert result["status"] == "settled"
    assert result["total_settled_usd"] == 1.50
    assert len(result["transfers"]) == 1
    assert result["transfers"][0]["agent_id"] == seller.id
    assert result["transfers"][0]["amount_usd"] == 1.50
    assert result["transfers"][0]["ledger_id"] == "ledger-123"
    assert result["errors"] == []

    # Verify transfer called with correct args
    mock_transfer.assert_called_once()
    call_kwargs = mock_transfer.call_args[1]
    assert call_kwargs["from_agent_id"] == buyer.id
    assert call_kwargs["to_agent_id"] == seller.id
    assert call_kwargs["amount"] == Decimal("1.5")
    assert call_kwargs["tx_type"] == "chain_settlement"
    assert call_kwargs["reference_id"] == ce.id


@patch("marketplace.services.chain_settlement_service.transfer", new_callable=AsyncMock)
async def test_settle_chain_execution_partial_failure(
    mock_transfer: AsyncMock, db: AsyncSession, make_agent, make_listing,
):
    """When one transfer fails, result status is 'partial' with errors."""
    buyer, _ = await make_agent()
    seller1, _ = await make_agent()
    seller2, _ = await make_agent()
    await make_listing(seller1.id, price_usdc=1.00)
    await make_listing(seller2.id, price_usdc=2.00)

    wf = await _create_workflow(db, buyer.id)
    we = await _create_workflow_execution(db, wf.id, buyer.id)
    ct = await _create_chain_template(db, buyer.id, workflow_id=wf.id)
    ce = await _create_chain_execution(db, ct.id, buyer.id, workflow_execution_id=we.id)

    await _create_node_execution(
        db, we.id, "node-1", input_json=json.dumps({"agent_id": seller1.id}),
    )
    await _create_node_execution(
        db, we.id, "node-2", input_json=json.dumps({"agent_id": seller2.id}),
    )
    await db.commit()

    mock_ledger = MagicMock()
    mock_ledger.id = "ledger-ok"
    mock_transfer.side_effect = [mock_ledger, ValueError("Insufficient balance")]

    result = await svc.settle_chain_execution(db, ce.id)

    assert result["status"] == "partial"
    assert len(result["transfers"]) == 1
    assert len(result["errors"]) == 1
    assert "Insufficient balance" in result["errors"][0]["error"]


@patch("marketplace.services.chain_settlement_service.transfer", new_callable=AsyncMock)
async def test_settle_chain_execution_agent_from_template_graph(
    mock_transfer: AsyncMock, db: AsyncSession, make_agent, make_listing,
):
    """When agent_id is not in input_json, it falls back to template graph_json."""
    buyer, _ = await make_agent()
    seller, _ = await make_agent()
    await make_listing(seller.id, price_usdc=3.00)

    graph = {
        "nodes": {
            "node-X": {
                "type": "agent_call",
                "config": {"agent_id": seller.id},
            },
        },
    }

    wf = await _create_workflow(db, buyer.id)
    we = await _create_workflow_execution(db, wf.id, buyer.id)
    ct = await _create_chain_template(db, buyer.id, graph=graph, workflow_id=wf.id)
    ce = await _create_chain_execution(db, ct.id, buyer.id, workflow_execution_id=we.id)

    # Node with empty input (no agent_id embedded)
    await _create_node_execution(db, we.id, "node-X", input_json="{}")
    await db.commit()

    mock_ledger = MagicMock()
    mock_ledger.id = "ledger-graph"
    mock_transfer.return_value = mock_ledger

    result = await svc.settle_chain_execution(db, ce.id)

    assert result["status"] == "settled"
    assert result["total_settled_usd"] == 3.00


async def test_settle_chain_execution_skips_non_completed_nodes(db: AsyncSession, make_agent, make_listing):
    """Nodes with status != 'completed' are skipped during settlement."""
    buyer, _ = await make_agent()
    seller, _ = await make_agent()
    await make_listing(seller.id, price_usdc=5.00)

    wf = await _create_workflow(db, buyer.id)
    we = await _create_workflow_execution(db, wf.id, buyer.id)
    ct = await _create_chain_template(db, buyer.id, workflow_id=wf.id)
    ce = await _create_chain_execution(db, ct.id, buyer.id, workflow_execution_id=we.id)

    await _create_node_execution(
        db, we.id, "failed-node",
        input_json=json.dumps({"agent_id": seller.id}),
        status="failed",
    )
    await db.commit()

    result = await svc.settle_chain_execution(db, ce.id)

    assert result["total_settled_usd"] == 0
    assert result["transfers"] == []


@patch("marketplace.services.chain_settlement_service.transfer", new_callable=AsyncMock)
async def test_settle_chain_idempotency_key_format(
    mock_transfer: AsyncMock, db: AsyncSession, make_agent, make_listing,
):
    """Idempotency key follows format: chn-{exec_id[:16]}-{sha256(node_id)[:16]}."""
    import hashlib

    buyer, _ = await make_agent()
    seller, _ = await make_agent()
    await make_listing(seller.id, price_usdc=1.00)

    wf = await _create_workflow(db, buyer.id)
    we = await _create_workflow_execution(db, wf.id, buyer.id)
    ct = await _create_chain_template(db, buyer.id, workflow_id=wf.id)
    ce = await _create_chain_execution(db, ct.id, buyer.id, workflow_execution_id=we.id)

    node_id = "test-node-123"
    await _create_node_execution(
        db, we.id, node_id, input_json=json.dumps({"agent_id": seller.id}),
    )
    await db.commit()

    mock_ledger = MagicMock()
    mock_ledger.id = "ledger-idem"
    mock_transfer.return_value = mock_ledger

    await svc.settle_chain_execution(db, ce.id)

    call_kwargs = mock_transfer.call_args[1]
    expected_hash = hashlib.sha256(node_id.encode()).hexdigest()[:16]
    expected_key = f"chn-{ce.id[:16]}-{expected_hash}"
    assert call_kwargs["idempotency_key"] == expected_key


# ---------------------------------------------------------------------------
# estimate_chain_cost
# ---------------------------------------------------------------------------


async def test_estimate_chain_cost_not_found(db: AsyncSession):
    """estimate_chain_cost raises ValueError for non-existent template."""
    with pytest.raises(ValueError, match="Chain template not found"):
        await svc.estimate_chain_cost(db, "nonexistent-template")


async def test_estimate_chain_cost_single_agent(db: AsyncSession, make_agent, make_listing):
    """estimate_chain_cost sums up agent prices from the template graph."""
    seller, _ = await make_agent()
    await make_listing(seller.id, price_usdc=4.00)

    graph = {
        "nodes": {
            "n1": {"type": "agent_call", "config": {"agent_id": seller.id}},
        },
    }
    ct = await _create_chain_template(db, seller.id, graph=graph)
    await db.commit()

    result = await svc.estimate_chain_cost(db, ct.id)

    assert result["chain_template_id"] == ct.id
    assert result["estimated_total_usd"] == 4.00
    assert len(result["agent_costs"]) == 1
    assert result["agent_costs"][0]["agent_id"] == seller.id


async def test_estimate_chain_cost_multiple_agents(db: AsyncSession, make_agent, make_listing):
    """estimate_chain_cost sums prices across multiple agent nodes."""
    seller1, _ = await make_agent()
    seller2, _ = await make_agent()
    await make_listing(seller1.id, price_usdc=2.00)
    await make_listing(seller2.id, price_usdc=3.00)

    graph = {
        "nodes": {
            "n1": {"type": "agent_call", "config": {"agent_id": seller1.id}},
            "n2": {"type": "agent_call", "config": {"agent_id": seller2.id}},
        },
    }
    ct = await _create_chain_template(db, seller1.id, graph=graph)
    await db.commit()

    result = await svc.estimate_chain_cost(db, ct.id)

    assert result["estimated_total_usd"] == 5.00
    assert len(result["agent_costs"]) == 2


async def test_estimate_chain_cost_skips_non_agent_nodes(db: AsyncSession, make_agent):
    """estimate_chain_cost ignores nodes with type != 'agent_call'."""
    agent, _ = await make_agent()
    graph = {
        "nodes": {
            "t1": {"type": "transform", "config": {}},
            "m1": {"type": "merge", "config": {}},
        },
    }
    ct = await _create_chain_template(db, agent.id, graph=graph)
    await db.commit()

    result = await svc.estimate_chain_cost(db, ct.id)

    assert result["estimated_total_usd"] == 0
    assert result["agent_costs"] == []


async def test_estimate_chain_cost_historical_avg(db: AsyncSession, make_agent):
    """estimate_chain_cost returns historical average from past executions."""
    agent, _ = await make_agent()
    graph = {"nodes": {}}
    wf = await _create_workflow(db, agent.id)
    ct = await _create_chain_template(db, agent.id, graph=graph, workflow_id=wf.id)
    we = await _create_workflow_execution(db, wf.id, agent.id)

    # Create completed executions with known costs
    await _create_chain_execution(
        db, ct.id, agent.id, workflow_execution_id=we.id, total_cost_usd=10.0,
    )
    we2 = await _create_workflow_execution(db, wf.id, agent.id)
    await _create_chain_execution(
        db, ct.id, agent.id, workflow_execution_id=we2.id, total_cost_usd=20.0,
    )
    await db.commit()

    result = await svc.estimate_chain_cost(db, ct.id)

    assert result["historical_avg_usd"] == 15.0  # (10 + 20) / 2


async def test_estimate_chain_cost_no_history(db: AsyncSession, make_agent):
    """estimate_chain_cost returns None for historical_avg when no past executions."""
    agent, _ = await make_agent()
    ct = await _create_chain_template(db, agent.id, graph={"nodes": {}})
    await db.commit()

    result = await svc.estimate_chain_cost(db, ct.id)

    assert result["historical_avg_usd"] is None


# ---------------------------------------------------------------------------
# get_settlement_report
# ---------------------------------------------------------------------------


async def test_settlement_report_not_found(db: AsyncSession):
    """get_settlement_report raises ValueError for non-existent execution."""
    with pytest.raises(ValueError, match="Chain execution not found"):
        await svc.get_settlement_report(db, "nonexistent-id")


async def test_settlement_report_empty(db: AsyncSession, make_agent):
    """get_settlement_report returns empty payments when no ledger entries exist."""
    agent, _ = await make_agent()
    wf = await _create_workflow(db, agent.id)
    we = await _create_workflow_execution(db, wf.id, agent.id)
    ct = await _create_chain_template(db, agent.id, workflow_id=wf.id)
    ce = await _create_chain_execution(db, ct.id, agent.id, workflow_execution_id=we.id)
    await db.commit()

    report = await svc.get_settlement_report(db, ce.id)

    assert report["chain_execution_id"] == ce.id
    assert report["execution_status"] == "completed"
    assert report["total_paid_usd"] == 0
    assert report["total_fees_usd"] == 0
    assert report["payments"] == []


async def test_settlement_report_with_ledger_entries(db: AsyncSession, make_agent):
    """get_settlement_report aggregates ledger entries for the execution."""
    agent, _ = await make_agent()
    wf = await _create_workflow(db, agent.id)
    we = await _create_workflow_execution(db, wf.id, agent.id)
    ct = await _create_chain_template(db, agent.id, workflow_id=wf.id)
    ce = await _create_chain_execution(db, ct.id, agent.id, workflow_execution_id=we.id)

    # Insert ledger entries manually
    ledger1 = TokenLedger(
        id=_uid(),
        amount=Decimal("5.0"),
        fee_amount=Decimal("0.10"),
        tx_type="chain_settlement",
        reference_id=ce.id,
        memo="Node A",
        idempotency_key=f"chn-{ce.id[:16]}-aaa",
    )
    ledger2 = TokenLedger(
        id=_uid(),
        amount=Decimal("3.0"),
        fee_amount=Decimal("0.06"),
        tx_type="chain_settlement",
        reference_id=ce.id,
        memo="Node B",
        idempotency_key=f"chn-{ce.id[:16]}-bbb",
    )
    db.add(ledger1)
    db.add(ledger2)
    await db.commit()

    report = await svc.get_settlement_report(db, ce.id)

    assert report["total_paid_usd"] == 8.0
    assert report["total_fees_usd"] == pytest.approx(0.16, abs=0.001)
    assert len(report["payments"]) == 2
