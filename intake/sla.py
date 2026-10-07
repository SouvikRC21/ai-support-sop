"""Step 6. Start SLA timers by severity and customer tier.

| Severity | First response (Enterprise / others) | Resolution            |
| Sev1     | 15 min / 30 min                      | workaround in 4 h     |
| Sev2     | 1 h / 2 h                            | 24 h                  |
| Sev3     | 4 h / 8 h                            | 3 business days       |
| Sev4     | 8 h / 24 h                           | 5 business days       |

Triage tickets also get a 15-minute triage deadline.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from .models import CustomerTier, Queue, RoutingDecision, Severity, SlaTimers

FIRST_RESPONSE = {
    Severity.SEV1: (timedelta(minutes=15), timedelta(minutes=30)),
    Severity.SEV2: (timedelta(hours=1), timedelta(hours=2)),
    Severity.SEV3: (timedelta(hours=4), timedelta(hours=8)),
    Severity.SEV4: (timedelta(hours=8), timedelta(hours=24)),
}

TRIAGE_WINDOW = timedelta(minutes=15)


def add_business_days(start: datetime, days: int) -> datetime:
    """Add working days (Mon to Fri). Plug in a holiday calendar here if needed."""
    current = start
    while days > 0:
        current += timedelta(days=1)
        if current.weekday() < 5:
            days -= 1
    return current


def start_timers(
    created_at: datetime, severity: Severity, tier: CustomerTier, routing: RoutingDecision
) -> SlaTimers:
    enterprise, others = FIRST_RESPONSE[severity]
    first_response = created_at + (enterprise if tier == CustomerTier.ENTERPRISE else others)

    if severity == Severity.SEV1:
        resolution, kind = created_at + timedelta(hours=4), "workaround"
    elif severity == Severity.SEV2:
        resolution, kind = created_at + timedelta(hours=24), "resolution"
    elif severity == Severity.SEV3:
        resolution, kind = add_business_days(created_at, 3), "resolution"
    else:
        resolution, kind = add_business_days(created_at, 5), "resolution"

    triage_due = created_at + TRIAGE_WINDOW if routing.queue == Queue.TRIAGE else None
    return SlaTimers(first_response, resolution, kind, triage_due)


def overdue_triage(timers_by_ticket: dict[str, SlaTimers], now: datetime) -> list[str]:
    """Ticket ids whose 15-minute triage window has passed. Run this every minute and alert the lead."""
    return [tid for tid, t in timers_by_ticket.items() if t.triage_due and now > t.triage_due]
