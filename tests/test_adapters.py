import json

import httpx

from intake.adapters.inhouse import InHouseAdapter
from intake.adapters.zendesk import ZendeskAdapter, ZendeskConfig
from intake.models import Queue
from tests.conftest import make_ticket


def _recording_client(base_url, seen):
    def handler(request):
        seen.append((request.method, request.url.path, json.loads(request.content)))
        return httpx.Response(200, json={})
    return httpx.Client(base_url=base_url, transport=httpx.MockTransport(handler))


def test_zendesk_update(pipeline):
    r = pipeline.process(make_ticket("UPI payment pending", "Money deducted", "pending", tid="555"))
    seen = []
    cfg = ZendeskConfig("acme", "ops@acme.test", "tok", {q: i for i, q in enumerate(Queue, start=100)},
                        {"severity": 1, "intent": 2, "first_response_due": 3})
    ZendeskAdapter(cfg, _recording_client("https://acme.zendesk.com", seen)).apply(r)
    method, path, body = seen[0]
    assert (method, path) == ("PUT", "/api/v2/tickets/555.json")
    t = body["ticket"]
    assert t["priority"] == "high" and t["group_id"] == cfg.group_ids[Queue.L0_AI_AGENT]
    assert {"id": 1, "value": "Sev2"} in t["custom_fields"]
    assert "sev_sev2" in t["additional_tags"] and t["comment"]["public"] is True
    assert "555" in t["comment"]["body"]


def test_inhouse_patch_and_reply(pipeline):
    r = pipeline.process(make_ticket("Hi", "help", tid="CH-9"))
    seen = []
    InHouseAdapter("https://tickets.internal", "k", _recording_client("https://tickets.internal", seen)).apply(r)
    assert [(m, p) for m, p, _ in seen] == [("PATCH", "/tickets/CH-9"), ("POST", "/tickets/CH-9/replies")]
    assert seen[0][2]["queue"] == "Triage" and seen[0][2]["sla"]["triage_due"]
