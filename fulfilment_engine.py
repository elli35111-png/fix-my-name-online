"""
FixMyNameOnline™ — Paid Plan Fulfilment Engine
Structured agent pipeline, QC gates, and fulfilment case state.

Copyright (c) 2026 MadisonJade Pty Ltd. All rights reserved.
FixMyNameOnline™ is a trademark of MadisonJade Pty Ltd.
"""
from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

DATA_DIR = Path(os.environ.get("FMNO_DATA_DIR", "data"))
DATA_DIR.mkdir(exist_ok=True)
CASES_AUDIT_FILE = DATA_DIR / "fulfilment_cases.jsonl"
CASE_STATE_FILE = DATA_DIR / "fulfilment_case_state.json"

SAFE_PUBLIC_WORDS_BLOCKLIST = [
    "suppression",
    "suppressing",
    "bury negative",
    "bombardment",
    "manipulate google",
    "guarantee removal",
    "guaranteed removal",
    "guarantee ranking",
    "guaranteed ranking",
    "first page strategy",
    "fps media network",
]

QC_GATES = {
    "intake_complete": "Required customer/plan/details captured.",
    "evidence_ready": "URLs/search results/reviews/snapshot notes captured before action.",
    "factuality": "No fabricated facts, roles, achievements, testimonials, or legal facts.",
    "brand_safety": "No unsafe public language or backend exposure.",
    "legal_escalation": "Sensitive/legal-risk material flagged for manual/legal review.",
    "client_approval": "Client approves public assets, responses, or platform submissions.",
    "execution_approval": "QC-approved item may be sent/published/submitted.",
}

AGENT_ROLES = {
    "IntakeAgent": "Normalize client details, names, links, risk terms, plan, and boundaries.",
    "SearchMapper": "Map search surface, associated names, risk terms, and content gaps.",
    "EvidenceAgent": "Capture URLs, snippets, dates, screenshots/snapshot notes, platform details.",
    "MonitoringAgent": "Set up and run recurring alert/mention checks.",
    "RemovalAnalyst": "Classify removal/reporting/de-indexing/correction pathways.",
    "ReviewDefenceAgent": "Audit review patterns and platform policy reporting paths.",
    "ContentArchitect": "Design truthful positive asset/search footprint plan.",
    "DraftingAgent": "Draft evidence packs, response notes, bios, articles, and profile content.",
    "QCJohnny": "Final quality control: factuality, tone, safety, compliance, hallucination check.",
    "LegalEscalationGate": "Flags legal-risk/sensitive matters for manual or lawyer review.",
    "ClientApprovalGate": "Requires client approval before public/sensitive execution.",
    "PublishingOperator": "Publishes or queues approved content only after gates pass.",
    "CaseOperator": "Submits/sends approved platform requests or review responses only after gates pass.",
    "ReportingAgent": "Produces client-facing and internal delivery reports.",
}


def utc_now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def task(task_id: str, title: str, agent: str, gates: Optional[List[str]] = None, depends_on: Optional[List[str]] = None, requires_client_approval: bool = False, execution_sensitive: bool = False) -> Dict[str, Any]:
    return {
        "id": task_id,
        "title": title,
        "agent": agent,
        "description": AGENT_ROLES.get(agent, ""),
        "depends_on": depends_on or [],
        "gates": gates or [],
        "requires_client_approval": requires_client_approval,
        "execution_sensitive": execution_sensitive,
        "status": "pending" if depends_on else "ready",
        "qc": {
            "required": bool(gates or requires_client_approval or execution_sensitive),
            "approved": False,
            "approved_by": None,
            "approved_at": None,
            "notes": [],
        },
        "outputs": {},
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }


