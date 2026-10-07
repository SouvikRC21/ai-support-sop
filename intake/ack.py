"""Step 7. Auto-acknowledge with ticket ID, expected response time and, for
bot-eligible intents, the AI agent's first answer."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from .models import Acknowledgement, Queue, RoutingDecision, SlaTimers


def _humanise(delta_seconds: float) -> str:
    minutes = max(1, round(delta_seconds / 60))
    if minutes < 60:
        return f"{minutes} minutes"
    hours = round(minutes / 60)
    return "1 hour" if hours == 1 else f"{hours} hours"


def build_ack(
    ticket_id: str,
    created_at: datetime,
    routing: RoutingDecision,
    timers: SlaTimers,
    ai_answer: Optional[str] = None,
) -> Acknowledgement:
    wait = _humanise((timers.first_response_due - created_at).total_seconds())
    lines = [f"Thanks for contacting us. Your ticket ID is {ticket_id}."]

    if ai_answer:
        lines += ["", "Here is what we can tell you right away:", ai_answer, ""]
        if routing.queue == Queue.L0_AI_AGENT:
            lines.append(
                "If this solves it, no need to reply. If not, just reply to this message "
                f"and a specialist will pick it up within {wait}."
            )
        else:
            lines.append(f"A specialist is also reviewing your ticket and will reply within {wait}.")
    elif routing.queue == Queue.INCIDENT:
        lines.append(
            "We are aware of an issue that may be affecting you and our engineers are working on it. "
            f"We will update you within {wait}."
        )
    else:
        lines.append(f"A specialist will reply within {wait}.")

    return Acknowledgement(
        ticket_id=ticket_id,
        expected_first_response=timers.first_response_due,
        text="\n".join(lines),
        ai_first_answer=ai_answer,
    )
