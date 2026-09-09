"""Walk through the ground truth case by case, so labelling takes 20 minutes
instead of 45 spent scrolling a JSON file.

    python eval/label.py            # only cases not yet verified
    python eval/label.py --all      # revisit everything
    python eval/label.py --case R1_priya

For each criterion it shows what the system said and the quote it used, next to
the CV. You accept or correct. Progress is saved after every case, so you can
stop and come back.

Your judgment here IS the standard the system is measured against. Where you
disagree with it, that disagreement becomes a finding.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sift.config import load_criteria          # noqa: E402
from sift.graph import process_one             # noqa: E402

GT = ROOT / "eval" / "ground_truth.json"
CASES = ROOT / "eval" / "cases"
CHOICES = {"1": "MET", "2": "NOT_MET", "3": "NOT_STATED"}


def show_cv(path: Path, limit: int = 2200) -> None:
    text = path.read_text(encoding="utf-8", errors="replace")
    print("\n" + "─" * 74)
    print(text[:limit] + ("\n… (truncated)" if len(text) > limit else ""))
    print("─" * 74)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--case", default=None)
    args = ap.parse_args()

    if not GT.exists():
        print("No ground truth yet. Run:  python eval/run_eval.py --seed")
        return 1

    truth = json.loads(GT.read_text())
    criteria = {c["id"]: c for c in load_criteria()["criteria"]}

    todo = [k for k, v in sorted(truth.items())
            if args.all or not v.get("verified_by_human")]
    if args.case:
        todo = [args.case] if args.case in truth else []
    if not todo:
        print("Everything is already verified. Run:  python eval/run_eval.py --tag before")
        return 0

    print(f"\n{len(todo)} case(s) to check. Ctrl-C to stop - progress is saved as you go.\n")

    for n, cid in enumerate(todo, 1):
        t = truth[cid]
        path = CASES / t["file"]
        print(f"\n{'='*74}\n  CASE {n}/{len(todo)}   {cid}   ({t['type']})\n{'='*74}")

        if t.get("expected_error_code"):
            print(f"\n  This file should be REJECTED before assessment.")
            print(f"  Expected error: {t['expected_error_code']}")
            show_cv(path, 600)
            if input("\n  Is that right? [Enter = yes / n = no]: ").strip().lower() == "n":
                t["expected_error_code"] = input("  Correct error code: ").strip() or None
            t["verified_by_human"] = True
            GT.write_text(json.dumps(truth, indent=2))
            continue

        show_cv(path)
        print("\n  For each requirement: is the system right?")
        print("  [Enter] accept   [1] MET   [2] NOT MET   [3] NOT STATED\n")

        # re-run so the quotes shown are current
        r = process_one(str(path), save=False)
        by_id = {a.criterion_id: a for a in r.assessments}
        statuses = {}

        for cid_k, spec in criteria.items():
            a = by_id.get(cid_k)
            said = a.status.value if a else "NOT_STATED"
            quote = (a.evidence_quote if a else None) or "(no quote - the CV is silent)"
            strength = f" [{a.evidence_strength.value.lower()}]" if a and a.evidence_quote else ""
            print(f"  {spec['description'][:66]}")
            print(f"    system says: {said}{strength}")
            print(f"    evidence   : {quote[:90]}")
            ans = input("    your call  : ").strip()
            statuses[cid_k] = CHOICES.get(ans, said)
            if statuses[cid_k] != said:
                print(f"    -> corrected to {statuses[cid_k]}  (this is a finding)")
            print()

        t["expected_status"] = statuses
        print(f"  System verdict was: {r.verdict.value} ({r.criteria_met}/{r.criteria_total})")
        v = input("  Accept that tier? [Enter = yes / type GREAT_FIT|MEDIUM_FIT|LOW_FIT]: ").strip()
        t["expected_verdict"] = v.upper() if v else r.verdict.value
        t["expected_flags"] = sorted({e.type for e in r.exceptions})
        t["verified_by_human"] = True
        t.pop("note", None)

        GT.write_text(json.dumps(truth, indent=2))
        print(f"  Saved. {sum(1 for x in truth.values() if x.get('verified_by_human'))}"
              f"/{len(truth)} verified.")

    done = sum(1 for v in truth.values() if v.get("verified_by_human"))
    print(f"\n{done}/{len(truth)} verified.")
    if done == len(truth):
        print("All done. Now run:  python eval/run_eval.py --tag before")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n\nStopped. Progress was saved - run again to continue.")
