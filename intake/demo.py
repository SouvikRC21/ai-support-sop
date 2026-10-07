"""Run sample tickets through the SOP 1 pipeline and print what happens.

    python -m intake.demo            # keyword classifier, no API key needed
    python -m intake.demo --claude   # Claude classifier + AI first answer (needs ANTHROPIC_API_KEY)
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone

from .answer import Article, ClaudeAnswerer, StaticKnowledgeBase, TemplateAnswerer
from .classifier import ClaudeClassifier
from .enrich import InMemoryEnrichment
from .models import Channel, Ticket
from .pipeline import IntakePipeline

CUSTOMERS = {
    "c1": {"tier": "Consumer", "health_score": 80, "last_txn_status": "PENDING", "last_txn_id": "UPI8812"},
    "c2": {"tier": "Enterprise", "health_score": 72},
    "c3": {"tier": "SMB", "health_score": 30},
    "c4": {"tier": "Consumer", "health_score": 65, "contacts_7d": 3},
    "c5": {"tier": "Consumer", "health_score": 70, "active_incident_id": "INC-2207"},
}

KB = StaticKnowledgeBase({
    "payment_pending_or_failed": [Article(
        "KB-UPI-01", "UPI debit pending",
        "If money was debited but the payment shows pending, it is auto-reversed to your bank "
        "account within T+1 working day. You do not need to pay again.",
        products=("UPI", "UPI QR"),
    )],
    "cancel_subscription": [Article(
        "KB-SUB-04", "Cancel a plan",
        "Go to Settings > Subscription > Cancel plan. You keep access until the end of the current period.",
    )],
    "invoice_request": [Article("KB-BIL-02", "Invoices", "Download any invoice from Settings > Billing > Invoices.")],
})

SAMPLES = [
    ("1001", "c1", "UPI payment stuck", "Money deducted from my account via UPI but app shows pending"),
    ("1002", "c2", "Invoice needed", "Please share the invoice for our Grand 1 year renewal"),
    ("1003", "c3", "Card payment failed", "My credit card payment keeps failing at checkout"),
    ("1004", "c1", "Unauthorised debit", "There is a UPI debit I didn't make. This is fraud!!"),
    ("1005", "c4", "Charged twice", "I was charged twice on my debit card, third time I'm writing"),
    ("1006", "c5", "Payments down", "Netbanking is not working for anyone in our team"),
    ("1007", "c1", "Cancel my Pro monthly plan", "How do I cancel? Don't want it to renew"),
    ("1008", "c1", "Hi", "something is wrong pls check"),
]


def main() -> None:
    use_claude = "--claude" in sys.argv
    if use_claude:
        pipeline = IntakePipeline(InMemoryEnrichment(CUSTOMERS), ClaudeClassifier(), ClaudeAnswerer(KB))
    else:
        pipeline = IntakePipeline(InMemoryEnrichment(CUSTOMERS), answerer=TemplateAnswerer(KB))

    now = datetime.now(timezone.utc)
    for tid, cust, subject, body in SAMPLES:
        r = pipeline.process(Ticket(tid, Channel.EMAIL, subject, body, cust, now))
        c = r.classification
        print(f"#{tid} {subject!r}")
        print(f"  {c.product_line}/{c.product} intent={c.intent} sentiment={c.sentiment} "
              f"confidence={c.confidence:.2f} {'LOCKED' if r.locked else 'TRIAGE'}")
        print(f"  {r.severity.value} -> {r.routing.rule} {r.routing.queue.value}"
              f"{' skill=' + r.routing.skill if r.routing.skill else ''}"
              f"{' flags=' + ','.join(r.routing.flags) if r.routing.flags else ''}"
              f"{' PAGE L3' if r.routing.page_l3 else ''}")
        print(f"  first response by {r.timers.first_response_due:%H:%M}, "
              f"{r.timers.resolution_kind} by {r.timers.resolution_due:%a %d %b %H:%M}"
              f"{f', triage by {r.timers.triage_due:%H:%M}' if r.timers.triage_due else ''}")
        print("  ack: " + r.ack.text.replace("\n", "\n       "))
        print()


if __name__ == "__main__":
    main()
