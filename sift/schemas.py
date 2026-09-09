"""The data contract.

Every run produces this shape, whatever the input looked like. The four rules
enforced here are what stop the system inventing evidence:

  1. status is exactly one of MET / NOT_MET / NOT_STATED - no fourth value.
  2. MET or NOT_MET must carry a quote.
  3. NOT_STATED must carry NO quote.
  4. Anything the document does not state is None, never "" and never a guess.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator

SCHEMA_VERSION = "1.0"


class Status(str, Enum):
    MET = "MET"
    NOT_MET = "NOT_MET"
    NOT_STATED = "NOT_STATED"


class EvidenceStrength(str, Enum):
    STRONG = "STRONG"   # quoted from a dated role or project description
    WEAK = "WEAK"       # quoted from a skills list or summary line
    NONE = "NONE"


class Verdict(str, Enum):
    """Fit tiers.

    Changed on Day 3 from ADVANCE/REVIEW/REJECT after the user pointed out that
    "REVIEW" told her nothing about how good the candidate actually was. A tier
    derived from how many criteria are met is legible at a glance and sorts a
    pile of CVs; the per-criterion flags still carry the detail.
    """
    GREAT_FIT = "GREAT_FIT"
    MEDIUM_FIT = "MEDIUM_FIT"
    LOW_FIT = "LOW_FIT"
    BLOCKED = "BLOCKED"     # could not assess - see exceptions


class DateRange(BaseModel):
    """Literal date strings copied from the CV. The model never does arithmetic."""
    role: Optional[str] = None
    start: Optional[str] = None    # as written, e.g. "2021" or "Mar 2021"
    end: Optional[str] = None      # as written, e.g. "present" or "2024"
    raw: Optional[str] = None


class Profile(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    location: Optional[str] = None
    current_role: Optional[str] = None
    companies: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)
    date_ranges: list[DateRange] = Field(default_factory=list)
    # computed in code from date_ranges - never asked of the model
    years_experience: Optional[float] = None

    @model_validator(mode="after")
    def _no_empty_strings(self):
        for f in ("name", "email", "location", "current_role"):
            if getattr(self, f) == "":
                setattr(self, f, None)
        return self


class Assessment(BaseModel):
    criterion_id: str
    status: Status
    evidence_quote: Optional[str] = None
    reasoning: str = ""
    confidence: float = 0.0

    # filled in by the verifier (code, no model involved)
    evidence_verified: Optional[bool] = None
    verification_method: Optional[str] = None   # exact | normalised | fuzzy | not_found
    evidence_strength: EvidenceStrength = EvidenceStrength.NONE
    needs_review: bool = False
    review_reason: Optional[str] = None

    @model_validator(mode="after")
    def _contract(self):
        if self.evidence_quote == "":
            self.evidence_quote = None
        # Rule 3: NOT_STATED must carry no quote. Enforced, not requested.
        if self.status == Status.NOT_STATED and self.evidence_quote is not None:
            self.evidence_quote = None
            self.needs_review = True
            self.review_reason = "Model supplied a quote for a criterion it marked NOT STATED"
        return self


class ExceptionRecord(BaseModel):
    type: str          # MISSING_FIELD | UNVERIFIED_EVIDENCE | POSSIBLE_INJECTION | ...
    field: Optional[str] = None
    detail: Optional[str] = None
    severity: str = "medium"   # low | medium | high
    resolved: bool = False


class RunMeta(BaseModel):
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    est_cost_usd: float = 0.0
    latency_ms: int = 0
    retries: int = 0
    llm_calls: int = 0
    schema_version: str = SCHEMA_VERSION


class EmailDraft(BaseModel):
    """An interview invitation. Never sent without an explicit human action."""
    to: Optional[str] = None
    subject: str = ""
    body: str = ""
    can_send: bool = False
    blocked_reason: Optional[str] = None
    sent: bool = False
    sent_at: Optional[str] = None
    dry_run: bool = True


class RunResult(BaseModel):
    run_id: str
    source_file: str
    source_sha256: str
    criteria_role: str = ""
    profile: Profile = Field(default_factory=Profile)
    assessments: list[Assessment] = Field(default_factory=list)
    verdict: Verdict = Verdict.BLOCKED
    verdict_reason: str = ""
    next_action: str = ""
    exceptions: list[ExceptionRecord] = Field(default_factory=list)
    criteria_met: int = 0
    criteria_total: int = 0
    prior_applications: list[dict] = Field(default_factory=list)
    email: Optional[EmailDraft] = None
    meta: RunMeta = Field(default_factory=RunMeta)
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    @property
    def fabricated_count(self) -> int:
        return sum(1 for a in self.assessments if a.evidence_verified is False)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


# ---- shapes we ask the model for (kept separate from the verified output) ----

EXTRACT_JSON_SHAPE = {
    "name": "string or null",
    "email": "the candidate's email address exactly as written, or null",
    "location": "string or null - ONLY if the CV states a place, country or timezone",
    "current_role": "string or null",
    "companies": ["string"],
    "skills": ["string"],
    "links": ["string"],
    "date_ranges": [
        {"role": "string", "start": "as written in the CV", "end": "as written, or 'present'",
         "raw": "the full line as written"}
    ],
}

ASSESS_JSON_SHAPE = {
    "assessments": [
        {
            "criterion_id": "string - must match one of the given criterion ids",
            "status": "MET | NOT_MET | NOT_STATED",
            "evidence_quote": "EXACT text copied from the CV, or null",
            "evidence_strength": "STRONG if quoted from a dated role/project, WEAK if from a skills list or summary, NONE if no quote",
            "confidence": "number between 0 and 1",
            "reasoning": "one sentence",
        }
    ]
}
