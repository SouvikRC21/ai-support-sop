"""Step 2. Enrich: attach tier, health, recent contacts and last transaction.

In production each lookup is a call to the CRM, the health-score service, the
ticketing platform and the payments ledger. They are behind one protocol so
the pipeline does not care where the data comes from.
"""

from __future__ import annotations

from typing import Protocol

from .models import CustomerTier, Enrichment, Ticket


class EnrichmentSource(Protocol):
    def enrich(self, ticket: Ticket) -> Enrichment: ...


class InMemoryEnrichment:
    """Reference source backed by dicts. Swap for CRM / ledger clients in production."""

    def __init__(
        self,
        customers: dict[str, dict] | None = None,
        default_tier: CustomerTier = CustomerTier.CONSUMER,
    ):
        self.customers = customers or {}
        self.default_tier = default_tier

    def enrich(self, ticket: Ticket) -> Enrichment:
        c = self.customers.get(ticket.customer_id, {})
        return Enrichment(
            tier=CustomerTier(c.get("tier", self.default_tier)),
            health_score=c.get("health_score", 70),
            open_tickets_7d=c.get("open_tickets_7d", 0),
            contacts_7d=c.get("contacts_7d", 1),
            last_txn_status=c.get("last_txn_status"),
            last_txn_id=c.get("last_txn_id"),
            active_incident_id=c.get("active_incident_id"),
        )
