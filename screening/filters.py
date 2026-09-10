"""Structured filters -> criteria.

The first criteria editor made the user write a sentence for every requirement,
every time she opened a role. Her words: "it is repeating everytime... we can
set criteria, we don't need to repeat everytime".

She was right. Recruiters think in filters - years, skills, location - not in
prose. So the editor now collects structured values and this module compiles
them into the criteria the engine already understands. The assessment engine is
unchanged; only the way requirements are expressed has changed.

One thing gets genuinely better as a side effect: years of experience is now
checked in CODE against the date ranges extracted from the CV, not judged by
the model. That removes a whole class of the arithmetic errors found earlier.
"""
from __future__ import annotations

import re
from typing import Any

DEFAULT_FILTERS: dict[str, Any] = {
    "min_years": 0,
    "must_have_skills": [],
    "nice_to_have_skills": [],
    "location": "",
    "custom": [],
}


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", text.strip().lower()).strip("_")
    return s or "criterion"


def compile_criteria(role: str, filters: dict, summary: str = "") -> list[dict]:
    """Turn the filter form into the criteria list the engine assesses."""
    f = {**DEFAULT_FILTERS, **(filters or {})}
    out: list[dict] = []

    years = int(f.get("min_years") or 0)
    if years > 0:
        out.append({
            "id": "experience_years",
            "description": f"{years} or more years of professional experience",
            "required": True,
            "check": "code",          # resolved from the CV's dates, not by the model
            "min_years": years,
            "short": f"{years}+ years experience",
        })

    for skill in f.get("must_have_skills") or []:
        skill = str(skill).strip()
        if not skill:
            continue
        out.append({
            "id": f"skill_{_slug(skill)}",
            "description": (f"Hands-on experience with {skill}, demonstrated in a role "
                            f"or project - not only listed in a skills section"),
            "required": True,
            "short": skill,
        })

    for skill in f.get("nice_to_have_skills") or []:
        skill = str(skill).strip()
        if not skill:
            continue
        out.append({
            "id": f"skill_{_slug(skill)}",
            "description": f"Experience with {skill}",
            "required": False,
            "short": skill,
        })

    loc = str(f.get("location") or "").strip()
    if loc:
        out.append({
            "id": "location",
            "description": f"Based in {loc}, or able to work {loc} business hours",
            "required": False,
            "short": f"based in {loc}",
        })

    for item in f.get("custom") or []:
        text = str(item).strip()
        if not text:
            continue
        out.append({
            "id": _slug(text)[:40],
            "description": text,
            "required": False,
            "short": text[:34],
        })

    # de-duplicate ids, keeping the stricter (required) version
    seen: dict[str, dict] = {}
    for c in out:
        prev = seen.get(c["id"])
        if prev is None or (c["required"] and not prev["required"]):
            seen[c["id"]] = c
    return list(seen.values())


def resolve_code_criteria(profile, criteria: list[dict]):
    """Evaluate the criteria marked check=code, deterministically.

    Returns a list of Assessment objects the model never sees, so a numeric
    requirement can never be mis-argued in prose.
    """
    from screening.schemas import Assessment, EvidenceStrength, Status

    out = []
    for c in criteria:
        if c.get("check") != "code" or c["id"] != "experience_years":
            continue
        need = float(c.get("min_years") or 0)
        have = profile.years_experience

        if have is None:
            out.append(Assessment(
                criterion_id=c["id"], status=Status.NOT_STATED, evidence_quote=None,
                reasoning="No dated roles were found in the CV, so total experience "
                          "could not be calculated.",
                confidence=1.0, evidence_verified=None,
                verification_method="computed", needs_review=True,
                review_reason="Ask the candidate how long they have been working."))
            continue

        quote = None
        if profile.date_ranges:
            d = profile.date_ranges[0]
            quote = d.raw or " - ".join(x for x in (d.role, d.start, d.end) if x)

        out.append(Assessment(
            criterion_id=c["id"],
            status=Status.MET if have >= need else Status.NOT_MET,
            evidence_quote=quote,
            reasoning=(f"{have} years computed from the dated roles in the CV, with "
                       f"overlapping periods counted once. Requirement is {need:g}+."),
            confidence=1.0,
            evidence_verified=True,
            verification_method="computed",
            evidence_strength=EvidenceStrength.STRONG))
    return out
