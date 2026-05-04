# FixMyNameOnline™ Paid Fulfilment Pipeline

Copyright (c) 2026 MadisonJade Pty Ltd. All rights reserved.
FixMyNameOnline™ is a trademark of MadisonJade Pty Ltd.

## Purpose

This is the internal operating system for executing paid FMNO plans safely and consistently.

FMNO must not be a random manual service. Every paid customer becomes a structured fulfilment case with:

- a plan-specific task graph
- named agent/operator roles
- evidence capture
- factual checks
- legal/escalation guardrails
- QC approval gates
- client approval gates where needed
- publishing/sending gates
- audit trail
- status reporting

No plan should proceed directly from AI output to public publishing or platform request without QC.

## Core principle

Automation does the drafting, sorting, preparation, monitoring, reporting, and queue management.

Humans/Hermes/QC approve high-risk steps before anything is sent publicly or to a third-party platform.

## Roles

| Role | Purpose | Can approve final action? |
|---|---|---|
| IntakeAgent | Normalize client details, names, links, risk terms, plan | No |
| SearchMapper | Build search/result map and risk surface | No |
| EvidenceAgent | Capture URLs, snippets, screenshots, dates, platform details | No |
| RemovalAnalyst | Identify possible removal/reporting/de-indexing paths | No |
| ReviewDefenceAgent | Audit reviews, policy indicators, response/reporting path | No |
| ContentArchitect | Plan truthful positive assets and search footprint | No |
| DraftingAgent | Draft bios, articles, profiles, responses, reports | No |
| QCJohnny | Quality control: truth, tone, risk, compliance, hallucination check | Yes, draft approval |
| LegalEscalationGate | Flags legal-risk items for lawyer/manual review | Yes/no gate only |
| ClientApprovalGate | Requires client approval before public publishing or sensitive sends | Yes/no gate only |
| PublishingOperator | Publishes approved assets or moves them to draft queue | Only after QC + client approval |
| ReportingAgent | Produces client updates and internal delivery summaries | No |

## Universal case statuses

- new
- intake_ready
- mapped
- evidence_ready
- drafting
- qc_pending
- client_approval_pending
- approved_for_execution
- executing
- monitoring
- complete
- blocked
- cancelled

## Universal task statuses

- pending
- ready
- in_progress
- qc_pending
- approved
- blocked
- done
- cancelled

## QC gates

Every plan uses these gates as applicable:

1. Intake completeness gate
   - name/email present
   - plan known
   - links/names/context captured
   - sensitive/avoid notes captured

2. Evidence gate
   - URLs preserved
   - screenshots or snapshot notes required before platform action
   - source/date/title/snippet stored

3. Factuality gate
   - no fabricated qualifications, roles, awards, testimonials, case facts
   - no claims the client did not approve

4. Brand/safety gate
   - no public mention of First Page Strategy backend
   - no words like suppression/bombardment/manipulate Google
   - no guarantees of removals/rankings/outcomes

5. Legal/escalation gate
   - anything involving crime/court/defamation/media/legal threats is flagged
   - AI can draft notes/evidence packs, but legal advice needs qualified lawyer/manual review

6. Client approval gate
   - required before public assets, public responses, or platform submissions

7. Execution gate
   - only approved tasks move to publish/send/submit

## Plan pipelines

### Sentinel Alert™ — $29/month

Purpose: monitoring only.

Tasks:
1. IntakeAgent — create keyword/watchlist map
2. SearchMapper — associated names + risk term matrix
3. EvidenceAgent — baseline current search snapshot
4. ReportingAgent — initial monitoring summary
5. MonitoringAgent — recurring alert checks
6. QCJohnny — review first report before client delivery

Do not include human repair/content/removal work unless upsold.

### Removal Review™ — $297 one-time

Purpose: assess whether links/articles/snippets/images may have a valid removal, correction, reporting, or de-indexing path.

Tasks:
1. IntakeAgent — validate case details
2. EvidenceAgent — capture target URLs, screenshots/snapshot notes, source metadata
3. RemovalAnalyst — classify pathway: platform policy, privacy, outdated content, correction, de-indexing, defamation-risk, no-path
4. DraftingAgent — draft evidence pack and request notes where appropriate
5. LegalEscalationGate — flag legal-risk items
6. QCJohnny — approve/reject drafts
7. ClientApprovalGate — client approves before anything is sent
8. PublishingOperator/CaseOperator — submit/send only after approval
9. ReportingAgent — deliver outcome and tracker link/status

### Review Defence™ — $497 one-time

Purpose: handle fake/malicious Google review patterns and response/reporting preparation.

Tasks:
1. IntakeAgent — business/profile/review details
2. EvidenceAgent — review list, dates, screenshots/snapshot notes, reviewer names where public
3. ReviewDefenceAgent — policy audit and likely reporting arguments
4. DraftingAgent — owner response drafts + platform reporting notes
5. QCJohnny — factual/tone/legal risk review
6. ClientApprovalGate — client approves final responses/reporting notes
7. CaseOperator — submit/report/respond if authorized
8. ReportingAgent — client report and follow-up schedule

### Starter™ — $499/month

Purpose: basic search repair and positive asset system.

Tasks:
1. IntakeAgent — client profile + boundaries
2. SearchMapper — search map and content gaps
3. ContentArchitect — starter asset plan
4. DraftingAgent — first content/profile drafts
5. QCJohnny — factuality and brand safety review
6. ClientApprovalGate — approval before public use
7. PublishingOperator — create draft/publish approved assets only
8. ReportingAgent — monthly status update

### Pro™ — $997/month

Purpose: deeper repair with more assets and monitoring.

Starter tasks plus:
- expanded keyword map
- more content drafts
- stronger internal QC
- monthly asset/report cadence
- removal/review opportunities flagged for upsell or included support depending scope

### Premium™ — $2,497/month

Purpose: high-touch repair and search footprint buildout.

Pro tasks plus:
- weekly review queue
- broader asset architecture
- stronger client approval workflow
- priority QC
- escalation notes for sensitive cases

### Concierge™ — custom

Purpose: urgent/high-risk/private handling.

Always starts blocked at LegalEscalationGate/ManualReviewGate before automation executes anything public.

## Automation boundaries

Allowed to automate now:
- intake normalization
- queue creation
- task creation
- internal alerts
- email confirmations
- draft generation
- internal reports
- status tracking
- non-public draft queues
- monitoring reminders

Requires QC/client approval:
- public publishing
- platform report submission
- removal/de-indexing request submission
- Google Business Profile responses
- sensitive claims
- any legal-risk wording

Never automate blindly:
- legal advice
- court/defamation threats
- fake reviews/testimonials
- unverified claims
- public posting under client identity without approval
- Reddit/Quora/Substack auto-posting claims where API/support is not reliable

## Implementation files

- `fulfilment_engine.py` — plan templates, task graph, case creation, status/QC utilities
- `server.py` — creates fulfilment cases from onboarding/webhook and exposes token-protected admin endpoints
- `data/fulfilment_cases.jsonl` — append-only case audit trail
- `data/fulfilment_case_state.json` — current mutable case state
- `data/fulfilment_queue.jsonl` — intake queue already created

## Next build step

Build the internal dashboard/command center page for Elli:

- view cases by plan/status/priority
- inspect task graph
- mark task approved/blocked/done
- add QC notes
- see which cases need client approval
- see which tasks are safe to execute vs blocked
