from datetime import datetime, timezone

import pytest

from intake.answer import Article, StaticKnowledgeBase, TemplateAnswerer
from intake.enrich import InMemoryEnrichment
from intake.models import Channel, Ticket
from intake.pipeline import IntakePipeline

# Wednesday 10:00 UTC, so business-day maths is easy to check.
NOW = datetime(2026, 10, 7, 10, 0, tzinfo=timezone.utc)

CUSTOMERS = {
    "consumer": {"tier": "Consumer", "health_score": 80},
    "enterprise": {"tier": "Enterprise", "health_score": 75},
    "red": {"tier": "SMB", "health_score": 25},
    "repeat": {"tier": "Consumer", "health_score": 70, "contacts_7d": 3},
    "incident": {"tier": "Consumer", "health_score": 70, "active_incident_id": "INC-42"},
    "pending": {"tier": "Consumer", "health_score": 70, "last_txn_status": "PENDING", "last_txn_id": "TXN9"},
}

KB = StaticKnowledgeBase({
    "payment_pending_or_failed": [Article("KB1", "UPI pending", "Pending UPI debits auto-reverse within T+1 working day.")],
    "invoice_request": [Article("KB2", "Invoices", "Download invoices from Settings > Billing > Invoices.")],
})


def make_ticket(subject, body="", customer="consumer", tid="T1"):
    return Ticket(id=tid, channel=Channel.EMAIL, subject=subject, body=body, customer_id=customer, created_at=NOW)


@pytest.fixture
def pipeline():
    return IntakePipeline(InMemoryEnrichment(CUSTOMERS), answerer=TemplateAnswerer(KB))
