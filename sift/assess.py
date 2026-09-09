"""Stage 4 - ASSESS (model). One judgment per criterion, each with a quote."""
from __future__ import annotations

from sift.llm import Usage, call_json
from sift.prompts import ASSESS_SYSTEM, assess_user
from sift.schemas import Assessment, EvidenceStrength, Profile, Status

_VALID = {s.value for s in Status}


def _make_validator(criteria: list[dict]):
    wanted = {c["id"] for c in criteria}

    def _validate(payload: dict) -> None:
        items = payload.get("assessments")
        if not isinstance(items, list):
            raise ValueError("Expected an 'assessments' array.")
        got = set()
        for i, a in enumerate(items):
            if not isinstance(a, dict):
                raise ValueError(f"assessments[{i}] must be an object.")
            cid = a.get("criterion_id")
            if cid not in wanted:
                raise ValueError(
                    f"assessments[{i}].criterion_id '{cid}' is not one of {sorted(wanted)}.")
            if a.get("status") not in _VALID:
                raise ValueError(
                    f"assessments[{i}].status '{a.get('status')}' must be one of {sorted(_VALID)}.")
            got.add(cid)
        missing = wanted - got
        if missing:
            raise ValueError(f"Missing an assessment for: {sorted(missing)}")

    return _validate


def assess(cv_text: str, criteria: list[dict], profile: Profile | None = None,
           model: str | None = None) -> tuple[list[Assessment], Usage]:
    note = ""
    if profile and profile.years_experience is not None:
        note = (f"total professional experience = {profile.years_experience} years "
                f"(overlapping roles counted once). Use this figure; do not recalculate.")

    payload, usage = call_json(
        ASSESS_SYSTEM, assess_user(cv_text, criteria, note),
        model=model, validate=_make_validator(criteria), trace_name="assess")

    out: list[Assessment] = []
    for a in payload["assessments"]:
        strength = a.get("evidence_strength", "NONE")
        if strength not in {e.value for e in EvidenceStrength}:
            strength = "NONE"
        try:
            conf = float(a.get("confidence", 0.0))
        except (TypeError, ValueError):
            conf = 0.0
        out.append(Assessment(
            criterion_id=a["criterion_id"],
            status=Status(a["status"]),
            evidence_quote=a.get("evidence_quote") or None,
            reasoning=str(a.get("reasoning", ""))[:500],
            confidence=max(0.0, min(1.0, conf)),
            evidence_strength=EvidenceStrength(strength),
        ))
    return out, usage
