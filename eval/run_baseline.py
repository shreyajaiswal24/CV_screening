"""Arm B - a plain LLM with one good prompt, and nothing around it.

    python eval/run_baseline.py

This is the honest competitor. It uses the SAME model as the system, with a
single well-written prompt that explicitly asks for evidence and for gaps to be
flagged. Running it through the same model rather than pasting into a chat
window is deliberate: it isolates what the SYSTEM adds, instead of confounding
that with a difference between two models. It is also reproducible, which a
chat transcript is not.

What it measures, per case:
  - could the output be parsed into a consistent shape at all?
  - is every quote actually present in the CV?          <- fabrication
  - was anything the CV is silent about answered anyway? <- gap filling
  - time and tokens
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sift.config import load_criteria          # noqa: E402
from sift.ingest import extract_text           # noqa: E402
from sift.llm import call_json                 # noqa: E402
from sift.verify import verify_quote           # noqa: E402

GT = ROOT / "eval" / "ground_truth.json"
CASES = ROOT / "eval" / "cases"

PROMPT = """I am screening candidates for a role. My criteria are:

{criteria}

Read the CV below and, for each criterion, tell me whether the candidate meets
it, quote the line from the CV that proves it, and say clearly if the CV does
not mention it. Then give an overall verdict and what I should do next.

Reply in json with this shape:
{{"assessments":[{{"criterion":"...","meets":"yes|no|not stated",
"quote":"...","reason":"..."}}],"verdict":"...","next_action":"..."}}

CV:
{cv}"""


def main() -> int:
    cfg = load_criteria()
    crit_text = "\n".join(
        f"{i}. {c['description']}" + ("  [REQUIRED]" if c.get("required") else "")
        for i, c in enumerate(cfg["criteria"], 1))

    truth = json.loads(GT.read_text()) if GT.exists() else {}
    cases = sorted(p for p in CASES.glob("*.txt"))
    rows = []

    for path in cases:
        cid = path.stem
        t = truth.get(cid, {})
        print(f"  {cid} …", flush=True)

        # A chat window cannot refuse a file it cannot read - it just tries.
        # The system rejects these before spending anything; the baseline does not.
        try:
            cv_text, _, _ = extract_text(path)
        except Exception as e:
            rows.append({"case": cid, "error": f"could not read: {e}"})
            continue

        t0 = time.time()
        try:
            payload, usage = call_json(
                "You are helping screen job candidates. Reply only in json.",
                PROMPT.format(criteria=crit_text, cv=cv_text))
            err = None
        except Exception as e:
            payload, usage, err = {}, None, str(e)[:120]

        elapsed = int((time.time() - t0) * 1000)
        items = payload.get("assessments") or []

        fabricated, gap_filled, shape_ok = 0, 0, bool(items)
        expected = t.get("expected_status") or {}
        should_be_silent = sum(1 for v in expected.values() if v == "NOT_STATED")
        answered_anyway = 0

        for a in items:
            q = (a or {}).get("quote") or None
            if q and str(q).strip().lower() not in ("n/a", "none", "not stated", ""):
                ok, _, _ = verify_quote(str(q), cv_text)
                if not ok:
                    fabricated += 1
            meets = str((a or {}).get("meets", "")).lower()
            if "not stated" not in meets and not q:
                gap_filled += 1

        # how many criteria the CV is silent about did it answer yes/no to anyway?
        for a in items:
            meets = str((a or {}).get("meets", "")).lower()
            if meets in ("yes", "no"):
                q = (a or {}).get("quote")
                if not q:
                    answered_anyway += 1

        rows.append({
            "case": cid, "error": err, "shape_ok": shape_ok,
            "n_assessments": len(items),
            "fabricated_quotes": fabricated,
            "answered_without_evidence": answered_anyway,
            "silent_criteria_in_cv": should_be_silent,
            "latency_ms": elapsed,
            "tokens": (usage.input_tokens + usage.output_tokens) if usage else 0,
            "cost_usd": usage.est_cost_usd if usage else 0.0,
            "recorded_decision": False,   # a chat reply is not a record
        })

    out = ROOT / "eval" / "results_baseline_b.json"
    out.write_text(json.dumps(rows, indent=2))

    ok = [r for r in rows if not r.get("error")]
    n = len(ok) or 1
    print(f"\n{'='*60}\n  ARM B - plain LLM, one prompt, no system\n{'='*60}")
    print(f"  cases run              {len(ok)}/{len(rows)}")
    print(f"  parsable output        {sum(1 for r in ok if r['shape_ok'])}/{len(ok)}")
    print(f"  FABRICATED quotes      {sum(r['fabricated_quotes'] for r in ok)}")
    print(f"  answered with no proof {sum(r['answered_without_evidence'] for r in ok)}")
    print(f"  decisions recorded     0/{len(ok)}   (a chat reply is not a record)")
    lat = sorted(r["latency_ms"] for r in ok) or [0]
    print(f"  median latency         {lat[len(lat)//2]}ms")
    print(f"  total tokens           {sum(r['tokens'] for r in ok)}")
    print(f"  total cost             ${sum(r['cost_usd'] for r in ok):.4f}")
    print(f"\n  Saved {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
