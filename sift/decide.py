"""Stage 6 - DECIDE (code). The fit tier is a rule, not an opinion.

Changed on Day 3. The first version returned ADVANCE / REVIEW / REJECT, and in
use almost everything landed on REVIEW - which told the user nothing about how
good a candidate actually was, and gave her no way to sort a pile of CVs.

The tier is now driven by HOW MANY criteria are met, with required criteria
acting as a gate. The per-criterion flags still carry the detail; the tier just
makes the pile sortable at a glance.
"""
from __future__ import annotations

from sift.schemas import (Assessment, EvidenceStrength, ExceptionRecord,
                          Status, Verdict)

TIER_LABEL = {
    Verdict.GREAT_FIT: "GREAT FIT",
    Verdict.MEDIUM_FIT: "MEDIUM FIT",
    Verdict.LOW_FIT: "LOW FIT",
    Verdict.BLOCKED: "COULD NOT ASSESS",
}


def decide(assessments: list[Assessment], criteria: list[dict], rules: dict,
           exceptions: list[ExceptionRecord]) -> tuple[Verdict, str, str, int, int]:
    """Return (tier, reason, next_action, criteria_met, criteria_total)."""
    by_id = {a.criterion_id: a for a in assessments}
    total = len(criteria)

    # A criterion counts as met only on verified, strong evidence.
    met = [a.criterion_id for a in assessments
           if a.status == Status.MET
           and a.evidence_verified is not False
           and a.evidence_strength != EvidenceStrength.WEAK]
    weak = [a.criterion_id for a in assessments
            if a.status == Status.MET and a.evidence_strength == EvidenceStrength.WEAK]
    not_met = [a.criterion_id for a in assessments if a.status == Status.NOT_MET]
    not_stated = [a.criterion_id for a in assessments if a.status == Status.NOT_STATED]

    required = [c["id"] for c in criteria if c.get("required")]
    required_failed = [cid for cid in required
                       if cid in by_id and by_id[cid].status == Status.NOT_MET]

    n = len(met)
    great_min = int(rules.get("great_fit_min", 4))
    medium_min = int(rules.get("medium_fit_min", 2))

    # An injection attempt overrides everything - a human must look first.
    if any(e.type == "POSSIBLE_INJECTION" for e in exceptions):
        return (Verdict.LOW_FIT,
                "This document contains text that tries to instruct the screening "
                "system. It was ignored, but the score cannot be trusted until a "
                "human has read the CV.",
                "Read this CV yourself before doing anything else.",
                n, total)

    # Required criteria gate the tier, whatever the count.
    if rules.get("required_are_gating", True) and required_failed:
        return (Verdict.LOW_FIT,
                f"{n} of {total} criteria met, but a must-have is not met: "
                f"{', '.join(required_failed)}.",
                "No action needed. The reason is recorded if the candidate asks.",
                n, total)

    if n >= great_min:
        tier = Verdict.GREAT_FIT
    elif n >= medium_min:
        tier = Verdict.MEDIUM_FIT
    else:
        tier = Verdict.LOW_FIT

    bits = [f"{n} of {total} criteria met"]
    if not_met:
        bits.append(f"not met: {', '.join(not_met)}")
    if weak:
        bits.append(f"weak evidence: {', '.join(weak)}")
    if not_stated:
        bits.append(f"the CV does not state: {', '.join(not_stated)}")
    reason = "; ".join(bits) + "."

    if tier == Verdict.GREAT_FIT:
        action = ("Strong match - review the evidence above, then invite them to "
                  "interview.")
        if not_stated:
            action = (f"Strong match. Confirm {', '.join(not_stated)} when you "
                      f"speak to them, then invite them to interview.")
    elif tier == Verdict.MEDIUM_FIT:
        action = (f"Partial match. Ask about {', '.join(not_stated or not_met)} "
                  f"before deciding." if (not_stated or not_met)
                  else "Partial match - your call whether the gaps matter.")
    else:
        action = "Below the bar for this role. The reason is recorded."

    return tier, reason, action, n, total
