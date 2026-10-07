"""Step 5. Route. Rules are evaluated top to bottom and the first match wins.

R1  Sev1 or linked to an incident     -> Incident queue, page L3
R2  regulatory / legal / fraud / chargeback -> L2 Payments Disputes (never the bot)
R3  Enterprise or red health          -> L1 Priority
R4  bot-eligible intent, confidence >= 0.85 -> L0 AI agent
R5  Payments                          -> L1 Payments, skill by product
R6  Subscriptions                     -> L1 Billing, skill by plan
R7  3rd contact in 7 days             -> L1 Priority + repeat flag
R8  no match                          -> Triage

A classification below the 0.85 lock is not trusted for R3 to R7, so those
tickets go to Triage (15-minute human review). R1 and R2 still apply because
they are safety rules: R1 uses enrichment, and R2 also checks the raw text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Optional

from .classifier import CONFIDENCE_LOCK
from .models import (
    NEVER_BOT_INTENTS,
    Classification,
    CustomerTier,
    Enrichment,
    Queue,
    RoutingDecision,
    Severity,
    Ticket,
)

_SENSITIVE_TEXT = re.compile(
    r"\b(fraud|scam|unauthori[sz]ed|charge\s*back|rbi|npci|ombudsman|legal notice|lawyer|court|consumer forum)\b",
    re.IGNORECASE,
)


@dataclass
class Context:
    ticket: Ticket
    enrichment: Enrichment
    classification: Classification
    severity: Severity

    @property
    def locked(self) -> bool:
        return self.classification.confidence >= CONFIDENCE_LOCK


Rule = Callable[[Context], Optional[RoutingDecision]]


def r1_incident(ctx: Context) -> Optional[RoutingDecision]:
    if ctx.severity == Severity.SEV1 or ctx.enrichment.active_incident_id:
        flags = [f"incident:{ctx.enrichment.active_incident_id}"] if ctx.enrichment.active_incident_id else []
        return RoutingDecision("R1", Queue.INCIDENT, flags=flags, page_l3=True)
    return None


def r2_sensitive(ctx: Context) -> Optional[RoutingDecision]:
    text = f"{ctx.ticket.subject} {ctx.ticket.body}"
    if ctx.classification.intent in NEVER_BOT_INTENTS or _SENSITIVE_TEXT.search(text):
        return RoutingDecision("R2", Queue.L2_PAYMENTS_DISPUTES, skill="disputes", flags=["never_bot"])
    return None


def r3_priority_account(ctx: Context) -> Optional[RoutingDecision]:
    if ctx.locked and (ctx.enrichment.tier == CustomerTier.ENTERPRISE or ctx.enrichment.health_red):
        reason = "enterprise" if ctx.enrichment.tier == CustomerTier.ENTERPRISE else "health_red"
        return RoutingDecision("R3", Queue.L1_PRIORITY, skill=_skill(ctx), flags=[reason])
    return None


def r4_bot(ctx: Context) -> Optional[RoutingDecision]:
    if ctx.locked and ctx.classification.bot_eligible:
        return RoutingDecision("R4", Queue.L0_AI_AGENT, skill=ctx.classification.intent)
    return None


def r5_payments(ctx: Context) -> Optional[RoutingDecision]:
    if ctx.locked and ctx.classification.product_line == "Payments":
        return RoutingDecision("R5", Queue.L1_PAYMENTS, skill=_skill(ctx))
    return None


def r6_subscriptions(ctx: Context) -> Optional[RoutingDecision]:
    if ctx.locked and ctx.classification.product_line == "Subscriptions":
        return RoutingDecision("R6", Queue.L1_BILLING, skill=_skill(ctx))
    return None


def r7_repeat_contact(ctx: Context) -> Optional[RoutingDecision]:
    if ctx.locked and ctx.enrichment.contacts_7d >= 3:
        return RoutingDecision("R7", Queue.L1_PRIORITY, skill=_skill(ctx), flags=["repeat_contact"])
    return None


def r8_triage(ctx: Context) -> RoutingDecision:
    flags = [] if ctx.locked else [f"low_confidence:{ctx.classification.confidence:.2f}"]
    return RoutingDecision("R8", Queue.TRIAGE, flags=flags)


RULES: list[Rule] = [
    r1_incident,
    r2_sensitive,
    r3_priority_account,
    r4_bot,
    r5_payments,
    r6_subscriptions,
    r7_repeat_contact,
]


def route(ctx: Context) -> RoutingDecision:
    for rule in RULES:
        decision = rule(ctx)
        if decision:
            # A repeat contact is always flagged, whichever rule won.
            if ctx.enrichment.contacts_7d >= 3 and "repeat_contact" not in decision.flags:
                decision.flags.append("repeat_contact")
            return decision
    return r8_triage(ctx)


def _skill(ctx: Context) -> Optional[str]:
    product = ctx.classification.product
    return None if product == "Unknown" else product.lower().replace(" ", "_")
