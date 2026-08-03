"""Billing's HTTP adapter.

Seven routes, including the gateway webhook. That route is a transport in front of
``PaymentWebhookHandler`` and adds nothing to it — the signature check, its ordering and its
silence about what went wrong all stay where CLAUDE.md section 4 put them.
"""

from billing.adapters.inbound.http.errors import EXCEPTION_STATUSES
from billing.adapters.inbound.http.router import STATE_KEY, BillingDependencies, router

__all__ = [
    "EXCEPTION_STATUSES",
    "STATE_KEY",
    "BillingDependencies",
    "router",
]
