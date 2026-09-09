"""Print all 12 cases with their evidence, compactly, for one-pass review.

    python eval/review.py                 # show everything
    python eval/review.py --accept-all    # mark every case verified as-is
    python eval/review.py --fix R1_priya:skill_python=NOT_STATED,location=MET

Faster than eval/label.py when you want to scan the whole set at once and only
correct the handful that are wrong. Your call on each line is what makes the
evaluation mean anything - accepting a line IS a judgment, as long as you have
actually read the evidence next to it.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from sift.config import load_criteria   # noqa: E402

GT = ROOT / "eval" / "ground_truth.json"
CASES = ROOT / "eval" / "cases"
MARK = {"MET": "YES", "NOT_MET": "NO ", "NOT_STATED": "?  "}


def show() -> int:
    truth = json.loads(GT.read_text())
    specs = {c["id"]: c for c in load_criteria()["criteria"]}

    for cid, t in sorted(truth.items()):
        flag = "verified" if t.get("verified_by_human") else "NOT CHECKED"
        print(f"\n{'='*78}\n  {cid}   ({t['type']})   [{flag}]")
        print(f"  file: {t['file']}")

        if t.get("expected_error_code"):
            print(f"  -> should be REJECTED before assessment: {t['expected_error_code']}")
            continue

        ev = t.get("evidence") or {}
        for k, v in (t.get("expected_status") or {}).items():
            label = specs.get(k, {}).get("short") or k.replace("skill_", "")
            quote = ev.get(k) or ""
            print(f"    {MARK.get(v,'?  ')}  {label:<22} {quote[:46]}")
        print(f"    => {t.get('expected_verdict')}")
    print(f"\n{'='*78}")
    n = sum(1 for v in truth.values() if v.get("verified_by_human"))
    print(f"  {n}/{len(truth)} verified")
    print("\n  To correct:  python eval/review.py --fix CASE:criterion=STATUS,...")
    print("  To accept:   python eval/review.py --accept-all")
    return 0


def fix(spec: str) -> int:
    truth = json.loads(GT.read_text())
    for block in spec.split(";"):
        block = block.strip()
        if not block:
            continue
        case, _, pairs = block.partition(":")
        case = case.strip()
        if case not in truth:
            print(f"  no such case: {case}")
            return 1
        for pair in pairs.split(","):
            k, _, v = pair.partition("=")
            k, v = k.strip(), v.strip().upper()
            if v not in ("MET", "NOT_MET", "NOT_STATED",
                         "GREAT_FIT", "MEDIUM_FIT", "LOW_FIT"):
                print(f"  bad value: {v}")
                return 1
            if k == "verdict":
                truth[case]["expected_verdict"] = v
            else:
                truth[case].setdefault("expected_status", {})[k] = v
            print(f"  {case}: {k} -> {v}")
        truth[case]["verified_by_human"] = True
    GT.write_text(json.dumps(truth, indent=2))
    return 0


def accept_all() -> int:
    truth = json.loads(GT.read_text())
    for v in truth.values():
        v["verified_by_human"] = True
        v.pop("note", None)
    GT.write_text(json.dumps(truth, indent=2))
    print(f"  {len(truth)}/{len(truth)} marked verified.")
    print("  Only do this if you have actually read the evidence for each one -")
    print("  otherwise the evaluation is the system agreeing with itself.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--accept-all", action="store_true")
    ap.add_argument("--fix", default=None)
    a = ap.parse_args()
    if not GT.exists():
        print("No ground truth yet - seeding may still be running.")
        raise SystemExit(1)
    raise SystemExit(accept_all() if a.accept_all else fix(a.fix) if a.fix else show())
