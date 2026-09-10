"""Integration 2 - Google Sheets (WRITE).

The output lands in the tracker she already keeps, so results appear where she
already looks. Falls back to a local CSV when no sheet is configured, so the
system is never blocked on a cloud dependency.
"""
from __future__ import annotations

import csv
from pathlib import Path

from screening.config import ROOT, Secrets

SCOPES = ["https://www.googleapis.com/auth/spreadsheets",
          "https://www.googleapis.com/auth/drive.file"]

HEADER = ["Screened at", "Candidate", "File", "Verdict", "Reason", "Next action",
          "Criteria met", "Not stated", "Needs review", "Evidence",
          "Model", "Seconds", "Run ID"]


class SheetError(Exception):
    pass


def _row(r: dict) -> list:
    assessments = r.get("assessments", [])
    met = [a["criterion_id"] for a in assessments if a["status"] == "MET"]
    ns = [a["criterion_id"] for a in assessments if a["status"] == "NOT_STATED"]
    rev = [a["criterion_id"] for a in assessments if a.get("needs_review")]
    ev = " | ".join(f'{a["criterion_id"]}: "{a["evidence_quote"]}"'
                    for a in assessments if a.get("evidence_quote"))
    p = r.get("profile") or {}
    m = r.get("meta") or {}
    return [r.get("run_id", "")[2:17], p.get("name") or "", r.get("source_file", ""),
            r.get("verdict", ""), r.get("verdict_reason", ""), r.get("next_action", ""),
            ", ".join(met), ", ".join(ns), ", ".join(rev), ev[:2000],
            m.get("model", ""), round(m.get("latency_ms", 0) / 1000, 1), r.get("run_id", "")]


def _existing_run_ids_csv(path: Path) -> set[str]:
    if not path.exists():
        return set()
    with open(path, newline="", encoding="utf-8") as f:
        return {r.get("Run ID", "") for r in csv.DictReader(f)}


def write_csv(rows: list[dict], path: Path) -> tuple[Path, int, int]:
    """Append rows, skipping anything already exported.

    Found in use: clicking Export twice appended the same candidates again, so a
    tracker filled with duplicates. Export is now idempotent - a candidate is
    written once, keyed on run_id.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    already = _existing_run_ids_csv(path)
    fresh = [r for r in rows if r.get("run_id") not in already]
    new_file = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(HEADER)
        for r in fresh:
            w.writerow(_row(r))
    return path, len(fresh), len(rows) - len(fresh)


def append_rows(sheet_id: str, rows: list[dict]) -> int:
    try:
        import gspread
        from google.oauth2 import service_account
    except ImportError:
        raise SheetError("Sheets export needs extra packages. Run: pip install gspread google-auth")

    path = ROOT / Secrets().google_credentials_path
    if not path.exists():
        raise SheetError(f"No Google credentials at {path}.")
    creds = service_account.Credentials.from_service_account_file(str(path), scopes=SCOPES)
    try:
        gc = gspread.authorize(creds)
        ws = gc.open_by_key(sheet_id).sheet1
    except Exception as e:
        import json
        email = json.loads(path.read_text()).get("client_email", "the service account")
        raise SheetError(
            f"Can't write to the results sheet. Share it with {email} as an Editor, "
            f"and check results_sheet_id in config.yaml. ({e})")

    values = ws.get_all_values()
    if not values:
        ws.append_row(HEADER)
        already = set()
    else:
        idx = HEADER.index("Run ID")
        already = {r[idx] for r in values[1:] if len(r) > idx}
    fresh = [r for r in rows if r.get("run_id") not in already]
    if fresh:
        ws.append_rows([_row(r) for r in fresh], value_input_option="RAW")
    return len(fresh), len(rows) - len(fresh)


# --------------------------------------------------------------------------
# Excel export
#
# CSV downloads fine but opens in whatever the machine has associated with
# .csv - often Notepad. A real .xlsx always opens in Excel, and lets the
# shortlist carry the formatting a reviewer actually wants: the fit tier
# colour-coded, the evidence readable, and the header frozen while scrolling.

def build_xlsx(rows: list[dict]) -> bytes:
    """Return a formatted Excel workbook of the shortlist."""
    from io import BytesIO

    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "Shortlist"

    head_fill = PatternFill("solid", fgColor="1C4FD8")
    head_font = Font(color="FFFFFF", bold=True, size=11)
    thin = Side(style="thin", color="D9DDE3")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    TIER = {
        "GREAT_FIT":  ("E7F6EE", "0D7A4A", "GREAT FIT"),
        "MEDIUM_FIT": ("FFF5E0", "8A5A00", "MEDIUM FIT"),
        "LOW_FIT":    ("FDECEF", "A52034", "LOW FIT"),
        "BLOCKED":    ("EEF0F3", "5F6875", "COULD NOT ASSESS"),
    }

    ws.append(HEADER)
    for c in ws[1]:
        c.fill, c.font, c.border = head_fill, head_font, border
        c.alignment = Alignment(vertical="center")
    ws.row_dimensions[1].height = 26

    for r in rows:
        ws.append(_row(r))
        row_i = ws.max_row
        verdict = str(r.get("verdict", ""))
        bg, fg, label = TIER.get(verdict, ("FFFFFF", "12151A", verdict))
        for c in ws[row_i]:
            c.border = border
            c.alignment = Alignment(vertical="top", wrap_text=True)
        vc = ws.cell(row=row_i, column=HEADER.index("Verdict") + 1)
        vc.value = label
        vc.fill = PatternFill("solid", fgColor=bg)
        vc.font = Font(color=fg, bold=True)
        vc.alignment = Alignment(vertical="center", horizontal="center")

    widths = {"Screened at": 17, "Candidate": 22, "File": 30, "Verdict": 15,
              "Reason": 46, "Next action": 40, "Criteria met": 26,
              "Not stated": 24, "Needs review": 20, "Evidence": 70,
              "Model": 20, "Seconds": 9, "Run ID": 24}
    for i, name in enumerate(HEADER, start=1):
        ws.column_dimensions[get_column_letter(i)].width = widths.get(name, 18)

    ws.freeze_panes = "A2"                      # header stays put when scrolling
    ws.auto_filter.ref = ws.dimensions          # sort and filter by tier

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
