"""ClaudeClassifier against a fake client, so no API key is needed."""

from types import SimpleNamespace

import anthropic
import httpx2

from intake.classifier import ClaudeClassifier
from intake.enrich import InMemoryEnrichment
from intake.models import Classification
from tests.conftest import make_ticket

GOOD = Classification(
    product_line="Subscriptions", product="Pro 1 month", intent="cancel_subscription", sentiment="neutral",
    language="hi", confidence=0.93, affected_customers_hint="one", money_blocked=False,
    workaround_exists=False, summary="Wants to cancel Pro",
)


class FakeClient:
    def __init__(self, response=None, error=None):
        self.calls = []
        self.response, self.error = response, error
        self.beta = SimpleNamespace(messages=SimpleNamespace(parse=self._parse))

    def _parse(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


def _enrich(t):
    return InMemoryEnrichment().enrich(t)


def test_uses_structured_output_and_fallbacks():
    client = FakeClient(SimpleNamespace(stop_reason="end_turn", parsed_output=GOOD))
    t = make_ticket("Pro plan band karna hai")
    assert ClaudeClassifier(client).classify(t, _enrich(t)) == GOOD
    call = client.calls[0]
    assert call["model"] == "claude-opus-5-5"
    assert call["output_format"] is Classification
    assert call["fallbacks"] == "default" and call["betas"] == ["server-side-fallback-2026-07-01"]


def test_refusal_falls_back_to_keywords():
    client = FakeClient(SimpleNamespace(stop_reason="refusal", parsed_output=None))
    t = make_ticket("Cancel my Pro monthly plan")
    c = ClaudeClassifier(client).classify(t, _enrich(t))
    assert c.intent == "cancel_subscription" and c.product == "Pro 1 month"


def test_api_error_falls_back_to_keywords():
    req = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    client = FakeClient(error=anthropic.APIConnectionError(request=req))
    t = make_ticket("Invoice for netbanking payment")
    assert ClaudeClassifier(client).classify(t, _enrich(t)).intent == "invoice_request"