PLAN_TEMPLATES = {
    "sentinel": {
        "name": "Sentinel Alert™",
        "default_priority": "standard",
        "description": "Monitoring-only plan. No human repair/content/removal work unless separately approved/upsold.",
        "tasks": [
            task("SEN-001", "Normalize customer watchlist and associated names", "IntakeAgent", ["intake_complete"]),
            task("SEN-002", "Build search/watch term matrix", "SearchMapper", ["brand_safety"], ["SEN-001"]),
            task("SEN-003", "Capture baseline search snapshot notes", "EvidenceAgent", ["evidence_ready"], ["SEN-002"]),
            task("SEN-004", "Create monitoring schedule and alert setup notes", "MonitoringAgent", [], ["SEN-003"]),
            task("SEN-005", "QC first monitoring summary", "QCJohnny", ["factuality", "brand_safety"], ["SEN-004"]),
            task("SEN-006", "Send initial monitoring report", "ReportingAgent", ["execution_approval"], ["SEN-005"]),
        ],
    },
    "removal-review": {
        "name": "Removal Review™",
        "default_priority": "high",
        "description": "Review links/articles/snippets/images for appropriate removal, correction, reporting, or de-indexing pathways. No legal advice or guaranteed outcome.",
        "tasks": [
            task("REM-001", "Validate intake and target links", "IntakeAgent", ["intake_complete"]),
            task("REM-002", "Capture evidence pack for each target", "EvidenceAgent", ["evidence_ready"], ["REM-001"]),
            task("REM-003", "Classify possible action pathways", "RemovalAnalyst", ["legal_escalation", "factuality"], ["REM-002"]),
            task("REM-004", "Draft request notes/evidence pack", "DraftingAgent", ["factuality", "brand_safety"], ["REM-003"]),
            task("REM-005", "Manual/legal-risk gate", "LegalEscalationGate", ["legal_escalation"], ["REM-004"], execution_sensitive=True),
            task("REM-006", "QC removal review pack", "QCJohnny", ["factuality", "brand_safety", "execution_approval"], ["REM-005"]),
            task("REM-007", "Client approval before submission", "ClientApprovalGate", ["client_approval"], ["REM-006"], requires_client_approval=True, execution_sensitive=True),
            task("REM-008", "Send/submit approved request or mark no-path", "CaseOperator", ["execution_approval"], ["REM-007"], execution_sensitive=True),
            task("REM-009", "Create status report and follow-up schedule", "ReportingAgent", [], ["REM-008"]),
        ],
    },
    "review-defence": {
        "name": "Review Defence™",
        "default_priority": "high",
        "description": "Audit malicious/fake review pattern, prepare policy reporting notes and owner responses. Client approval required before public response/submission.",
        "tasks": [
            task("REV-001", "Validate business/profile/review intake", "IntakeAgent", ["intake_complete"]),
            task("REV-002", "Capture review evidence and review metadata", "EvidenceAgent", ["evidence_ready"], ["REV-001"]),
            task("REV-003", "Audit review policy indicators", "ReviewDefenceAgent", ["factuality"], ["REV-002"]),
            task("REV-004", "Draft owner responses and reporting notes", "DraftingAgent", ["factuality", "brand_safety"], ["REV-003"]),
            task("REV-005", "QC response/reporting pack", "QCJohnny", ["factuality", "brand_safety", "execution_approval"], ["REV-004"]),
            task("REV-006", "Client approval before response/report", "ClientApprovalGate", ["client_approval"], ["REV-005"], requires_client_approval=True, execution_sensitive=True),
            task("REV-007", "Submit/report/respond only if approved", "CaseOperator", ["execution_approval"], ["REV-006"], execution_sensitive=True),
            task("REV-008", "Prepare follow-up report", "ReportingAgent", [], ["REV-007"]),
        ],
    },
    "starter": {
        "name": "Starter™",
        "default_priority": "standard",
        "description": "Basic search repair and truthful positive asset buildout.",
        "tasks": [
            task("STA-001", "Validate profile, boundaries, names, and search terms", "IntakeAgent", ["intake_complete"]),
            task("STA-002", "Map search surface and asset gaps", "SearchMapper", ["evidence_ready"], ["STA-001"]),
            task("STA-003", "Design Starter asset plan", "ContentArchitect", ["brand_safety"], ["STA-002"]),
            task("STA-004", "Draft first asset/content set", "DraftingAgent", ["factuality", "brand_safety"], ["STA-003"]),
            task("STA-005", "QC factuality and safe positioning", "QCJohnny", ["factuality", "brand_safety"], ["STA-004"]),
            task("STA-006", "Client approval before public use", "ClientApprovalGate", ["client_approval"], ["STA-005"], requires_client_approval=True),
            task("STA-007", "Queue/publish approved assets", "PublishingOperator", ["execution_approval"], ["STA-006"], execution_sensitive=True),
            task("STA-008", "Monthly delivery report", "ReportingAgent", [], ["STA-007"]),
        ],
    },
    "pro": {
        "name": "Pro™",
        "default_priority": "high",
        "description": "Expanded search repair, monitoring, and asset cadence.",
        "inherits": "starter",
        "extra_tasks": [
            task("PRO-009", "Expand keyword/associated-name map", "SearchMapper", ["evidence_ready"], ["STA-002"]),
            task("PRO-010", "Create Pro content cluster plan", "ContentArchitect", ["brand_safety"], ["PRO-009"]),
            task("PRO-011", "Draft expanded approved asset batch", "DraftingAgent", ["factuality", "brand_safety"], ["PRO-010"]),
            task("PRO-012", "QC expanded asset batch", "QCJohnny", ["factuality", "brand_safety"], ["PRO-011"]),
            task("PRO-013", "Pro monthly strategy report", "ReportingAgent", [], ["PRO-012"]),
        ],
    },
    "premium": {
        "name": "Premium™",
        "default_priority": "urgent",
        "description": "High-touch repair, broader footprint, weekly review cadence, priority QC.",
        "inherits": "pro",
        "extra_tasks": [
            task("PRE-014", "Premium weekly risk review", "QCJohnny", ["factuality", "brand_safety"], ["PRO-013"]),
            task("PRE-015", "Premium authority asset roadmap", "ContentArchitect", ["brand_safety"], ["PRE-014"]),
            task("PRE-016", "Premium client update pack", "ReportingAgent", [], ["PRE-015"]),
        ],
    },
    "concierge": {
        "name": "Concierge™",
        "default_priority": "urgent",
        "description": "Custom high-risk/private handling. Starts blocked until manual/legal-risk review.",
        "tasks": [
            task("CON-001", "High-risk private intake review", "IntakeAgent", ["intake_complete", "legal_escalation"]),
            task("CON-002", "Manual/legal-risk gate before automation", "LegalEscalationGate", ["legal_escalation"], ["CON-001"], execution_sensitive=True),
            task("CON-003", "Custom private case plan", "QCJohnny", ["factuality", "brand_safety"], ["CON-002"]),
            task("CON-004", "Client approval of custom scope", "ClientApprovalGate", ["client_approval"], ["CON-003"], requires_client_approval=True),
        ],
        "initial_status": "blocked",
    },
}


