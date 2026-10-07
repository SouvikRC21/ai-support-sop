"""SOP 1 intake pipeline: create -> enrich -> classify -> severity -> route -> SLA -> acknowledge."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .ack import build_ack
from .answer import Answerer
from .classifier import CONFIDENCE_LOCK, Classifier, KeywordClassifier
from .enrich import EnrichmentSource
from .models import (
    Acknowledgement,
    Classification,
    Enrichment,
    Queue,
    RoutingDecision,
    Severity,
    SlaTimers,
    Ticket,
)
from .routing import Context, route
from .severity import set_severity
from .sla import start_timers


@dataclass
class IntakeResult:
    ticket: Ticket
    enrichment: Enrichment
    classification: Classification
    locked: bool
    severity: Severity
    routing: RoutingDecision
    timers: SlaTimers
    ack: Acknowledgement

    def tags(self) -> list[str]:
        c = self.classification
        tags = [
            f"sev_{self.severity.value.lower()}",
            f"rule_{self.routing.rule.lower()}",
            f"intent_{c.intent}",
            f"sentiment_{c.sentiment}",
            f"lang_{c.language}",
            "ai_locked" if self.locked else "ai_needs_triage",
        ]
        if self.ack.ai_first_answer:
            tags.append("ai_first_answer_sent")
        tags += [f.replace(":", "_") for f in self.routing.flags]
        return tags


class IntakePipeline:
    def __init__(
        self,
        enrichment: EnrichmentSource,
        classifier: Optional[Classifier] = None,
        answerer: Optional[Answerer] = None,
    ):
        self.enrichment = enrichment
        self.classifier = classifier or KeywordClassifier()
        self.answerer = answerer

    def process(self, ticket: Ticket) -> IntakeResult:
        # Step 1 (create) happens in the channel / platform; the ticket arrives here with its ID.
        enrichment = self.enrichment.enrich(ticket)                                # Step 2
        classification = self.classifier.classify(ticket, enrichment)              # Step 3
        locked = classification.confidence >= CONFIDENCE_LOCK
        severity = set_severity(classification, enrichment)                        # Step 4
        routing = route(Context(ticket, enrichment, classification, severity))     # Step 5
        timers = start_timers(ticket.created_at, severity, enrichment.tier, routing)  # Step 6

        ai_answer = None                                                           # Step 7
        if (
            self.answerer
            and locked
            and classification.bot_eligible
            and routing.queue not in (Queue.INCIDENT, Queue.L2_PAYMENTS_DISPUTES)
        ):
            ai_answer = self.answerer.first_answer(ticket, classification, enrichment)
        ack = build_ack(ticket.id, ticket.created_at, routing, timers, ai_answer)

        return IntakeResult(ticket, enrichment, classification, locked, severity, routing, timers, ack)
