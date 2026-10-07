"""Policy Guard: deterministic rules every proposed action must pass before it can run.

The resolver (an LLM) only *proposes*. This module decides. It is plain code so it is
auditable, cannot be persuaded by ticket text, and can be unit-tested exhaustively.
"""
from __future__ import annotations

import os
from datetime import date

from .schemas import PolicyDecision

ALLOWED_ACTIONS = {"refund", "cancel_order", "password_reset"}
REFUND_WINDOW_DAYS = 30
AUTO_REFUND_LIMIT = 100.00   # above this a human must approve
# Fixed "today" so sample data and evals are reproducible. Override with SUPPORTDESK_TODAY.
TODAY = date.fromisoformat(os.getenv("SUPPORTDESK_TODAY", "2026-10-07"))


def _deny(code: str, message: str) -> PolicyDecision:
    return PolicyDecision(allowed=False, reasons=[{"code": code, "message": message}])


def _owned_order(store, order_id, customer_id):
    order = store.orders.get(order_id)
    if order is None:
        return None, _deny("order_not_found", "that order doesn't exist")
    if order["customer_id"] != customer_id:
        return None, _deny("ownership_mismatch", "that order isn't on this account")
    return order, None


def evaluate(action: dict | None, customer_id: str, store, today: date = TODAY) -> PolicyDecision:
    if action is None:
        return PolicyDecision(allowed=True)
    kind = action.get("type")
    params = action.get("params") or {}
    if kind not in ALLOWED_ACTIONS:
        return _deny("action_not_allowed", f"the action {kind!r} isn't something support can do")

    if kind == "refund":
        order, err = _owned_order(store, params.get("order_id"), customer_id)
        if err:
            return err
        if order["status"] != "delivered" or not order.get("delivered_on"):
            return _deny("not_delivered", "it hasn't been delivered yet")
        age = (today - date.fromisoformat(order["delivered_on"])).days
        if age > REFUND_WINDOW_DAYS:
            return _deny("outside_refund_window",
                         f"it was delivered more than {REFUND_WINDOW_DAYS} days ago")
        refundable = round(order["total"] - order["refunded"], 2)
        if refundable <= 0:
            return _deny("already_refunded", "it has already been fully refunded")
        try:
            amount = float(params.get("amount"))
        except (TypeError, ValueError):
            return _deny("invalid_amount", "the refund amount is missing")
        if amount <= 0 or amount > refundable + 1e-9:
            return _deny("amount_exceeds_refundable",
                         f"the amount must be between 0 and the refundable {refundable:.2f}")
        if amount > AUTO_REFUND_LIMIT:
            return PolicyDecision(allowed=True, requires_approval=True, reasons=[
                {"code": "over_auto_limit", "message": f"refunds over {AUTO_REFUND_LIMIT:.0f} need review"}])
        return PolicyDecision(allowed=True)

    if kind == "cancel_order":
        order, err = _owned_order(store, params.get("order_id"), customer_id)
        if err:
            return err
        if order["status"] != "processing":
            return _deny("already_shipped" if order["status"] in ("shipped", "delivered") else "not_cancellable",
                         "it has already shipped" if order["status"] in ("shipped", "delivered")
                         else f"it is {order['status']}")
        return PolicyDecision(allowed=True)

    # password_reset: only ever for the account that opened the ticket
    if params.get("customer_id") != customer_id:
        return _deny("ownership_mismatch", "password resets can only go to the ticket's own account")
    return PolicyDecision(allowed=True)