def utc_now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def _append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")


def resolve_template(plan: str) -> Dict[str, Any]:
    key = normalize_plan(plan)
    if key not in PLAN_TEMPLATES:
        key = "starter"
    template = deepcopy(PLAN_TEMPLATES[key])
    inherited = template.get("inherits")
    if inherited:
        parent = resolve_template(inherited)
        parent_tasks = parent.get("tasks", [])
        template["tasks"] = parent_tasks + template.get("extra_tasks", [])
        template.pop("extra_tasks", None)
    return template


def normalize_plan(plan: str) -> str:
    plan = (plan or "starter").strip().lower().replace("_", "-")
    aliases = {
        "sentinel-alert": "sentinel",
        "sentinel-alert™": "sentinel",
        "removal": "removal-review",
        "removal-application": "removal-review",
        "review-defense": "review-defence",
        "review-defence™": "review-defence",
        "starter™": "starter",
        "pro™": "pro",
        "premium™": "premium",
        "private": "concierge",
        "high-risk": "concierge",
    }
    return aliases.get(plan, plan)


def load_case_state() -> Dict[str, Any]:
    return _read_json(CASE_STATE_FILE, {"cases": {}})


def save_case_state(state: Dict[str, Any]) -> None:
    _write_json(CASE_STATE_FILE, state)


