# AI-First Support Operations: SOP Pack

An end-to-end support operating model for an enterprise SaaS business, showing where AI removes cost and where humans stay in the loop. It covers two product lines (Payments: UPI, UPI QR, netbanking, cards; Subscriptions: 1-month, 6-month and 1-year plans) and two platform options (an in-house ticketing platform + Jira, or Zendesk + Jira).

**Core idea:** measure AI on *resolution*, not *deflection*. In an illustrative model of 50,000 contacts a month, a hybrid AI-plus-human design cuts support run cost by about 44% within six months (roughly $2.5M a year), in line with published research showing 30% to 53% savings for AI-led tier-one support.

![Tier flow](diagrams/00-tier-flow.png)

## Contents

| File | What it is |
| --- | --- |
| [SOP.md](SOP.md) | The full SOP: operating model, seven SOPs with AI-touchpoint diagrams, escalation macros, real-time use cases, savings model, roadmap and risks |
| [Support_AI_Savings_Model.xlsx](Support_AI_Savings_Model.xlsx) | Formula-driven cost model; change the yellow inputs to your own numbers |
| [diagrams/](diagrams/) | One process-and-AI diagram per SOP, plus the tier flow |
| [intake/](intake/) | Reference Python code that automates SOP 1 (intake, triage and routing) |

## The seven SOPs

1. Intake, triage and routing
2. Tiered resolution (L0 AI agent to L4 engineering)
3. Escalation and human handoff (macro-driven)
4. Quality management and reopen root-cause analysis
5. Knowledge management
6. Customer health and churn prevention
7. Workforce management and governance

## SOP 1 automation (reference code)

The `intake/` package automates the seven SOP 1 steps for every new ticket:

| Step | Module | What it does |
| --- | --- | --- |
| 1. Create | `webhook.py`, `adapters/` | Receives the new ticket from Zendesk (trigger + webhook) or the in-house platform |
| 2. Enrich | `enrich.py` | Adds tier, health score, contacts and open tickets in 7 days, last transaction status, active incident |
| 3. Classify | `classifier.py` | Claude returns product line, product, intent, sentiment, language and confidence as structured output. At 0.85 or above the result is locked; below it the ticket goes to Triage with a 15-minute timer |
| 4. Severity | `severity.py` | Sev1 to Sev4 from the matrix (outage, money blocked, workaround, question) |
| 5. Route | `routing.py` | Rules R1 to R8, first match wins. Fraud, chargeback, legal and regulator mentions never go to the bot, even at low confidence |
| 6. SLA timers | `sla.py` | First response by severity and tier, resolution in hours or business days, 15-minute triage deadline and an overdue sweep |
| 7. Acknowledge | `ack.py`, `answer.py` | Ticket ID, expected response time and, for bot-eligible intents, the AI agent's first answer grounded in knowledge articles |

`pipeline.py` runs the steps in order and returns one result that an adapter writes back (group, priority, tags, custom fields, public reply).

```bash
pip install -r requirements.txt
python -m intake.demo            # 8 sample tickets, keyword classifier, no API key needed
python -m pytest -q              # tests run offline
export ANTHROPIC_API_KEY=...     # then:
python -m intake.demo --claude   # Claude classifier and AI first answer
```

Notes for production:

- The Claude calls use `claude-opus-5-5` at low effort, with server-side refusal fallbacks enabled (`fallbacks="default"`). If the API errors or declines, the classifier falls back to the keyword rules, which cap confidence so unclear tickets land in Triage.
- Zendesk: create a trigger on "Ticket is Created" that calls a webhook to the intake service, map queues to group IDs and the classification fields to custom field IDs in `ZendeskConfig`, and point Zendesk SLA policies at the `sev_*` tags.
- In-house platform: adjust the paths in `adapters/inhouse.py` to your ticket API.
- Replace `InMemoryEnrichment` and `StaticKnowledgeBase` with your CRM, ledger and help-centre search. Run `sla.overdue_triage` every minute and alert the triage lead.
- Paging L3 on R1 (`page_l3`) and the Jira link for incidents are left to your on-call and Jira integrations.

## Disclaimer

This is a first-cut reference design. Volumes, costs and savings are illustrative assumptions, and benchmark figures are vendor- or analyst-cited and directional. Regulatory timelines (for example UPI reversal turnaround times) should be confirmed against current RBI/NPCI guidance before use.
