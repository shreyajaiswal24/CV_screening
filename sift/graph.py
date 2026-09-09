"""The LangGraph state machine.

A framework is justified here because the flow is not linear: verification can
send the run BACK to assessment with corrective feedback, up to a bounded number
of repairs, and pre-flight can terminate the run before any model call. That
cycle plus conditional termination is what a state machine is for.

  ingest -> preflight -+-> (fail) ------------------------> record
                       |
                       +-> extract -> assess -> verify -+-> (repair) -> assess
                                                        |
                                                        +-> decide -> record
"""
from __future__ import annotations

import time
import uuid
from typing import Annotated, Any, Optional, TypedDict

from langgraph.graph import END, StateGraph

from sift import db
from sift.assess import assess as assess_stage
from sift.config import SETTINGS, load_criteria
from sift.decide import decide as decide_stage
from sift.extract import extract as extract_stage
from sift.ingest import IngestError, extract_text
from sift.llm import LLMError, Usage
from sift.observability import trace_node
from sift.preflight import preflight as preflight_stage
from sift.schemas import (Assessment, ExceptionRecord, Profile, RunMeta,
                          RunResult, Status, Verdict)
from sift.verify import verify_batch

MAX_REPAIRS = 1


class State(TypedDict, total=False):
    run_id: str
    file_path: str
    filename: str
    criteria: list[dict]
    rules: dict
    role: str
    seen_hashes: set

    cv_text: str
    digest: str
    ingest_meta: dict

    profile: Optional[Profile]
    assessments: list[Assessment]
    exceptions: list[ExceptionRecord]
    repair_count: int
    repair_note: str

    prior_applications: list
    verdict: Optional[Verdict]
    verdict_reason: str
    next_action: str
    criteria_met: int
    criteria_total: int

    usage: Usage
    started_ms: float
    error_code: Optional[str]
    error_message: Optional[str]


# ---------------------------------------------------------------- nodes

@trace_node("ingest")
def n_ingest(state: State) -> dict:
    try:
        text, digest, meta = extract_text(state["file_path"])
        return {"cv_text": text, "digest": digest, "ingest_meta": meta,
                "filename": state.get("filename") or meta["filename"]}
    except IngestError as e:
        return {"error_code": e.code, "error_message": e.message}


@trace_node("preflight")
def n_preflight(state: State) -> dict:
    if state.get("error_code"):
        return {}
    res = preflight_stage(state["cv_text"], state["digest"],
                          state.get("seen_hashes") or set(),
                          state.get("filename", "this file"))
    exceptions = [ExceptionRecord(type=f["type"], detail=f.get("detail"),
                                  severity=f.get("severity", "medium"))
                  for f in res.flags]
    if not res.ok:
        return {"error_code": res.error_code, "error_message": res.error_message,
                "exceptions": exceptions}
    return {"exceptions": exceptions}


@trace_node("extract")
def n_extract(state: State) -> dict:
    try:
        profile, usage = extract_stage(state["cv_text"])
        u = state.get("usage") or Usage()
        u.add(usage)
        return {"profile": profile, "usage": u}
    except LLMError as e:
        return {"error_code": e.code, "error_message": e.message}


@trace_node("identity")
def n_identity(state: State) -> dict:
    """Has this PERSON applied before, under a different file?

    Separate from the content-hash check in pre-flight: that one catches the
    same file, this one catches the same candidate with an edited CV.
    """
    if state.get("error_code") or not state.get("profile"):
        return {}
    prof = state["profile"]
    prior = db.find_prior_applications(prof.email, prof.name, state["run_id"])
    if not prior:
        return {}
    last = prior[0]
    detail = (f"This person was already screened on {last['when']} "
              f"as {last['verdict'].replace('_', ' ').title()} "
              f"(file: {last['file']}"
              + (f", +{len(prior)-1} more" if len(prior) > 1 else "") + "). "
              f"Matched on their {last['matched_on']}. This CV may be a newer "
              f"version - check before treating them as a new applicant.")
    return {"exceptions": (state.get("exceptions") or []) + [
        ExceptionRecord(type="DUPLICATE_PERSON", field=last["run_id"],
                        severity="medium", detail=detail)],
            "prior_applications": prior}


@trace_node("assess")
def n_assess(state: State) -> dict:
    try:
        text = state["cv_text"]
        if state.get("repair_note"):
            text = text  # source is unchanged; the correction goes in the criteria note
        # Criteria marked check=code are resolved deterministically and never
        # sent to the model - a numeric requirement cannot be mis-argued in prose.
        from sift.filters import resolve_code_criteria
        computed = resolve_code_criteria(state["profile"], state["criteria"])
        computed_ids = {a.criterion_id for a in computed}
        for_model = [c for c in state["criteria"] if c["id"] not in computed_ids]

        items, usage = ([], Usage())
        if for_model:
            items, usage = assess_stage(text, for_model, state.get("profile"))
        u = state.get("usage") or Usage()
        u.add(usage)
        return {"assessments": computed + items, "usage": u}
    except LLMError as e:
        return {"error_code": e.code, "error_message": e.message}


@trace_node("verify")
def n_verify(state: State) -> dict:
    if state.get("error_code"):
        return {}
    items, new_exc = verify_batch(
        state["assessments"], state["cv_text"],
        threshold=SETTINGS.get("fuzzy_match_threshold", 0.95),
        confidence_threshold=SETTINGS.get("confidence_threshold", 0.70))
    return {"assessments": items,
            "exceptions": (state.get("exceptions") or []) + new_exc}