def create_fulfilment_case(plan: str, customer: Dict[str, Any], source: Optional[Dict[str, Any]] = None, trigger: str = "manual") -> Dict[str, Any]:
    plan_key = normalize_plan(plan)
    template = resolve_template(plan_key)
    now = utc_now()
    case_id = f"FMNO-CASE-{now.replace('-', '').replace(':', '').replace('.', '').replace('Z', '')}"
    tasks = template.get("tasks", [])
    initial_status = template.get("initial_status") or "new"
    case = {
        "id": case_id,
        "plan_key": plan_key,
        "plan_name": template.get("name", plan_key.title()),
        "description": template.get("description", ""),
        "status": initial_status,
        "priority": template.get("default_priority", "standard"),
        "trigger": trigger,
        "customer": {
            "name": customer.get("name") or customer.get("customer_name") or "",
            "email": customer.get("email") or customer.get("customer_email") or "",
            "phone": customer.get("phone", ""),
            "business": customer.get("business", ""),
        },
        "source": source or {},
        "tasks": tasks,
        "gates": deepcopy(QC_GATES),
        "notes": [],
        "created_at": now,
        "updated_at": now,
    }
    case["risk_flags"] = detect_risk_flags(case)
    if case["risk_flags"] and case["status"] != "blocked":
        case["status"] = "blocked"
        case["notes"].append({"at": now, "type": "risk_flag", "note": "Sensitive/legal-risk words detected; manual gate required before execution.", "flags": case["risk_flags"]})

    state = load_case_state()
    state.setdefault("cases", {})[case_id] = case
    save_case_state(state)
    _append_jsonl(CASES_AUDIT_FILE, {"event": "case_created", "case": case, "created_at": now})
    return case


def detect_risk_flags(case: Dict[str, Any]) -> List[str]:
    text = json.dumps(case.get("source", {}), ensure_ascii=False).lower()
    flags = []
    legal_words = ["court", "criminal", "police", "lawsuit", "defamation", "media", "journalist", "threat", "stalking", "dox", "urgent"]
    for word in legal_words:
        if word in text:
            flags.append(word)
    return sorted(set(flags))


