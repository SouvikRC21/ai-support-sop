"""The L0 AI agent's first answer, grounded in the knowledge base (RAG)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, Protocol

import anthropic

from .classifier import MODEL
from .models import Classification, Enrichment, Ticket

log = logging.getLogger(__name__)


@dataclass
class Article:
    id: str
    title: str
    body: str
    products: tuple[str, ...] = ()  # empty = applies to every product


class KnowledgeBase(Protocol):
    def search(self, query: str, product: str, intent: str, k: int = 3) -> list[Article]: ...


class Answerer(Protocol):
    def first_answer(self, ticket: Ticket, c: Classification, e: Enrichment) -> Optional[str]: ...


class StaticKnowledgeBase:
    """Reference KB keyed by intent. Replace with your vector store or help-centre search."""

    def __init__(self, articles_by_intent: dict[str, list[Article]]):
        self.articles_by_intent = articles_by_intent

    def search(self, query: str, product: str, intent: str, k: int = 3) -> list[Article]:
        hits = [a for a in self.articles_by_intent.get(intent, []) if not a.products or product in a.products]
        return hits[:k]


ANSWER_SYSTEM = """You are the first-line support agent for a payments and subscriptions company.
Answer the customer's question using only the knowledge articles provided. If the articles
do not cover it, say a specialist will reply and do not guess. Never ask for full card
numbers, CVV, UPI PIN or OTP. Reply in the customer's language, in under 120 words,
plain text, no greeting or sign-off (those are added around your answer)."""


class ClaudeAnswerer:
    def __init__(self, kb: KnowledgeBase, client: anthropic.Anthropic | None = None):
        self.kb = kb
        self.client = client or anthropic.Anthropic()

    def first_answer(self, ticket: Ticket, c: Classification, e: Enrichment) -> Optional[str]:
        articles = self.kb.search(f"{ticket.subject} {ticket.body}", c.product, c.intent)
        if not articles:
            return None  # no grounding, no bot answer
        docs = "\n".join(f'<article id="{a.id}" title="{a.title}">\n{a.body}\n</article>' for a in articles)
        prompt = (
            f"<knowledge>\n{docs}\n</knowledge>\n"
            f"<account last_txn_status=\"{e.last_txn_status}\" last_txn_id=\"{e.last_txn_id}\" />\n"
            f"<customer_message language=\"{c.language}\">\nSubject: {ticket.subject}\n\n{ticket.body}\n</customer_message>"
        )
        try:
            response = self.client.beta.messages.create(
                model=MODEL,
                max_tokens=2048,
                system=ANSWER_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
                output_config={"effort": "low"},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.APIError as exc:
            log.warning("AI first answer failed for %s: %s", ticket.id, exc)
            return None
        if response.stop_reason == "refusal":
            return None
        text = "".join(b.text for b in response.content if b.type == "text").strip()
        return text or None


class TemplateAnswerer:
    """Offline answerer: returns the top article body for the intent."""

    def __init__(self, kb: KnowledgeBase):
        self.kb = kb

    def first_answer(self, ticket: Ticket, c: Classification, e: Enrichment) -> Optional[str]:
        articles = self.kb.search(ticket.body, c.product, c.intent, k=1)
        return articles[0].body if articles else None