def n_repair(state: State) -> dict:
    """Bounded corrective pass. Only unverifiable quotes trigger this."""
    bad = [a.criterion_id for a in state["assessments"]
           if a.verification_method == "not_found"]
    return {"repair_count": state.get("repair_count", 0) + 1,
            "repair_note": f"These criteria had quotes that are not in the document: "
                           f"{', '.join(bad)}. Re-read the document and either quote it "
                           f"exactly or return NOT_STATED."}


@trace_node("decide")
def n_decide(state: State) -> dict:
    if state.get("error_code"):
        return {}
    verdict, reason, action, met, total = decide_stage(
        state["assessments"], state["criteria"], state.get("rules") or {},
        state.get("exceptions") or [])
    return {"verdict": verdict, "verdict_reason": reason, "next_action": action,
            "criteria_met": met, "criteria_total": total}


# ---------------------------------------------------------------- edges

def after_preflight(state: State) -> str:
    return "record" if state.get("error_code") else "extract"


def after_extract(state: State) -> str:
    return "record" if state.get("error_code") else "identity"


def after_assess(state: State) -> str:
    return "record" if state.get("error_code") else "verify"


def after_verify(state: State) -> str:
    unverified = any(a.verification_method == "not_found" for a in state["assessments"])
    if unverified and state.get("repair_count", 0) < MAX_REPAIRS:
        return "repair"
    return "decide"


def n_record(state: State) -> dict:
    return {}


def build_graph():
    g = StateGraph(State)
    for name, fn in [("ingest", n_ingest), ("preflight", n_preflight),
                     ("extract", n_extract), ("identity", n_identity),
                     ("assess", n_assess),
                     ("verify", n_verify), ("repair", n_repair),
                     ("decide", n_decide), ("record", n_record)]:
        g.add_node(name, fn)

    g.set_entry_point("ingest")
    g.add_edge("ingest", "preflight")
    g.add_conditional_edges("preflight", after_preflight,
                            {"extract": "extract", "record": "record"})
    g.add_conditional_edges("extract", after_extract,
                            {"identity": "identity", "record": "record"})
    g.add_edge("identity", "assess")
    g.add_conditional_edges("assess", after_assess,
                            {"verify": "verify", "record": "record"})
    g.add_conditional_edges("verify", after_verify,
                            {"repair": "repair", "decide": "decide"})
    g.add_edge("repair", "assess")          # the cycle that justifies the framework
    g.add_edge("decide", "record")
    g.add_edge("record", END)
    return g.compile()


GRAPH = build_graph()


def process_one(file_path: str, criteria_path: str | None = None,
                seen_hashes: set | None = None, save: bool = True,
                original_name: str | None = None) -> RunResult:
    """Run one CV through the whole flow. Never raises - failures come back as
    a RunResult with an error code, so one bad file cannot kill a batch."""
    cfg = load_criteria(criteria_path) if criteria_path else load_criteria()
    run_id = f"r_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"
    started_at = db.now()
    t0 = time.time()

    state: State = {
        "run_id": run_id, "file_path": str(file_path),
        "filename": original_name or str(file_path).split("/")[-1],
        "criteria": cfg["criteria"], "rules": cfg.get("decision_rules", {}),
        "role": cfg.get("role", ""),
        "seen_hashes": seen_hashes if seen_hashes is not None else db.seen_hashes(),
        "assessments": [], "exceptions": [], "usage": Usage(), "repair_count": 0,
    }

    try:
        final = GRAPH.invoke(state)
    except Exception as e:                      # never let one file kill a batch
        final = dict(state)
        final["error_code"] = "UNEXPECTED_ERROR"
        final["error_message"] = f"Something went wrong processing this file: {e}"

    usage = final.get("usage") or Usage()
    result = RunResult(
        run_id=run_id,
        source_file=final.get("filename", str(file_path)),
        source_sha256=final.get("digest", ""),
        criteria_role=cfg.get("role", ""),
        profile=final.get("profile") or Profile(),
        assessments=final.get("assessments") or [],
        verdict=final.get("verdict") or Verdict.BLOCKED,
        verdict_reason=final.get("verdict_reason") or (final.get("error_message") or ""),
        next_action=final.get("next_action") or "",
        exceptions=final.get("exceptions") or [],
        prior_applications=final.get("prior_applications") or [],
        criteria_met=final.get("criteria_met", 0),
        criteria_total=final.get("criteria_total", 0),
        error_code=final.get("error_code"),
        error_message=final.get("error_message"),
        meta=RunMeta(model=SETTINGS["model"], input_tokens=usage.input_tokens,
                     output_tokens=usage.output_tokens, est_cost_usd=usage.est_cost_usd,
                     latency_ms=int((time.time() - t0) * 1000),
                     retries=usage.retries, llm_calls=usage.calls),
    )
    # Draft the invitation, but never send it. Sending requires two explicit
    # human actions in the interface.
    if not result.error_code and result.assessments:
        from sift.emailer import build_draft
        try:
            result.email = build_draft(result, cfg["criteria"],
                                       cfg.get("decision_rules", {}))
        except Exception as e:
            result.email = None
            result.exceptions.append(ExceptionRecord(
                type="EMAIL_DRAFT_FAILED", severity="low", detail=str(e)[:200]))

    if save:
        db.init()
        db.save(result, started_at)
    return result
