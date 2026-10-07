from datetime import timedelta

import pytest

from intake.models import Queue, Severity
from tests.conftest import NOW, make_ticket


def test_bot_eligible_upi_goes_to_ai_agent_with_first_answer(pipeline):
    r = pipeline.process(make_ticket("UPI payment pending", "Money deducted via UPI but order not confirmed", "pending"))
    assert r.locked
    assert r.classification.product == "UPI"
    assert r.severity == Severity.SEV2
    assert (r.routing.rule, r.routing.queue) == ("R4", Queue.L0_AI_AGENT)
    assert r.timers.first_response_due == NOW + timedelta(hours=2)
    assert "T1" in r.ack.text and "2 hours" in r.ack.text
    assert "T+1 working day" in r.ack.ai_first_answer


def test_incident_wins_over_everything(pipeline):
    r = pipeline.process(make_ticket("UPI fraud on my account", "", "incident"))
    assert (r.routing.rule, r.routing.queue, r.routing.page_l3) == ("R1", Queue.INCIDENT, True)
    assert r.severity == Severity.SEV1
    assert r.timers.resolution_due == NOW + timedelta(hours=4)
    assert r.timers.resolution_kind == "workaround"
    assert r.ack.ai_first_answer is None


@pytest.mark.parametrize("text", ["Unauthorised UPI debit, this is fraud", "I will raise a chargeback on my credit card"])
def test_sensitive_goes_to_disputes_never_bot(pipeline, text):
    r = pipeline.process(make_ticket(text))
    assert (r.routing.rule, r.routing.queue) == ("R2", Queue.L2_PAYMENTS_DISPUTES)
    assert "never_bot" in r.routing.flags
    assert r.ack.ai_first_answer is None


def test_sensitive_rule_applies_even_when_confidence_is_low(pipeline):
    r = pipeline.process(make_ticket("hello", "please check, I am going to the RBI ombudsman"))
    assert not r.locked
    assert r.routing.queue == Queue.L2_PAYMENTS_DISPUTES


def test_enterprise_goes_to_priority_with_enterprise_sla(pipeline):
    r = pipeline.process(make_ticket("Need invoice for Grand annual plan", "", "enterprise"))
    assert (r.routing.rule, r.routing.queue) == ("R3", Queue.L1_PRIORITY)
    assert r.severity == Severity.SEV4
    assert r.timers.first_response_due == NOW + timedelta(hours=8)
    # Bot-eligible intent still gets the AI's first answer, with a specialist following up.
    assert r.ack.ai_first_answer and "specialist is also reviewing" in r.ack.text


def test_red_health_goes_to_priority(pipeline):
    r = pipeline.process(make_ticket("Netbanking payment failed", "", "red"))
    assert (r.routing.rule, r.routing.queue) == ("R3", Queue.L1_PRIORITY)
    assert "health_red" in r.routing.flags


def test_payments_non_bot_intent_goes_to_l1_payments_with_skill(pipeline):
    r = pipeline.process(make_ticket("Charged twice on my debit card"))
    assert (r.routing.rule, r.routing.queue, r.routing.skill) == ("R5", Queue.L1_PAYMENTS, "debit_card")


def test_subscription_access_issue_goes_to_billing(pipeline):
    r = pipeline.process(make_ticket("Can't login to my Max 6 month plan"))
    assert (r.routing.rule, r.routing.queue, r.routing.skill) == ("R6", Queue.L1_BILLING, "max_6_months")


def test_repeat_contact_is_flagged(pipeline):
    r = pipeline.process(make_ticket("Charged twice on my credit card", "", "repeat"))
    assert "repeat_contact" in r.routing.flags


def test_low_confidence_goes_to_triage_with_15_minute_timer(pipeline):
    r = pipeline.process(make_ticket("Hi", "Something is wrong, please help"))
    assert not r.locked
    assert (r.routing.rule, r.routing.queue) == ("R8", Queue.TRIAGE)
    assert r.timers.triage_due == NOW + timedelta(minutes=15)
    assert "ai_needs_triage" in r.tags()
    assert r.ack.ai_first_answer is None


def test_kb_article_scoped_to_product_is_not_used_for_other_products():
    from intake.answer import Article, StaticKnowledgeBase

    kb = StaticKnowledgeBase({"payment_pending_or_failed": [Article("A", "UPI", "upi only", products=("UPI",))]})
    assert kb.search("", "Credit card", "payment_pending_or_failed") == []
    assert kb.search("", "UPI", "payment_pending_or_failed")[0].id == "A"
