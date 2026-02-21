"""Analytics plugin -- tracks marketplace transaction metrics.

Provides an ``AnalyticsPlugin`` class that records transaction events
and exposes aggregate statistics.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)


class AnalyticsPlugin:
    """Tracks marketplace transactions and exposes summary analytics.

    Implements the standard plugin hook interface:
    - ``on_register()`` -- called when the plugin is added to the registry
    - ``on_transaction_completed(tx)`` -- called after a transaction completes
    - ``get_stats()`` -- returns aggregate statistics
    """

    def __init__(self) -> None:
        self._registered = False
        self._transaction_count: int = 0
        self._total_amount: float = 0.0
        self._event_counts: dict[str, int] = defaultdict(int)
        self._transactions: list[dict] = []

    def on_register(self) -> None:
        """Called when the plugin is registered with the PluginRegistry."""
        self._registered = True
        logger.info("[AnalyticsPlugin] Registered -- tracking marketplace analytics.")

    def on_transaction_completed(self, tx: Any) -> None:
        """Called when a marketplace transaction is completed.

        *tx* may be a dict with keys like ``transaction_id``, ``amount``,
        ``buyer_id``, ``seller_id``, or an object with matching attributes.
        """
        if isinstance(tx, dict):
            tx_id = tx.get("transaction_id", "unknown")
            amount = float(tx.get("amount", 0.0))
            tx_type = tx.get("tx_type", "unknown")
        else:
            tx_id = getattr(tx, "transaction_id", "unknown")
            amount = float(getattr(tx, "amount", 0.0))
            tx_type = getattr(tx, "tx_type", "unknown")

        self._transaction_count += 1
        self._total_amount += amount
        self._event_counts[tx_type] += 1
        self._transactions.append({
            "transaction_id": tx_id,
            "amount": amount,
            "tx_type": tx_type,
        })

        logger.info(
            "[AnalyticsPlugin] Transaction #%d completed: %s (%.2f USD)",
            self._transaction_count,
            tx_id,
            amount,
        )

    def get_stats(self) -> dict:
        """Return aggregate analytics statistics.

        Returns a dict with transaction count, total amount,
        average transaction value, and per-type breakdowns.
        """
        avg = (
            self._total_amount / self._transaction_count
            if self._transaction_count > 0
            else 0.0
        )
        return {
            "registered": self._registered,
            "transaction_count": self._transaction_count,
            "total_amount_usd": round(self._total_amount, 2),
            "average_amount_usd": round(avg, 2),
            "by_type": dict(self._event_counts),
            "recent_transactions": self._transactions[-10:],
        }
