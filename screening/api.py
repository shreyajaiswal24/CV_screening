"""FastAPI app + static UI. The only interface a non-developer needs."""
from __future__ import annotations

import re
import shutil
import tempfile
import traceback
from pathlib import Path

import yaml
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from screening import db
from screening.config import ROOT, SETTINGS, Secrets, load_criteria, output_dir, windows_path
from screening.graph import process_one
from screening.observability import enabled as tracing_enabled

app = FastAPI(title="CV Screening", docs_url="/api/docs")
STATIC = ROOT / "static"


@app.on_event("startup")
def _startup() -> None:
    db.init()


@app.exception_handler(Exception)
async def _unhandled(request, exc):
    traceback.print_exc()
    return JSONResponse(status_code=500, content={
        "error_code": "UNEXPECTED_ERROR",
        "error_message": f"Something went wrong: {exc}. "
                         f"The details are in the terminal window where you started the app.",
    })


# ---------------------------------------------------------------- health

def _clean_error(exc: Exception) -> str:
    """Strip validation-library noise so the user sees only the instruction."""
    text = str(exc)
    m = re.search(r"Value error,\s*(.+?)(?:\s*\[type=|$)", text, flags=re.DOTALL)
    if m:
        return m.group(1).strip()
    return text.split("\n[")[0].strip()


@app.get("/api/health")
def health():
    problems = []
    try:
        Secrets()
    except Exception as e:
        problems.append(_clean_error(e))
    try:
        cfg = load_criteria()
        role, n = cfg.get("role", ""), len(cfg["criteria"])
    except Exception as e:
        problems.append(_clean_error(e))
        role, n = "", 0
    return {"ok": not problems, "problems": problems, "role": role,
            "criteria_count": n, "model": SETTINGS["model"],
            "tracing": tracing_enabled(),
            "drive_configured": bool(SETTINGS.get("drive_folder_id")),
            "sheet_configured": bool(SETTINGS.get("results_sheet_id"))}


# ---------------------------------------------------------------- criteria

@app.get("/api/criteria")
def get_criteria():
    return load_criteria()


class CriteriaPayload(BaseModel):
    role: str
    summary: str = ""
    filters: dict = {}
    criteria: list[dict] = []
    decision_rules: dict = {}


@app.put("/api/criteria")
def put_criteria(payload: CriteriaPayload):
    """Lets the user change what she is screening for, without a developer."""
    from screening.filters import compile_criteria

    data = payload.model_dump()
    if payload.filters:
        data["criteria"] = compile_criteria(payload.role, payload.filters, payload.summary)
    if not data["criteria"]:
        raise HTTPException(
            400, "Add at least one thing to screen for - a skill, a number of "
                 "years, or a location.")
    payload = CriteriaPayload(**data)

    path = ROOT / "criteria.yaml"
    backup = ROOT / "criteria.backup.yaml"
    if path.exists():
        shutil.copy(path, backup)
    out = payload.model_dump()
    with open(path, "w") as f:
        f.write("# Written by the CV Screening criteria editor. 'filters' is the source of\n"
                "# truth; 'criteria' below is generated from it.\n")
        yaml.safe_dump(out, f, sort_keys=False, allow_unicode=True)
    return {"ok": True, "saved_to": str(path), "criteria_count": len(out["criteria"])}


# ---------------------------------------------------------------- screening

@app.post("/api/screen")
async def screen(file: UploadFile = File(...)):
    suffix = Path(file.filename or "cv.txt").suffix or ".txt"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name
    try:
        # Pass the real filename IN - patching it after the run saved the temp
        # name to the log, which made the audit trail useless.
        result = process_one(tmp_path, original_name=file.filename)
        return result.to_dict()
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@app.post("/api/scan-drive")
def scan_drive():
    folder = SETTINGS.get("drive_folder_id")
    if not folder:
        raise HTTPException(400, "No Google Drive folder is configured. "
                                 "Add drive_folder_id to config.yaml, or upload files directly.")
    from screening.integrations.gdrive import list_cvs
    return {"files": list_cvs(folder, db.seen_hashes())}


class DriveRun(BaseModel):
    file_id: str
    name: str


