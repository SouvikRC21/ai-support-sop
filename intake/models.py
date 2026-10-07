"""Data shapes shared by every step of the SOP 1 pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


class Channel(str, Enum):
    EMAIL = "email"
    CHAT = "chat"
    WEB_FORM = "web_form"
    IN_APP = "in_app"
    PHONE = "phone"
    SOCIAL = "social"


class CustomerTier(str, Enum):
    ENTERPRISE = "Enterprise"
    MID_MARKET = "Mid-market"
    SMB = "SMB"
    CONSUMER = "Consumer"


class Severity(str, Enum):
    SEV1 = "Sev1"
    SEV2 = "Sev2"
    SEV3 = "Sev3"
    SEV4 = "Sev4"


ProductLine = Literal["Payments", "Subscriptions", "Unknown"]
Product = Literal[
    "UPI", "UPI QR", "Netbanking", "Credit card", "Debit card",
    "Pro 1 month", "Max 6 months", "Grand 1 year", "Unknown",
]
Sentiment = Literal["positive", "neutral", "negative", "angry"]

# Intents the L0 AI agent may answer on its own (the repeated ~40% of volume).
BOT_ELIGIBLE_INTENTS = frozenset({
    "payment_status",
    "payment_pending_or_failed",
    "refund_status",
    "how_to",
    "invoice_request",
    "plan_change",
    "renewal_date",
    "cancel_subscription",
    "update_payment_method",
})

# Intents that must never be handled by the bot (SOP 1, rule R2).
NEVER_BOT_INTENTS = frozenset({
    "fraud_report",
    "chargeback",
    "dispute",
    "regulatory_complaint",
    "legal_notice",
})

ALL_INTENTS = sorted(BOT_ELIGIBLE_INTENTS | NEVER_BOT_INTENTS | {
    "duplicate_charge",
    "outage_report",
    "account_access",
    "technical_issue",
    "feedback",
    "other",
})


@dataclass
class Ticket:
    """Step 1. A ticket as created from any channel."""

    id: str
    channel: Channel
    subject: str
    body: str
    customer_id: str
    created_at: datetime
    language_hint: Optional[str] = None
    attachments: list[str] = field(default_factory=list)


@dataclass
class Enrichment:
    """Step 2. Context attached from CRM, billing and the payments ledger."""

    tier: CustomerTier
    health_score: int  # 0-100; below 40 is "red"
    open_tickets_7d: int
    contacts_7d: int  # contacts on any channel in the last 7 days, this one included
    last_txn_status: Optional[str] = None  # e.g. "SUCCESS", "PENDING", "FAILED", "REVERSED"
    last_txn_id: Optional[str] = None
    active_incident_id: Optional[str] = None  # open incident matching this customer's product

    @property
    def health_red(self) -> bool:
        return self.health_score < 40


class Classification(BaseModel):
    """Step 3. What the classifier returns. Also used as the structured-output schema."""

    product_line: ProductLine
    product: Product
    intent: str = Field(description=f"One of: {', '.join(ALL_INTENTS)}")
    sentiment: Sentiment
    language: str = Field(description="ISO 639-1 code of the customer's message, e.g. en, hi, ta")
    confidence: float = Field(ge=0.0, le=1.0, description="Your confidence in product_line, product and intent together")
    affected_customers_hint: Literal["one", "many", "unknown"] = Field(
        description="Does the message suggest many customers are affected (an outage)?"
    )
    money_blocked: bool = Field(description="Is the customer's money or access blocked right now?")
    workaround_exists: bool
    summary: str = Field(description="One-sentence neutral summary for the agent")

    @property
    def bot_eligible(self) -> bool:
        return self.intent in BOT_ELIGIBLE_INTENTS


class Queue(str, Enum):
    INCIDENT = "Incident"
    L2_PAYMENTS_DISPUTES = "L2 Payments Disputes"
    L1_PRIORITY = "L1 Priority"
    L0_AI_AGENT = "L0 AI Agent"
    L1_PAYMENTS = "L1 Payments"
    L1_BILLING = "L1 Billing"
    TRIAGE = "Triage"


@dataclass
class RoutingDecision:
    """Step 5. Where the ticket went and which rule sent it there."""

    rule: str
    queue: Queue
    skill: Optional[str] = None
    flags: list[str] = field(default_factory=list)
    page_l3: bool = False


@dataclass
class SlaTimers:
    """Step 6. Deadlines started at creation time."""

    first_response_due: datetime
    resolution_due: datetime
    resolution_kind: str  # "workaround" for Sev1, "resolution" otherwise
    triage_due: Optional[datetime] = None  # only when the ticket is in the Triage queue


@dataclass
class Acknowledgement:
    """Step 7. The auto-acknowledgement sent to the customer."""

    ticket_id: str
    expected_first_response: datetime
    text: str
    ai_first_answer: Optional[str] = None
