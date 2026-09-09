"""Command line entry point:  python -m sift.cli <file> [--criteria criteria.yaml]"""
from __future__ import annotations

import argparse
import json
import sys

from sift.graph import process_one
from sift.observability import flush
from sift.schemas import Status

ICON = {Status.MET.value: "[MET]", Status.NOT_MET.value: "[NOT MET]",
        Status.NOT_STATED.value: "[NOT STATED]"}


def render(r) -> str:
    if r.error_code:
        return f"\n  {r.source_file}\n  ! {r.error_code}: {r.error_message}\n"
    out = [f"\n  {r.profile.name or r.source_file}  ({r.source_file})"]
    if r.profile.location:
        out.append(f"  Location: {r.profile.location}")
    if r.profile.years_experience is not None:
        out.append(f"  Experience: {r.profile.years_experience} years (computed in code)")
    out.append("")
    for a in r.assessments:
        out.append(f"  {ICON.get(a.status.value, a.status.value):<13} {a.criterion_id}")
        if a.evidence_quote:
            out.append(f"      \"{a.evidence_quote}\"")
            out.append(f"      verified: {a.verification_method}  "
                       f"strength: {a.evidence_strength.value}  "
                       f"confidence: {a.confidence:.0%}")
        else:
            out.append(f"      (no quote - the CV does not state this)")
        if a.needs_review:
            out.append(f"      >> NEEDS REVIEW: {a.review_reason}")
        out.append("")
    out.append(f"  VERDICT: {r.verdict.value} - {r.verdict_reason}")
    out.append(f"  NEXT:    {r.next_action}")
    if r.exceptions:
        out.append("\n  Exceptions:")
        for e in r.exceptions:
            out.append(f"    - [{e.severity}] {e.type}: {e.detail}")
    m = r.meta
    out.append(f"\n  {m.latency_ms}ms | {m.llm_calls} calls | "
               f"{m.input_tokens}+{m.output_tokens} tokens | "
               f"~${m.est_cost_usd:.5f} | retries {m.retries} | {m.model}")
    return "\n".join(out)


def main() -> int:
    p = argparse.ArgumentParser(prog="sift", description="Screen a CV against your criteria.")
    p.add_argument("files", nargs="+", help="CV file(s): PDF, DOCX or TXT")
    p.add_argument("--criteria", default=None, help="path to criteria.yaml")
    p.add_argument("--json", action="store_true", help="print raw JSON instead")
    args = p.parse_args()

    exit_code = 0
    for f in args.files:
        r = process_one(f, args.criteria)
        print(json.dumps(r.to_dict(), indent=2) if args.json else render(r))
        if r.error_code:
            exit_code = 1
    flush()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