@app.post("/api/screen-drive")
def screen_drive(item: DriveRun):
    from screening.integrations.gdrive import download
    path = download(item.file_id, item.name)
    try:
        result = process_one(str(path), original_name=item.name)
        return result.to_dict()
    finally:
        Path(path).unlink(missing_ok=True)


# ---------------------------------------------------------------- human decisions

class Decision(BaseModel):
    run_id: str
    criterion_id: str
    action: str                     # approved | edited | overridden
    new_status: str | None = None
    note: str | None = None


@app.post("/api/decision")
def decision(d: Decision):
    if d.action not in {"approved", "edited", "overridden"}:
        raise HTTPException(400, "action must be approved, edited or overridden")
    db.record_decision(d.run_id, d.criterion_id, d.action, d.new_status, d.note)
    return {"ok": True}


# ---------------------------------------------------------------- invitations

class SendEmail(BaseModel):
    run_id: str
    to: str | None = None          # human may correct a missing/wrong address
    subject: str | None = None
    body: str | None = None
    confirm: bool = False          # must be explicitly true


@app.post("/api/email/send")
def send_email(payload: SendEmail):
    """Send one interview invitation. Four gates, all enforced here.

    This is the only outward-facing, irreversible action in the system, so it
    is deliberately awkward: one candidate at a time, explicit confirm, and a
    refusal to send twice for the same run.
    """
    from screening.emailer import build_draft, send as do_send

    if not payload.confirm:
        raise HTTPException(400, "Nothing was sent - the confirm flag was not set.")

    stored = db.get_run(payload.run_id)
    if not stored:
        raise HTTPException(404, "No such screening run.")
    if db.email_already_sent(payload.run_id):
        raise HTTPException(409, "An invitation was already sent to this candidate. "
                                 "Sending a second one would be a duplicate.")

    from screening.schemas import RunResult
    result = RunResult.model_validate(stored)
    cfg = load_criteria()
    draft = build_draft(result, cfg["criteria"], cfg.get("decision_rules", {}))

    # A human may fix the address or edit the wording; the tier gate still holds.
    if payload.to:
        draft.to = payload.to.strip()
        if draft.blocked_reason and "No email address" in draft.blocked_reason:
            draft.can_send, draft.blocked_reason = True, None
    if payload.subject:
        draft.subject = payload.subject
    if payload.body:
        draft.body = payload.body

    if not draft.can_send:
        raise HTTPException(403, draft.blocked_reason or "This candidate cannot be invited.")

    try:
        draft = do_send(draft, payload.run_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(502, f"The mail server rejected the message: {e}")

    db.record_email(payload.run_id, draft, result.verdict.value, approved=True)
    return {"ok": True, "sent": True, "dry_run": draft.dry_run,
            "to": draft.to, "sent_at": draft.sent_at,
            "message": ("Draft logged to data/sent_emails.log (dry run - nothing was "
                        "actually sent)." if draft.dry_run
                        else f"Invitation sent to {draft.to}.")}


# ---------------------------------------------------------------- export

class ExportPayload(BaseModel):
    run_ids: list[str]


@app.post("/api/export")
def export(payload: ExportPayload):
    sheet = SETTINGS.get("results_sheet_id")
    rows = [db.get_run(r) for r in payload.run_ids]
    rows = [r for r in rows if r]
    if not rows:
        raise HTTPException(400, "Nothing to export.")
    if not sheet:
        out = output_dir() / "shortlist.csv"
        from screening.integrations.gsheets import write_csv
        _, written, skipped = write_csv(rows, out)
        return {"ok": True, "destination": "csv", "path": windows_path(out),
                "rows": written, "skipped": skipped}
    from screening.integrations.gsheets import append_rows
    written, skipped = append_rows(sheet, rows)
    return {"ok": True, "destination": "google_sheet",
            "url": f"https://docs.google.com/spreadsheets/d/{sheet}",
            "rows": written, "skipped": skipped}


# ---------------------------------------------------------------- history

@app.get("/api/runs")
def runs(limit: int = 100):
    return {"runs": db.list_runs(limit)}


@app.get("/api/runs/{run_id}")
def run(run_id: str):
    r = db.get_run(run_id)
    if not r:
        raise HTTPException(404, "No such run.")
    return r


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
