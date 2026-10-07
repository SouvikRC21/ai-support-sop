"""Step 4. Set severity from the SOP 1 matrix.

Sev1  outage, or money at risk for many customers
Sev2  one customer's money or access blocked
Sev3  impaired, a workaround exists
Sev4  a question
"""

from __future__ import annotations

from .models import NEVER_BOT_INTENTS, Classification, Enrichment, Severity

QUESTION_INTENTS = frozenset({"how_to", "invoice_request", "renewal_date", "payment_status", "feedback", "other"})


def set_severity(c: Classification, e: Enrichment) -> Severity:
    if e.active_incident_id or c.affected_customers_hint == "many" or c.intent == "outage_report":
        return Severity.SEV1
    if c.money_blocked or c.intent in NEVER_BOT_INTENTS:
        return Severity.SEV2
    if c.intent in QUESTION_INTENTS and not c.money_blocked:
        return Severity.SEV4
    return Severity.SEV3
