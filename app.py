"""RelayDesk demo: evidence-backed ticket triage with approval-gated actions."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import Flask, jsonify, render_template, request
from dotenv import load_dotenv

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")
app = Flask(__name__)


def load_json(name: str):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


TICKETS = load_json("tickets.json")
ARTICLES = load_json("knowledge.json")
AUDIT_LOG: list[dict] = []
APPROVED_ACTIONS: list[dict] = []
STOP_WORDS = {"the", "and", "for", "with", "that", "this", "from", "have", "can", "you", "our", "are", "was", "were", "not", "what", "where", "after", "into", "still", "then", "about"}


def words(text: str) -> list[str]:
    return [word for word in re.findall(r"[a-z0-9]+", text.lower()) if len(word) > 2 and word not in STOP_WORDS]


def retrieve(message: str, limit: int = 3) -> list[dict]:
    query = set(words(message))
    ranked = []
    for article in ARTICLES:
        title_terms = set(words(article["title"]))
        haystack = set(words(article["title"] + " " + article["category"] + " " + article["body"]))
        overlap = query & haystack
        score = sum(2.0 if term in title_terms else 1.0 for term in overlap)
        if score:
            ranked.append((min(1.0, score / max(1, len(query) + len(title_terms))), article))
    ranked.sort(key=lambda row: (-row[0], row[1]["id"]))
    return [dict(article, score=round(score, 3)) for score, article in ranked[:limit]]


def classify(message: str) -> dict:
    text = message.lower()
    rules = [
        ("Billing", ("charge", "charged", "invoice", "renewal", "billing", "refund", "payment")),
        ("Access & accounts", ("invite", "seat", "login", "sign in", "member", "permission", "access")),
        ("Workspace", ("sync", "folder", "workspace", "plan change", "project folder")),
        ("Reporting", ("export", "csv", "report", "download")),
    ]
    category = next((label for label, cues in rules if any(cue in text for cue in cues)), "General support")
    urgency_cues = ("blocked", "cannot work", "can't work", "deadline", "review at", "outage", "urgent", "business interruption")
    urgency = "High" if any(cue in text for cue in urgency_cues) else "Normal"
    if category == "Billing":
        action = {"key": "billing_review", "label": "Prepare a billing-review handoff", "reason": "Billing outcomes require a specialist; the copilot will not promise a refund."}
    elif urgency == "High":
        action = {"key": "specialist_escalation", "label": "Prepare a specialist escalation", "reason": "The message describes time-sensitive impact, so a person should review the handoff."}
    elif category == "Access & accounts":
        action = {"key": "account_check", "label": "Prepare an account-seat check", "reason": "The next documented check is the workspace's member, invitation and seat state."}
    else:
        action = {"key": "send_guidance", "label": "Prepare a guidance reply", "reason": "The available guide contains a documented next step for this request."}
    return {"category": category, "priority": urgency, "action": action}


def draft_from_evidence(ticket: dict, result: dict) -> tuple[str, str]:
    evidence = result["evidence"]
    if not evidence or evidence[0]["score"] < 0.22:
        return "Thanks for reaching out. I could not find sufficiently relevant guidance to recommend a reliable next step, so a support specialist should review this request.", "Safe fallback · evidence needs review"
    if os.getenv("OPENAI_API_KEY") and os.getenv("OPENAI_MODEL"):
        source_text = "\n".join(f"[{item['id']}] {item['title']}: {item['body']}" for item in evidence)
        prompt = (
            "Write a concise, courteous support reply using only the supplied evidence. "
            "Do not invent account facts, promise outcomes or imply an action has happened. "
            "If the evidence is insufficient, say a specialist needs to review it. "
            "Return only the reply text.\n\n"
            f"Customer message: {ticket['message']}\n\nEvidence:\n{source_text}"
        )
        payload = json.dumps({"model": os.environ["OPENAI_MODEL"], "input": prompt, "store": False}).encode()
        req = Request("https://api.openai.com/v1/responses", data=payload, headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}", "Content-Type": "application/json"})
        try:
            with urlopen(req, timeout=20) as response:
                data = json.loads(response.read().decode())
            text = "\n".join(part.get("text", "") for item in data.get("output", []) for part in item.get("content", []) if part.get("type") == "output_text").strip()
            if text:
                return text, "Model-assisted draft · verify before sending"
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, KeyError):
            pass
    if evidence:
        lead = "Thanks for reaching out. Based on the support guide, the recommended next step is: " + evidence[0]["body"]
        if result["triage"]["priority"] == "High":
            lead += " We’ll flag the reported time-sensitive impact for a support specialist to review."
        return lead, "Evidence-based demo draft · no model key needed"
    return "Thanks for reaching out. I don’t have enough documented information to give a reliable next step, so this needs a support specialist to review.", "Safe fallback · evidence not found"


def ticket_by_id(ticket_id: str):
    return next((ticket for ticket in TICKETS if ticket["id"] == ticket_id), None)


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/tickets")
def tickets():
    return jsonify(TICKETS)


@app.post("/api/triage")
def triage():
    data = request.get_json(silent=True) or {}
    ticket = ticket_by_id(str(data.get("ticket_id", "")))
    if not ticket:
        return jsonify({"error": "Select a sample ticket and try again."}), 400
    evidence = retrieve(ticket["subject"] + " " + ticket["message"])
    result = {"ticket": ticket, "triage": classify(ticket["message"]), "evidence": evidence}
    result["draft"], result["draft_mode"] = draft_from_evidence(ticket, result)
    result["confidence"] = "Strong match" if evidence and evidence[0]["score"] >= 0.22 else "Review"
    result["run_id"] = f"RUN-{len(AUDIT_LOG) + 1:03d}"
    AUDIT_LOG.insert(0, {"kind": "triage", "ticket_id": ticket["id"], "run_id": result["run_id"], "at": datetime.now(timezone.utc).isoformat(timespec="minutes"), "category": result["triage"]["category"], "priority": result["triage"]["priority"]})
    return jsonify(result)


@app.post("/api/actions/approve")
def approve_action():
    data = request.get_json(silent=True) or {}
    ticket = ticket_by_id(str(data.get("ticket_id", "")))
    key = str(data.get("action_key", ""))
    if not ticket or key not in {"billing_review", "specialist_escalation", "account_check", "send_guidance"}:
        return jsonify({"error": "That action is not available in this demo."}), 400
    action = {"id": f"ACT-{len(APPROVED_ACTIONS) + 1:03d}", "ticket_id": ticket["id"], "action_key": key, "status": "Demo action recorded", "at": datetime.now(timezone.utc).isoformat(timespec="minutes")}
    APPROVED_ACTIONS.insert(0, action)
    AUDIT_LOG.insert(0, {"kind": "approved_action", **action})
    return jsonify(action)


@app.get("/api/audit")
def audit():
    return jsonify({"events": AUDIT_LOG[:30], "approved_actions": APPROVED_ACTIONS[:15]})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5055")), debug=False)