def list_cases(status: Optional[str] = None, plan: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    state = load_case_state()
    cases = list(state.get("cases", {}).values())
    if status:
        cases = [c for c in cases if c.get("status") == status]
    if plan:
        plan_key = normalize_plan(plan)
        cases = [c for c in cases if c.get("plan_key") == plan_key]
    cases.sort(key=lambda c: c.get("updated_at", ""), reverse=True)
    return cases[:limit]


def get_case(case_id: str) -> Optional[Dict[str, Any]]:
    return load_case_state().get("cases", {}).get(case_id)


def add_case_note(case_id: str, note: str, author: str = "system", note_type: str = "note") -> Optional[Dict[str, Any]]:
    state = load_case_state()
    case = state.get("cases", {}).get(case_id)
    if not case:
        return None
    entry = {"at": utc_now(), "author": author, "type": note_type, "note": note}
    case.setdefault("notes", []).append(entry)
    case["updated_at"] = utc_now()
    save_case_state(state)
    _append_jsonl(CASES_AUDIT_FILE, {"event": "case_note", "case_id": case_id, "entry": entry, "created_at": utc_now()})
    return case


def update_task_status(case_id: str, task_id: str, status: str, note: str = "", author: str = "system") -> Optional[Dict[str, Any]]:
    allowed = {"pending", "ready", "in_progress", "qc_pending", "approved", "blocked", "done", "cancelled"}
    if status not in allowed:
        raise ValueError(f"Invalid task status: {status}")
    state = load_case_state()
    case = state.get("cases", {}).get(case_id)
    if not case:
        return None
    task_obj = _find_task(case, task_id)
    if not task_obj:
        return None
    task_obj["status"] = status
    task_obj["updated_at"] = utc_now()
    if note:
        task_obj.setdefault("qc", {}).setdefault("notes", []).append({"at": utc_now(), "author": author, "note": note, "status": status})
    _promote_ready_tasks(case)
    _refresh_case_status(case)
    case["updated_at"] = utc_now()
    save_case_state(state)
    _append_jsonl(CASES_AUDIT_FILE, {"event": "task_status", "case_id": case_id, "task_id": task_id, "status": status, "note": note, "author": author, "created_at": utc_now()})
    return case


def approve_task(case_id: str, task_id: str, approved_by: str = "QCJohnny", note: str = "") -> Optional[Dict[str, Any]]:
    state = load_case_state()
    case = state.get("cases", {}).get(case_id)
    if not case:
        return None
    task_obj = _find_task(case, task_id)
    if not task_obj:
        return None
    task_obj["qc"]["approved"] = True
    task_obj["qc"]["approved_by"] = approved_by
    task_obj["qc"]["approved_at"] = utc_now()
    if note:
        task_obj["qc"].setdefault("notes", []).append({"at": utc_now(), "author": approved_by, "note": note, "status": "approved"})
    task_obj["status"] = "approved"
    task_obj["updated_at"] = utc_now()
    _promote_ready_tasks(case)
    _refresh_case_status(case)
    case["updated_at"] = utc_now()
    save_case_state(state)
    _append_jsonl(CASES_AUDIT_FILE, {"event": "task_approved", "case_id": case_id, "task_id": task_id, "approved_by": approved_by, "note": note, "created_at": utc_now()})
    return case


def next_actions(case_id: str) -> List[Dict[str, Any]]:
    case = get_case(case_id)
    if not case:
        return []
    actions = []
    done_like = {"done", "approved"}
    for t in case.get("tasks", []):
        deps_done = all((_find_task(case, dep) or {}).get("status") in done_like for dep in t.get("depends_on", []))
        if t.get("status") in {"ready", "in_progress", "qc_pending", "blocked"} or (t.get("status") == "pending" and deps_done):
            actions.append({
                "task_id": t["id"],
                "title": t["title"],
                "agent": t["agent"],
                "status": "ready" if deps_done and t.get("status") == "pending" else t.get("status"),
                "requires_qc": t.get("qc", {}).get("required", False),
                "requires_client_approval": t.get("requires_client_approval", False),
                "execution_sensitive": t.get("execution_sensitive", False),
                "gates": t.get("gates", []),
            })
    return actions


def validate_public_text(text: str) -> Dict[str, Any]:
    low = (text or "").lower()
    hits = [w for w in SAFE_PUBLIC_WORDS_BLOCKLIST if w in low]
    return {"ok": not hits, "blocked_terms": hits}


def _find_task(case: Dict[str, Any], task_id: str) -> Optional[Dict[str, Any]]:
    for t in case.get("tasks", []):
        if t.get("id") == task_id:
            return t
    return None


def _promote_ready_tasks(case: Dict[str, Any]) -> None:
    done_like = {"done", "approved"}
    for t in case.get("tasks", []):
        if t.get("status") != "pending":
            continue
        if all((_find_task(case, dep) or {}).get("status") in done_like for dep in t.get("depends_on", [])):
            t["status"] = "ready"
            t["updated_at"] = utc_now()


def _refresh_case_status(case: Dict[str, Any]) -> None:
    statuses = [t.get("status") for t in case.get("tasks", [])]
    if any(s == "blocked" for s in statuses) or case.get("risk_flags"):
        case["status"] = "blocked"
    elif all(s in {"done", "approved", "cancelled"} for s in statuses):
        case["status"] = "complete"
    elif any(s == "qc_pending" for s in statuses):
        case["status"] = "qc_pending"
    elif any(s == "in_progress" for s in statuses):
        case["status"] = "executing"
    elif any(s == "ready" for s in statuses):
        case["status"] = "intake_ready"
    else:
        case["status"] = "new"


if __name__ == "__main__":
    demo = create_fulfilment_case(
        "review-defence",
        {"name": "Demo Customer", "email": "demo@example.com", "business": "Demo Business"},
        {"links": "https://example.com/review", "context": "demo only"},
        trigger="cli_demo",
    )
    print(json.dumps({"created": demo["id"], "next_actions": next_actions(demo["id"])}, indent=2))
