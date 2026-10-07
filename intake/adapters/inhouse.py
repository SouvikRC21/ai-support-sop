"""In-house ticketing adapter (Model A).

Assumes the in-house platform exposes a REST endpoint to patch a ticket and
post a public reply. Rename the paths and fields to match your API. SLA clocks
are written as absolute due times so the platform's SLA job can alert on them.
"""

from __future__ import annotations

import httpx

from ..pipeline import IntakeResult


class InHouseAdapter:
    def __init__(self, base_url: str, api_key: str, http: httpx.Client | None = None):
        self.http = http or httpx.Client(
            base_url=base_url, headers={"Authorization": f"Bearer {api_key}"}, timeout=15
        )

    def build_patch(self, r: IntakeResult) -> dict:
        c = r.classification
        return {
            "queue": r.routing.queue.value,
            "skill": r.routing.skill,
            "severity": r.severity.value,
            "routing_rule": r.routing.rule,
            "page_l3": r.routing.page_l3,
            "classification": c.model_dump(),
            "classification_locked": r.locked,
            "enrichment": {
                "tier": r.enrichment.tier.value,
                "health_score": r.enrichment.health_score,
                "open_tickets_7d": r.enrichment.open_tickets_7d,
                "last_txn_status": r.enrichment.last_txn_status,
            },
            "sla": {
                "first_response_due": r.timers.first_response_due.isoformat(),
                "resolution_due": r.timers.resolution_due.isoformat(),
                "resolution_kind": r.timers.resolution_kind,
                "triage_due": r.timers.triage_due.isoformat() if r.timers.triage_due else None,
            },
            "tags": r.tags(),
        }

    def apply(self, r: IntakeResult) -> None:
        self.http.patch(f"/tickets/{r.ticket.id}", json=self.build_patch(r)).raise_for_status()
        self.http.post(
            f"/tickets/{r.ticket.id}/replies", json={"body": r.ack.text, "public": True}
        ).raise_for_status()
