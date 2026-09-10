"""One command produces every number in the case study.

    python eval/run_eval.py --seed            # create a ground-truth template
    python eval/run_eval.py --tag before      # run and score
    python eval/run_eval.py --tag after
    python eval/run_eval.py --compare before after

Ground truth must be verified by a human. A case whose ground truth still has
"verified_by_human": false is EXCLUDED from the score - grading a system against
its own output measures nothing. The seed mode exists to save typing, not to
supply the answers.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from screening.config import load_criteria          # noqa: E402
from screening.graph import process_one             # noqa: E402

CASES_DIR = ROOT / "eval" / "cases"
GT_PATH = ROOT / "eval" / "ground_truth.json"

RUBRIC = ["schema_valid", "evidence_verified", "no_fabrication", "correct_status",
          "gaps_flagged", "verdict_correct", "action_usable"]
CRITICAL = {"no_fabrication", "gaps_flagged"}


# ----------------------------------------------------------------- seeding

def seed() -> int:
    """Run every case once and write a ground-truth template to fill in by hand."""
    cases = sorted(CASES_DIR.glob("*.txt"))
    criteria = load_criteria()["criteria"]
    existing = json.loads(GT_PATH.read_text()) if GT_PATH.exists() else {}
    out = {}
    for path in cases:
        cid = path.stem
        print(f"  seeding {cid} …", flush=True)
        r = process_one(str(path), save=False)
        # Only carry values forward when a HUMAN verified them. The first
        # version preserved everything, so a re-seed after the criteria changed
        # faithfully kept stale machine output - old criterion ids, old verdict
        # names - and would have scored the system against a vocabulary it no
        # longer speaks. Unverified entries are regenerated from scratch.
        prior = existing.get(cid, {}) if existing.get(cid, {}).get("verified_by_human") else {}
        out[cid] = {
            "file": path.name,
            "type": ("failure" if cid.startswith("F")
                     else "edge" if cid.startswith("E") else "representative"),
            "verified_by_human": prior.get("verified_by_human", False),
            "note": prior.get("note", "CHECK EVERY FIELD BELOW AGAINST THE CV, "
                                      "THEN SET verified_by_human TO true"),
            "expected_error_code": prior.get("expected_error_code", r.error_code),
            "expected_verdict": prior.get("expected_verdict",
                                          r.verdict.value if not r.error_code else None),
            "expected_status": prior.get("expected_status", {
                a.criterion_id: a.status.value for a in r.assessments}
                or {c["id"]: None for c in criteria}),
            "expected_flags": prior.get("expected_flags",
                                        sorted({e.type for e in r.exceptions})),
            # keep the quote the system used, so a reviewer can check the
            # judgment without re-running the case
            "evidence": {a.criterion_id: a.evidence_quote
                         for a in r.assessments if a.evidence_quote},
        }
    GT_PATH.write_text(json.dumps(out, indent=2))
    print(f"\nWrote {GT_PATH} with {len(out)} cases.")
    print("NOW: open it, check every value against the CV, and set "
          "verified_by_human to true. Unverified cases are excluded from scoring.")
    return 0


# ----------------------------------------------------------------- grading

def grade(result, truth: dict) -> tuple[bool, dict, list[str]]:
    checks, notes = {}, []

    if truth.get("expected_error_code"):
        ok = result.error_code == truth["expected_error_code"]
        if not ok:
            notes.append(f"expected error {truth['expected_error_code']}, got {result.error_code}")
        return ok, {c: ok for c in RUBRIC}, notes

    if result.error_code:
        notes.append(f"unexpected error: {result.error_code}")
        return False, {c: False for c in RUBRIC}, notes

    by_id = {a.criterion_id: a for a in result.assessments}
    exp = truth.get("expected_status") or {}

    checks["schema_valid"] = bool(result.assessments) and all(
        a.status.value in {"MET", "NOT_MET", "NOT_STATED"} for a in result.assessments)

    checks["evidence_verified"] = all(
        a.evidence_verified is not False for a in result.assessments)

    checks["no_fabrication"] = not any(
        a.verification_method == "not_found" for a in result.assessments)
    if not checks["no_fabrication"]:
        notes.append("FABRICATED: " + ", ".join(
            a.criterion_id for a in result.assessments if a.verification_method == "not_found"))

    wrong = [cid for cid, want in exp.items()
             if want and (cid not in by_id or by_id[cid].status.value != want)]
    checks["correct_status"] = not wrong
    if wrong:
        notes.append("status mismatch: " + ", ".join(
            f"{c}(want {exp[c]}, got {by_id[c].status.value if c in by_id else 'missing'})"
            for c in wrong))

    should_be_ns = [cid for cid, want in exp.items() if want == "NOT_STATED"]
    checks["gaps_flagged"] = all(
        cid in by_id and by_id[cid].status.value == "NOT_STATED" for cid in should_be_ns)
    if not checks["gaps_flagged"]:
        notes.append("GAP FILLED: inferred a fact the CV does not state")

    checks["verdict_correct"] = (not truth.get("expected_verdict")
                                 or result.verdict.value == truth["expected_verdict"])
    if not checks["verdict_correct"]:
        notes.append(f"verdict {result.verdict.value}, expected {truth['expected_verdict']}")

    checks["action_usable"] = bool(result.next_action and len(result.next_action) > 15)

    passed = all(checks[c] for c in CRITICAL) and sum(checks.values()) >= 6
    return passed, checks, notes


# ----------------------------------------------------------------- running

def run(tag: str) -> int:
    if not GT_PATH.exists():
        print("No ground truth. Run:  python eval/run_eval.py --seed")
        return 1
    truth = json.loads(GT_PATH.read_text())
    verified = {k: v for k, v in truth.items() if v.get("verified_by_human")}
    skipped = [k for k in truth if k not in verified]

    if not verified:
        print("No ground truth has been verified by a human yet.")
        print(f"Open {GT_PATH}, check each case against its CV, set "
              f"verified_by_human to true, then re-run.")
        return 1

    rows = []
    for cid, t in sorted(verified.items()):
        path = CASES_DIR / t["file"]
        t0 = time.time()
        r = process_one(str(path), save=False)
        passed, checks, notes = grade(r, t)
        rows.append({
            "case": cid, "type": t["type"], "passed": passed, "checks": checks,
            "notes": notes,
            "latency_ms": int((time.time() - t0) * 1000),
            "cost_usd": r.meta.est_cost_usd,
            "tokens": r.meta.input_tokens + r.meta.output_tokens,
            "retries": r.meta.retries,
            "verdict": r.verdict.value, "error": r.error_code,
            "needs_review": sum(1 for a in r.assessments if a.needs_review),
            "verification_methods": [a.verification_method for a in r.assessments
                                     if a.evidence_quote],
        })
        print(f"  {'PASS' if passed else 'FAIL'}  {cid:<24} {r.verdict.value:<9} "
              f"{rows[-1]['latency_ms']:>6}ms" + (f"   {notes[0]}" if notes else ""))

    report(rows, tag, skipped)
    out = ROOT / "eval" / f"results_{tag}.json"
    out.write_text(json.dumps(rows, indent=2))
    print(f"\nSaved {out}")
    return 0


def report(rows: list[dict], tag: str, skipped: list[str]) -> None:
    n = len(rows)
    lat = sorted(r["latency_ms"] for r in rows)
    methods = [m for r in rows for m in r["verification_methods"]]

    print(f"\n{'='*62}\n  RESULTS: {tag}   ({n} verified cases)\n{'='*62}")
    print(f"  PASS RATE            {sum(r['passed'] for r in rows)}/{n}"
          f"  ({sum(r['passed'] for r in rows)/n:.0%})")
    print("\n  Rubric breakdown")
    for c in RUBRIC:
        hits = sum(r["checks"].get(c, False) for r in rows)
        star = " *critical*" if c in CRITICAL else ""
        print(f"    {c:<20} {hits}/{n}{star}")
    print("\n  By case type")
    for t in ("representative", "edge", "failure"):
        sub = [r for r in rows if r["type"] == t]
        if sub:
            print(f"    {t:<16} {sum(r['passed'] for r in sub)}/{len(sub)}")
    print("\n  Speed / cost")
    print(f"    p50 latency        {lat[n//2]}ms")
    print(f"    p95 latency        {lat[min(n-1, int(n*0.95))]}ms")
    print(f"    max latency        {lat[-1]}ms")
    print(f"    mean cost/CV       ${statistics.mean(r['cost_usd'] for r in rows):.5f}")
    print(f"    total cost         ${sum(r['cost_usd'] for r in rows):.4f}")
    print(f"    total retries      {sum(r['retries'] for r in rows)}")
    print("\n  Human intervention")
    flagged = sum(r["needs_review"] for r in rows)
    clean = sum(1 for r in rows if r["needs_review"] == 0 and not r["error"])
    print(f"    criteria flagged for review   {flagged}")
    print(f"    candidates needing no edits   {clean}/{n}")
    if methods:
        print("\n  Quote verification tiers")
        for m in ("exact", "normalised", "despaced", "fuzzy", "not_found"):
            c = methods.count(m)
            if c:
                print(f"    {m:<12} {c}/{len(methods)}  ({c/len(methods):.0%})")
    if skipped:
        print(f"\n  EXCLUDED (ground truth not human-verified): {', '.join(sorted(skipped))}")


def compare(a: str, b: str) -> int:
    pa = ROOT / "eval" / f"results_{a}.json"
    pb = ROOT / "eval" / f"results_{b}.json"
    if not (pa.exists() and pb.exists()):
        print("Run both tags first.")
        return 1
    ra = {r["case"]: r for r in json.loads(pa.read_text())}
    rb = {r["case"]: r for r in json.loads(pb.read_text())}
    print(f"\n  {'case':<24} {a:>10} {b:>10}   change")
    print("  " + "-" * 58)
    for cid in sorted(set(ra) | set(rb)):
        x = "PASS" if ra.get(cid, {}).get("passed") else "fail"
        y = "PASS" if rb.get(cid, {}).get("passed") else "fail"
        mark = "  fixed" if (x, y) == ("fail", "PASS") else \
               "  REGRESSION" if (x, y) == ("PASS", "fail") else ""
        print(f"  {cid:<24} {x:>10} {y:>10} {mark}")
    print(f"\n  total   {sum(r['passed'] for r in ra.values())}/{len(ra)}"
          f"  ->  {sum(r['passed'] for r in rb.values())}/{len(rb)}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--seed", action="store_true")
    p.add_argument("--tag", default=None)
    p.add_argument("--compare", nargs=2, metavar=("BEFORE", "AFTER"))
    a = p.parse_args()
    if a.seed:
        return seed()
    if a.compare:
        return compare(*a.compare)
    if a.tag:
        return run(a.tag)
    p.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
