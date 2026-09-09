"""Stage 3 - EXTRACT (model). Facts only, no judgment.

Split from assessment on purpose: extraction asks what the document SAYS,
assessment asks whether that MEETS the bar. Splitting them costs one extra call
per CV and buys traceable failures plus a model that cannot bend the facts
toward a verdict it has already chosen.
"""
from __future__ import annotations

from sift.dates import total_years
from sift.llm import Usage, call_json
from sift.prompts import EXTRACT_SYSTEM, extract_user
from sift.schemas import DateRange, Profile


def _validate(payload: dict) -> None:
    if not isinstance(payload, dict):
        raise ValueError("Expected a JSON object at the top level.")
    for key in ("name", "location", "current_role"):
        if key in payload and isinstance(payload[key], (list, dict)):
            raise ValueError(f"'{key}' must be a string or null, not a {type(payload[key]).__name__}.")


def extract(cv_text: str, model: str | None = None) -> tuple[Profile, Usage]:
    payload, usage = call_json(
        EXTRACT_SYSTEM, extract_user(cv_text), model=model,
        validate=_validate, trace_name="extract")

    ranges = []
    for d in payload.get("date_ranges") or []:
        if isinstance(d, dict):
            ranges.append(DateRange(
                role=d.get("role"), start=d.get("start"),
                end=d.get("end"), raw=d.get("raw")))

    def _clean(v):
        return None if v in ("", "null", "N/A", "not stated", "unknown") else v

    def _list(v):
        return [str(x) for x in v if x] if isinstance(v, list) else []

    profile = Profile(
        name=_clean(payload.get("name")),
        email=_clean(payload.get("email")),
        location=_clean(payload.get("location")),
        current_role=_clean(payload.get("current_role")),
        companies=_list(payload.get("companies")),
        skills=_list(payload.get("skills")),
        links=_list(payload.get("links")),
        date_ranges=ranges,
    )
    # Computed in code, never asked of the model. Fix for E1/E2.
    profile.years_experience = total_years(ranges)
    return profile, usage
