"""Zendesk adapter (Model B).

Flow: a Zendesk trigger ("Ticket is Created") calls a webhook pointing at
intake.webhook. The webhook runs the pipeline and this adapter writes the
result back with one ticket update: group, priority, tags, custom fields and
the public auto-acknowledgement.

Zendesk's own SLA policies own the clocks. Point them at the sev_* tags this
adapter sets so the timers here and in Zendesk agree; the due times are also
written to custom fields for reporting.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

import httpx

from ..models import Queue, Severity
from ..pipeline import IntakeResult

PRIORITY = {
    Severity.SEV1: "urgent",
    Severity.SEV2: "high",
    Severity.SEV3: "normal",
    Severity.SEV4: "low",
}


@dataclass
class ZendeskConfig:
    subdomain: str
    email: str
    api_token: str
    group_ids: dict[Queue, int]
    # Custom field ids from Admin Center > Objects and rules > Tickets > Fields.
    field_ids: dict[str, int] = field(default_factory=dict)

    @classmethod
    def from_env(cls, group_ids: dict[Queue, int], field_ids: dict[str, int]) -> "ZendeskConfig":
        return cls(
            subdomain=os.environ["ZENDESK_SUBDOMAIN"],
            email=os.environ["ZENDESK_EMAIL"],
            api_token=os.environ["ZENDESK_API_TOKEN"],
            group_ids=group_ids,
            field_ids=field_ids,
        )


class ZendeskAdapter:
    def __init__(self, config: ZendeskConfig, http: httpx.Client | None = None):
        self.config = config
        self.http = http or httpx.Client(
            base_url=f"https://{config.subdomain}.zendesk.com",
            auth=(f"{config.email}/token", config.api_token),
            timeout=15,
        )

    def build_update(self, r: IntakeResult) -> dict:
        c = r.classification
        values = {
            "product_line": c.product_line,
            "product": c.product,
            "intent": c.intent,
            "sentiment": c.sentiment,
            "language": c.language,
            "ai_confidence": f"{c.confidence:.2f}",
            "severity": r.severity.value,
            "routing_rule": r.routing.rule,
            "skill": r.routing.skill or "",
            "first_response_due": r.timers.first_response_due.isoformat(),
            "resolution_due": r.timers.resolution_due.isoformat(),
            "triage_due": r.timers.triage_due.isoformat() if r.timers.triage_due else "",
        }
        ticket = {
            "group_id": self.config.group_ids[r.routing.queue],
            "priority": PRIORITY[r.severity],
            "additional_tags": r.tags(),
            "custom_fields": [
                {"id": fid, "value": values[name]} for name, fid in self.config.field_ids.items() if name in values
            ],
            "comment": {"body": r.ack.text, "public": True},
        }
        return {"ticket": ticket}

    def apply(self, r: IntakeResult) -> None:
        resp = self.http.put(f"/api/v2/tickets/{r.ticket.id}.json", json=self.build_update(r))
        resp.raise_for_status()
