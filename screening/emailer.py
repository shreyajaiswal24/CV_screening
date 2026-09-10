"""Interview invitations.

THE STRICTEST GATE IN THE SYSTEM. An email to a real candidate cannot be
unsent, so four conditions must ALL hold before anything leaves:

  1. the fit tier is at or above email_min_tier (GREAT FIT by default)
  2. an email address was actually extracted from the CV - never guessed
  3. a human clicked approve on the screening result
  4. a human clicked send on the draft itself, having seen it in full

Default is dry-run: the draft is rendered and logged, nothing is sent. Sending
is switched on deliberately in config.yaml.

The draft is a TEMPLATE, not model output. Every specific in it - the name, the
role, the criteria named - comes from a field that was already verified against
the CV. A model writing free text straight to a candidate would reintroduce
exactly the fabrication risk the rest of this system exists to remove.
"""
from __future__ import annotations

import os
import re
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

from screening.config import ROOT, SETTINGS, Secrets
from screening.schemas import EmailDraft, RunResult, Verdict

TIER_ORDER = {Verdict.LOW_FIT: 0, Verdict.MEDIUM_FIT: 1, Verdict.GREAT_FIT: 2}
EMAIL_RE = re.compile(r"^[\w.+-]+@[\w-]+\.[\w.]+$")

TEMPLATE = """Hi {first_name},

Thanks for applying for the {role} role at {company}.

We've reviewed your CV and would like to speak with you. Your experience with
{highlights} is a strong match for what we're looking for.

Would you be free for a {duration} introductory call this week or next? Reply
with a couple of times that suit you and we'll send an invitation.

{extra}Looking forward to speaking.

Best regards,
{sender_name}
{company}
"""

ASK_LINE = ("One thing we couldn't tell from your CV - could you also confirm "
            "{gaps} when you reply?\n\n")


def _short_label(crit: dict, cid: str) -> str:
    """A short human phrase for a criterion.

    The first draft pasted whole criterion descriptions into the sentence and
    read like a form letter written by a machine. Criteria are written for
    screening, not for reading aloud to a candidate.
    """
    if crit.get("short"):
        return str(crit["short"])
    KNOWN = {"llm": "LLMs", "llms": "LLMs", "ai": "AI", "ml": "ML", "api": "APIs",
             "sql": "SQL", "aws": "AWS", "gcp": "GCP", "nlp": "NLP",
             "python": "Python", "java": "Java", "ist": "Indian hours"}
    PHRASES = {"timezone ist": "your location",
               "cloud or containers": "cloud and containers",
               "production deployment": "shipping to production"}
    raw = cid.replace("_", " ").strip()
    if raw in PHRASES:
        return PHRASES[raw]
    raw = raw.replace("proficiency", "").replace("experience", "").strip()
    if raw in PHRASES:
        return PHRASES[raw]
    words = [KNOWN.get(w.lower(), w) for w in raw.split()]
    if not words:
        return cid
    if words[0].islower():
        words[0] = words[0].capitalize()
    return " ".join(words)


def _first_name(full: str | None) -> str:
    if not full:
        return "there"
    part = full.strip().split()[0]
    return part.title() if part.isupper() or part.islower() else part


def build_draft(result: RunResult, criteria: list[dict], rules: dict) -> EmailDraft:
    """Render the invitation and decide whether it is allowed to be sent."""
    cfg = SETTINGS.get("email", {}) or {}
    min_tier = Verdict(rules.get("email_min_tier", "GREAT_FIT"))
    by_id = {c["id"]: c for c in criteria}

    tier_ok = TIER_ORDER.get(result.verdict, -1) >= TIER_ORDER.get(min_tier, 2)
    address = (result.profile.email or "").strip()
    address_ok = bool(address and EMAIL_RE.match(address))

    met = [a for a in result.assessments
           if a.status.value == "MET" and a.evidence_verified is not False]
    labels = [_short_label(by_id.get(a.criterion_id, {}), a.criterion_id) for a in met[:3]]
    if len(labels) > 1:
        highlights = ", ".join(labels[:-1]) + " and " + labels[-1]
    else:
        highlights = labels[0] if labels else "your background"

    gaps = [_short_label(by_id.get(a.criterion_id, {}), a.criterion_id)
            for a in result.assessments if a.status.value == "NOT_STATED"]

    body = TEMPLATE.format(
        first_name=_first_name(result.profile.name),
        role=result.criteria_role or "the role",
        company=cfg.get("company_name", "our team"),
        highlights=highlights,
        duration=cfg.get("call_duration", "30-minute"),
        extra=ASK_LINE.format(gaps=" and ".join(gaps[:2])) if gaps else "",
        sender_name=cfg.get("sender_name", "The hiring team"),
    )

    blocked = None
    if not tier_ok:
        blocked = (f"Only {min_tier.value.replace('_', ' ').title()} candidates can be "
                   f"invited. This one is {result.verdict.value.replace('_', ' ').title()}.")
    elif not address_ok:
        blocked = ("No email address was found in this CV. The system will not guess "
                   "one - add it by hand if you have it.")

    # A public URL has no login, so anyone who opens it could otherwise send
    # mail from the operator's account. A hosted instance is ALWAYS dry-run,
    # whatever config.yaml says. This cannot be overridden by configuration -
    # only by running the app on your own machine.
    hosted = bool(os.environ.get("RENDER") or os.environ.get("DEMO_MODE")
                  or os.environ.get("SPACE_ID") or os.environ.get("RAILWAY_ENVIRONMENT"))

    return EmailDraft(
        to=address if address_ok else None,
        subject=cfg.get("subject", "Interview - {role} at {company}").format(
            role=result.criteria_role or "the role",
            company=cfg.get("company_name", "our team")),
        body=body,
        can_send=blocked is None,
        blocked_reason=blocked,
        dry_run=hosted or not bool(cfg.get("send_email", False)),
    )


def send(draft: EmailDraft, run_id: str) -> EmailDraft:
    """Actually send. Only ever called from an explicit human action."""
    if not draft.can_send:
        raise ValueError(draft.blocked_reason or "This draft is not allowed to be sent.")

    cfg = SETTINGS.get("email", {}) or {}
    log = ROOT / "data" / "sent_emails.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")

    if draft.dry_run:
        log.open("a", encoding="utf-8").write(
            f"\n===== DRY RUN {stamp} run={run_id} =====\n"
            f"To: {draft.to}\nSubject: {draft.subject}\n\n{draft.body}\n")
        draft.sent, draft.sent_at = True, stamp
        return draft

    secrets = Secrets()
    if not (secrets.smtp_host and secrets.smtp_user and secrets.smtp_password):
        raise ValueError(
            "Sending is switched on, but there are no mail credentials. Add "
            "SMTP_HOST, SMTP_USER and SMTP_PASSWORD to .env - or set "
            "email.send_email back to false in config.yaml to stay in dry-run.")

    msg = EmailMessage()
    msg["From"] = f"{cfg.get('sender_name', 'Hiring')} <{secrets.smtp_user}>"
    msg["To"] = draft.to
    msg["Subject"] = draft.subject
    if cfg.get("reply_to"):
        msg["Reply-To"] = cfg["reply_to"]
    msg.set_content(draft.body)

    with smtplib.SMTP(secrets.smtp_host, secrets.smtp_port, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(secrets.smtp_user, secrets.smtp_password)
        smtp.send_message(msg)

    log.open("a", encoding="utf-8").write(
        f"\n===== SENT {stamp} run={run_id} to={draft.to} =====\n"
        f"Subject: {draft.subject}\n\n{draft.body}\n")
    draft.sent, draft.sent_at = True, stamp
    return draft
