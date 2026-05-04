"""
FixMyNameOnline™ — Fulfilment Worker Agents
Runs role-specific internal agent tasks and stores draft outputs in fulfilment cases.

This is intentionally QC-gated: workers prepare drafts, maps, notes, and reports.
They do not publish, submit platform requests, or send legal/sensitive material.

Copyright (c) 2026 MadisonJade Pty Ltd. All rights reserved.
FixMyNameOnline™ is a trademark of MadisonJade Pty Ltd.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, Optional

from fulfilment_engine import (
    load_case_state,
    save_case_state,
    validate_public_text,
    next_actions,
)


def utc_now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def run_task_agent(case_id: str, task_id: str, operator: str = "FulfilmentWorker") -> Dict[str, Any]:
    """Run the correct internal worker for a single task.

    Returns {ok, case, task, output, error?}. All outputs are internal drafts.
    """
    state = load_case_state()
    case = state.get("cases", {}).get(case_id)
    if not case:
        return {"ok": False, "error": "Case not found"}
    task = _find_task(case, task_id)
    if not task:
        return {"ok": False, "error": "Task not found"}

    if task.get("status") in {"done", "approved", "cancelled"}:
        return {"ok": False, "error": f"Task already {task.get('status')}"}
    if task.get("status") == "blocked":
        return {"ok": False, "error": "Task is blocked and needs manual review"}
    if not _dependencies_satisfied(case, task):
        return {"ok": False, "error": "Task dependencies are not complete/approved"}

    agent = task.get("agent", "")
    source = case.get("source", {}) or {}
    customer = case.get("customer", {}) or {}

    output = _dispatch_agent(agent, case, task, source, customer)
    now = utc_now()
    output.update({
        "generated_by": operator,
        "agent": agent,
        "task_id": task_id,
        "generated_at": now,
        "public_text_check": validate_public_text(json.dumps(output, ensure_ascii=False)),
    })

    task.setdefault("outputs", {})[now] = output

    # Execution-sensitive tasks must never auto-complete. They wait for QC/manual approval.
    if task.get("execution_sensitive") or task.get("requires_client_approval"):
        task["status"] = "qc_pending"
        output["gate_result"] = "Prepared only. Execution/client approval still required."
    elif task.get("qc", {}).get("required"):
        task["status"] = "qc_pending"
        output["gate_result"] = "Prepared for QC review."
    else:
        task["status"] = "done"
        output["gate_result"] = "Completed internal non-sensitive task."

    task["updated_at"] = now
    task.setdefault("qc", {}).setdefault("notes", []).append({
        "at": now,
        "author": operator,
        "note": f"{agent} generated internal output. {output['gate_result']}",
        "status": task["status"],
    })
    case.setdefault("notes", []).append({
        "at": now,
        "author": operator,
        "type": "agent_output",
        "note": f"Ran {agent} on {task_id}: {task.get('title')}",
    })
    _promote_ready_tasks(case)
    _refresh_case_status(case)
    case["updated_at"] = now
    save_case_state(state)
    return {"ok": True, "case": case, "task": task, "output": output}


def run_next_ready(case_id: str, operator: str = "FulfilmentWorker") -> Dict[str, Any]:
    actions = next_actions(case_id)
    for action in actions:
        if action.get("status") == "ready":
            return run_task_agent(case_id, action["task_id"], operator=operator)
    return {"ok": False, "error": "No ready task found"}


def _dispatch_agent(agent: str, case: Dict[str, Any], task: Dict[str, Any], source: Dict[str, Any], customer: Dict[str, Any]) -> Dict[str, Any]:
    handlers = {
        "IntakeAgent": _intake_agent,
        "SearchMapper": _search_mapper,
        "EvidenceAgent": _evidence_agent,
        "MonitoringAgent": _monitoring_agent,
        "RemovalAnalyst": _removal_analyst,
        "ReviewDefenceAgent": _review_defence_agent,
        "ContentArchitect": _content_architect,
        "DraftingAgent": _drafting_agent,
        "QCJohnny": _qc_johnny,
        "LegalEscalationGate": _legal_gate,
        "ClientApprovalGate": _client_approval_gate,
        "PublishingOperator": _publishing_operator,
        "CaseOperator": _case_operator,
        "ReportingAgent": _reporting_agent,
    }
    return handlers.get(agent, _generic_agent)(case, task, source, customer)


def _intake_agent(case, task, source, customer):
    missing = []
    for field in ["name", "email"]:
        if not customer.get(field):
            missing.append(field)
    names = source.get("names") or source.get("names_to_check") or customer.get("name") or ""
    links = source.get("links") or source.get("problem_links") or ""
    return {
        "type": "intake_summary",
        "customer": customer,
        "plan": case.get("plan_name"),
        "missing_required": missing,
        "names_to_check": _split_lines(names),
        "links_or_targets": _split_lines(links),
        "context_summary": source.get("context") or source.get("goal") or "No extra context supplied.",
        "avoid_notes": source.get("avoid") or "None supplied.",
        "recommendation": "Proceed to mapping/evidence once required fields are complete." if not missing else "Block until missing fields are collected.",
    }


def _search_mapper(case, task, source, customer):
    base_names = _split_lines(source.get("names") or source.get("names_to_check") or customer.get("name") or "")
    business = customer.get("business") or source.get("business") or ""
    terms = []
    for name in base_names or [customer.get("name", "")]:
        if name:
            terms.extend([
                name,
                f"{name} reviews",
                f"{name} complaint",
                f"{name} court",
                f"{name} news",
                f"{name} {business}".strip(),
            ])
    if business:
        terms.extend([business, f"{business} reviews", f"{business} complaint"])
    return {
        "type": "search_map",
        "primary_terms": sorted(set([t for t in terms if t])),
        "risk_terms": ["reviews", "complaint", "court", "news", "scam", "lawsuit"],
        "asset_gap_hypothesis": [
            "owned profile/about asset",
            "professional bio asset",
            "search-safe article/profile content",
            "review response/reporting notes if relevant",
        ],
        "next_step": "EvidenceAgent should capture current search/review/link state before any drafting or action.",
    }


def _evidence_agent(case, task, source, customer):
    raw_links = source.get("links") or source.get("problem_links") or ""
    links = _split_lines(raw_links)
    evidence = []
    for link in links:
        evidence.append({
            "url_or_term": link,
            "status": "needs screenshot/manual capture" if link.startswith("http") else "search term needs manual capture",
            "capture_fields": ["title", "source/platform", "date seen", "snippet/review text", "screenshot path", "notes"],
        })
    if not evidence:
        evidence.append({
            "url_or_term": customer.get("name") or "customer name",
            "status": "baseline search snapshot needed",
            "capture_fields": ["top results", "risk results", "positive assets", "screenshots", "date seen"],
        })
    return {
        "type": "evidence_plan",
        "evidence_items": evidence,
        "qc_warning": "Do not send requests/responses until evidence screenshots or notes are captured.",
    }


def _monitoring_agent(case, task, source, customer):
    names = _split_lines(source.get("names") or source.get("names_to_check") or customer.get("name") or "")
    return {
        "type": "monitoring_setup",
        "watch_terms": names,
        "frequency": "weekly baseline; urgent terms daily if Premium/Concierge",
        "manual_setup_links": [f"https://www.google.com/alerts?hl=en#1:0"],
        "note": "Google Alerts setup may need manual account interaction; store RSS/feed links when available.",
    }


def _removal_analyst(case, task, source, customer):
    links = _split_lines(source.get("links") or source.get("problem_links") or "")
    pathways = []
    for link in links or ["target not supplied"]:
        low = link.lower()
        if "review" in low or "google" in low:
            path = "platform policy/reporting review"
        elif "news" in low or "article" in low:
            path = "correction/outdated content/de-indexing assessment"
        elif "image" in low:
            path = "image/privacy/copyright pathway assessment"
        else:
            path = "general removal/correction pathway assessment"
        pathways.append({"target": link, "possible_pathway": path, "confidence": "needs evidence/manual verification"})
    return {
        "type": "removal_pathway_analysis",
        "pathways": pathways,
        "legal_guardrail": "This is not legal advice. Legal-risk items require lawyer/manual review.",
        "next_step": "Draft evidence pack/request notes only after evidence is captured.",
    }


def _review_defence_agent(case, task, source, customer):
    return {
        "type": "review_defence_audit",
        "policy_indicators_to_check": [
            "conflict of interest",
            "not a genuine customer experience",
            "harassment or hate content",
            "personal information exposure",
            "review bombing pattern",
            "competitor/ex-employee/ex-partner indicators",
        ],
        "recommended_outputs": [
            "owner response draft in calm professional tone",
            "Google policy reporting notes",
            "evidence table of review/date/reviewer/text/policy issue",
        ],
        "guardrail": "No public response or report submission without client approval.",
    }


def _content_architect(case, task, source, customer):
    name = customer.get("name") or source.get("names") or "Client"
    return {
        "type": "asset_architecture",
        "asset_plan": [
            {"asset": "professional bio/about page", "purpose": "owned truthful identity anchor"},
            {"asset": "profile/social bio refresh", "purpose": "consistent safe entity signals"},
            {"asset": "expertise/FAQ article", "purpose": "positive search-safe context"},
            {"asset": "business/profile listing cleanup", "purpose": "trust and consistency"},
        ],
        "keyword_focus": [name, f"{name} professional", f"{name} profile"],
        "approval_required": True,
    }


def _drafting_agent(case, task, source, customer):
    name = customer.get("name") or "Client"
    business = customer.get("business") or ""
    plan = case.get("plan_key")
    if plan == "review-defence":
        draft = f"Thank you for your feedback. We take all genuine customer experiences seriously and have checked our records so we can understand this properly. If you are open to it, please contact us directly so we can review the details and respond appropriately."
    elif plan == "removal-review":
        draft = "Draft evidence pack: identify the URL, preserve screenshots, note why the content may be inaccurate/outdated/private/policy-relevant, and prepare a careful platform-appropriate request. No legal threats or guarantees included."
    else:
        draft = f"{name} is building a clear, professional online presence based on accurate information, useful context, and approved public-facing materials."
        if business:
            draft += f" This includes careful profile and content assets connected to {business}."
    return {
        "type": "draft_output",
        "draft": draft,
        "approval_required": True,
        "public_text_check": validate_public_text(draft),
        "notes": "Draft is intentionally conservative. Client/QC approval required before public use.",
    }


def _qc_johnny(case, task, source, customer):
    findings = []
    for t in case.get("tasks", []):
        for output in (t.get("outputs") or {}).values():
            check = output.get("public_text_check") or {}
            if check.get("blocked_terms"):
                findings.append({"task": t.get("id"), "blocked_terms": check.get("blocked_terms")})
    return {
        "type": "qc_review",
        "verdict": "needs_fixes" if findings else "draft_safe_for_manual_review",
        "findings": findings,
        "checklist": [
            "No unsupported guarantees",
            "No FPS/backend exposure",
            "No fabricated claims",
            "Sensitive/legal-risk items flagged",
            "Client approval required before public action",
        ],
        "note": "QCJohnny output is a review aid; human/Hermes approval still controls execution gates.",
    }


def _legal_gate(case, task, source, customer):
    return {
        "type": "legal_escalation_gate",
        "risk_flags": case.get("risk_flags", []),
        "verdict": "manual_review_required" if case.get("risk_flags") else "no_obvious_legal_flag_from_intake",
        "guardrail": "Do not provide legal advice. Use qualified lawyer/manual review for legal threats, defamation, court/crime/media issues.",
    }


def _client_approval_gate(case, task, source, customer):
    return {
        "type": "client_approval_request",
        "approval_required": True,
        "client": customer,
        "message_template": "Please review and approve the prepared draft/action notes before anything is published, sent, or submitted.",
        "status": "waiting_for_manual_client_approval",
    }


def _publishing_operator(case, task, source, customer):
    return {
        "type": "publishing_operator_hold",
        "status": "not_executed",
        "reason": "Publishing is intentionally blocked until QC and client approval are recorded.",
        "safe_next_step": "Move approved assets to draft queue only after approvals.",
    }


def _case_operator(case, task, source, customer):
    return {
        "type": "case_operator_hold",
        "status": "not_submitted",
        "reason": "Platform/removal/review actions require QC + client approval + evidence capture.",
        "safe_next_step": "Prepare final checklist, then manually submit/send only after approval.",
    }


def _reporting_agent(case, task, source, customer):
    done = [t for t in case.get("tasks", []) if t.get("status") in {"done", "approved"}]
    pending = [t for t in case.get("tasks", []) if t.get("status") not in {"done", "approved", "cancelled"}]
    return {
        "type": "status_report",
        "case_id": case.get("id"),
        "plan": case.get("plan_name"),
        "completed_tasks": [f"{t.get('id')} {t.get('title')}" for t in done],
        "pending_tasks": [f"{t.get('id')} {t.get('title')}" for t in pending],
        "client_summary": "Work is being prepared through the private QC-gated process. No public action is taken without approval.",
    }


def _generic_agent(case, task, source, customer):
    return {
        "type": "generic_task_output",
        "summary": f"Prepared internal notes for {task.get('title')}.",
        "agent": task.get("agent"),
        "requires_review": True,
    }


def _split_lines(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    raw = str(value).replace(",", "\n")
    return [line.strip() for line in raw.splitlines() if line.strip()]


def _find_task(case: Dict[str, Any], task_id: str) -> Optional[Dict[str, Any]]:
    for task in case.get("tasks", []):
        if task.get("id") == task_id:
            return task
    return None


def _dependencies_satisfied(case: Dict[str, Any], task: Dict[str, Any]) -> bool:
    done_like = {"done", "approved"}
    return all((_find_task(case, dep) or {}).get("status") in done_like for dep in task.get("depends_on", []))


def _promote_ready_tasks(case: Dict[str, Any]) -> None:
    done_like = {"done", "approved"}
    for task in case.get("tasks", []):
        if task.get("status") == "pending" and _dependencies_satisfied(case, task):
            task["status"] = "ready"
            task["updated_at"] = utc_now()


def _refresh_case_status(case: Dict[str, Any]) -> None:
    statuses = [task.get("status") for task in case.get("tasks", [])]
    if any(status == "blocked" for status in statuses) or case.get("risk_flags"):
        case["status"] = "blocked"
    elif all(status in {"done", "approved", "cancelled"} for status in statuses):
        case["status"] = "complete"
    elif any(status == "qc_pending" for status in statuses):
        case["status"] = "qc_pending"
    elif any(status == "in_progress" for status in statuses):
        case["status"] = "executing"
    elif any(status == "ready" for status in statuses):
        case["status"] = "intake_ready"
    else:
        case["status"] = "new"
