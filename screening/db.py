"""Stage 8 - RECORD. SQLite, one file, no server.

The `assessments` table is not plumbing. It is the evaluation dataset, the audit
trail and the human-intervention metric, produced automatically by normal use.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from screening.config import ROOT
from screening.schemas import RunResult

DB_PATH = ROOT / "data" / "screening.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY, started_at TEXT, finished_at TEXT,
  source_file TEXT, source_sha256 TEXT, criteria_role TEXT,
  status TEXT, verdict TEXT, verdict_reason TEXT, next_action TEXT,
  model TEXT, input_tokens INT, output_tokens INT, est_cost_usd REAL,
  latency_ms INT, retries INT, llm_calls INT,
  error_code TEXT, error_message TEXT, payload TEXT
);
CREATE TABLE IF NOT EXISTS assessments (
  run_id TEXT, criterion_id TEXT, status TEXT,
  evidence_quote TEXT, evidence_verified INT, verification_method TEXT,
  evidence_strength TEXT, confidence REAL, needs_review INT, review_reason TEXT,
  human_action TEXT, human_status TEXT, human_note TEXT, human_at TEXT,
  PRIMARY KEY (run_id, criterion_id)
);
CREATE TABLE IF NOT EXISTS emails (
  run_id TEXT PRIMARY KEY, recipient TEXT, subject TEXT, body TEXT,
  tier TEXT, dry_run INT, sent INT, sent_at TEXT, approved_by_human INT
);
CREATE TABLE IF NOT EXISTS exceptions (
  run_id TEXT, type TEXT, field TEXT, detail TEXT, severity TEXT, resolved INT
);
CREATE INDEX IF NOT EXISTS idx_runs_started ON runs(started_at);
CREATE INDEX IF NOT EXISTS idx_runs_hash    ON runs(source_sha256);
"""


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init() -> None:
    with connect() as c:
        c.executescript(SCHEMA)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def seen_hashes() -> set[str]:
    with connect() as c:
        return {r[0] for r in c.execute(
            "SELECT source_sha256 FROM runs WHERE status='completed'")}


def _norm_email(addr: str | None) -> str:
    """Normalise for comparison. Gmail ignores dots and +suffixes, so
    'shreya.j+jobs@gmail.com' and 'shreyaj@gmail.com' are the same inbox."""
    if not addr:
        return ""
    addr = addr.strip().lower()
    if "@" not in addr:
        return ""
    local, domain = addr.rsplit("@", 1)
    local = local.split("+", 1)[0]
    if domain in ("gmail.com", "googlemail.com"):
        local = local.replace(".", "")
        domain = "gmail.com"
    return f"{local}@{domain}"


def find_prior_applications(email: str | None, name: str | None,
                            exclude_run_id: str = "") -> list[dict]:
    """Has this PERSON been screened before, under any file?

    The content hash only catches the identical file. Candidates routinely
    submit a tweaked CV, which produces a different hash and slipped straight
    through - found in real use with two versions of the same person's CV.
    Identity is matched on the email address extracted from the document, with
    an exact full-name match as a weaker fallback.
    """
    target = _norm_email(email)
    nm = (name or "").strip().lower()
    if not target and not nm:
        return []

    out = []
    with connect() as c:
        rows = c.execute(
            """SELECT run_id, started_at, source_file, verdict, payload
               FROM runs
               WHERE status='completed' AND run_id != ?
               ORDER BY started_at DESC LIMIT 400""", (exclude_run_id,)).fetchall()
    for r in rows:
        try:
            prof = (json.loads(r["payload"]).get("profile") or {})
        except Exception:
            continue
        match = None
        if target and _norm_email(prof.get("email")) == target:
            match = "email"
        elif nm and (prof.get("name") or "").strip().lower() == nm:
            match = "name"
        if match:
            out.append({"run_id": r["run_id"], "when": r["started_at"][:10],
                        "file": r["source_file"], "verdict": r["verdict"],
                        "matched_on": match})
    return out


def save(result: RunResult, started_at: str) -> None:
    m = result.meta
    with connect() as c:
        c.execute("""INSERT OR REPLACE INTO runs VALUES
                     (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
            result.run_id, started_at, now(), result.source_file, result.source_sha256,
            result.criteria_role, "failed" if result.error_code else "completed",
            result.verdict.value, result.verdict_reason, result.next_action,
            m.model, m.input_tokens, m.output_tokens, m.est_cost_usd,
            m.latency_ms, m.retries, m.llm_calls,
            result.error_code, result.error_message, json.dumps(result.to_dict()),
        ))
        for a in result.assessments:
            c.execute("""INSERT OR REPLACE INTO assessments
                         (run_id,criterion_id,status,evidence_quote,evidence_verified,
                          verification_method,evidence_strength,confidence,
                          needs_review,review_reason)
                         VALUES (?,?,?,?,?,?,?,?,?,?)""", (
                result.run_id, a.criterion_id, a.status.value, a.evidence_quote,
                None if a.evidence_verified is None else int(a.evidence_verified),
                a.verification_method, a.evidence_strength.value, a.confidence,
                int(a.needs_review), a.review_reason))
        c.execute("DELETE FROM exceptions WHERE run_id=?", (result.run_id,))
        for e in result.exceptions:
            c.execute("INSERT INTO exceptions VALUES (?,?,?,?,?,?)",
                      (result.run_id, e.type, e.field, e.detail, e.severity, int(e.resolved)))


def record_email(run_id: str, draft, tier: str, approved: bool) -> None:
    with connect() as c:
        c.execute("""INSERT OR REPLACE INTO emails VALUES (?,?,?,?,?,?,?,?,?)""",
                  (run_id, draft.to, draft.subject, draft.body, tier,
                   int(draft.dry_run), int(draft.sent), draft.sent_at, int(approved)))


def email_already_sent(run_id: str) -> bool:
    with connect() as c:
        row = c.execute("SELECT sent FROM emails WHERE run_id=?", (run_id,)).fetchone()
        return bool(row and row["sent"])


def record_decision(run_id: str, criterion_id: str, action: str,
                    new_status: str | None = None, note: str | None = None) -> None:
    """Every human override is logged: what the system said, what she said, when."""
    with connect() as c:
        c.execute("""UPDATE assessments
                     SET human_action=?, human_status=?, human_note=?, human_at=?
                     WHERE run_id=? AND criterion_id=?""",
                  (action, new_status, note, now(), run_id, criterion_id))


def get_run(run_id: str) -> dict | None:
    with connect() as c:
        row = c.execute("SELECT payload FROM runs WHERE run_id=?", (run_id,)).fetchone()
        return json.loads(row["payload"]) if row else None


def list_runs(limit: int = 100) -> list[dict]:
    with connect() as c:
        return [dict(r) for r in c.execute(
            """SELECT run_id, started_at, source_file, verdict, status,
                      latency_ms, est_cost_usd, error_code
               FROM runs ORDER BY started_at DESC LIMIT ?""", (limit,))]
