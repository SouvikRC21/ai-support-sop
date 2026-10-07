"""Minimal webhook receiver for a Zendesk "Ticket is Created" trigger.

Webhook JSON body (set in the Zendesk webhook / trigger):
  {"id": "{{ticket.id}}", "subject": "{{ticket.title}}", "body": "{{ticket.description}}",
   "requester_id": "{{ticket.requester.id}}", "channel": "{{ticket.via}}"}

Run locally:  python -m intake.webhook   (listens on :8080, keyword classifier, no write-back)
In production, host this behind your API gateway, verify the Zendesk webhook
signature, and pass a ZendeskAdapter so results are written back.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

from .enrich import InMemoryEnrichment
from .models import Channel, Ticket
from .pipeline import IntakePipeline

_CHANNELS = {"email": Channel.EMAIL, "web": Channel.WEB_FORM, "chat": Channel.CHAT, "api": Channel.IN_APP}


def ticket_from_zendesk(payload: dict) -> Ticket:
    return Ticket(
        id=str(payload["id"]),
        channel=_CHANNELS.get(str(payload.get("channel", "")).lower(), Channel.WEB_FORM),
        subject=payload.get("subject", ""),
        body=payload.get("body", ""),
        customer_id=str(payload.get("requester_id", "")),
        created_at=datetime.now(timezone.utc),
    )


def make_handler(pipeline: IntakePipeline, adapter=None):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            result = pipeline.process(ticket_from_zendesk(payload))
            if adapter:
                adapter.apply(result)
            body = json.dumps({
                "queue": result.routing.queue.value,
                "rule": result.routing.rule,
                "severity": result.severity.value,
                "tags": result.tags(),
                "ack": result.ack.text,
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

    return Handler


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 8080), make_handler(IntakePipeline(InMemoryEnrichment()))).serve_forever()
