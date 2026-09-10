"""Stage 5 - VERIFY (code). NO MODEL IS INVOLVED HERE, ON PURPOSE.

The model returns a quote claiming to come from the CV. This module checks that
the quote is actually there. A model cannot be trusted to audit its own honesty
about a verifiable fact, so the check is a text search.

Matching is tiered because exact matching was too brittle (failure #2): PDF text
extraction breaks sentences across lines, so an honest quote can fail a naive
substring test. Each tier is recorded, so reliability can be described rather
than asserted.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

from screening.schemas import Assessment, EvidenceStrength, ExceptionRecord, Status


def normalise(s: str) -> str:
    return re.sub(r"[\s ]+", " ", s).strip().lower()


def despace(s: str) -> str:
    """Drop ALL whitespace before comparing.

    Third verification tier, added after real PDFs broke the first two. PDF text
    extraction routinely drops spaces ("decision systemusing LangChain"), and the
    model re-inserts them when it quotes. Collapsing whitespace cannot fix that,
    because the space is missing in the SOURCE, not the quote. Comparing with
    whitespace removed entirely is immune to it, while still catching genuinely
    invented text.
    """
    return re.sub(r"\s+", "", s).lower()
    return re.sub(r"[\s ]+", " ", s).strip().lower()


def _best_window_ratio(needle: str, hay: str) -> float:
    """Best similarity of `needle` against any same-length window of `hay`."""
    n, h = len(needle), len(hay)
    if n == 0 or h == 0:
        return 0.0
    if n >= h:
        return SequenceMatcher(None, needle, hay).ratio()
    step = max(1, n // 4)
    best = 0.0
    sm = SequenceMatcher(None)
    sm.set_seq2(needle)
    for i in range(0, h - n + 1, step):
        window = hay[i:i + n + step]
        sm.set_seq1(window)
        if sm.real_quick_ratio() <= best or sm.quick_ratio() <= best:
            continue
        best = max(best, sm.ratio())
        if best >= 0.999:
            break
    return best


def verify_quote(quote: str | None, source: str, threshold: float = 0.95
                 ) -> tuple[bool, str, float]:
    """Return (verified, method, score)."""
    if quote is None:
        return True, "no_quote_required", 1.0
    if quote in source:
        return True, "exact", 1.0
    nq, ns = normalise(quote), normalise(source)
    if nq and nq in ns:
        return True, "normalised", 1.0
    dq, ds = despace(quote), despace(source)
    if dq and dq in ds:
        return True, "despaced", 1.0
    score = _best_window_ratio(dq, ds)
    if score >= threshold:
        return True, "fuzzy", round(score, 3)
    return False, "not_found", round(score, 3)


# Where in the document a quote came from decides how strong it is.
# Failure #3: a keyword in a "Skills:" list is a real quote but not proof of
# experience. The verifier was right; the definition of evidence was wrong.
_WEAK_SECTION = re.compile(
    r"(skills?|technologies|tech\s*stack|tools|competenc|summary|profile|about\s+me|keywords)\s*:?\s*$",
    re.IGNORECASE)
_DATE_NEARBY = re.compile(r"(19|20)\d{2}", re.IGNORECASE)

# Second bug found on real data: walking backwards, the code returned WEAK on the
# first weak heading anywhere in the preceding lines - even when a STRONG heading
# ("EXPERIENCE") sat between the quote and that weak heading. Whichever heading is
# reached FIRST going backwards is the one the quote actually sits under.
_STRONG_SECTION = re.compile(
    r"^\s*(work\s+)?(experience|employment|work\s+history|career|projects?|"
    r"professional\s+experience|roles?)\s*:?\s*$", re.IGNORECASE)


def _raw_index(quote: str, source: str) -> int:
    """Locate a quote in the RAW source, tolerating whitespace differences.

    Bug found on first run: searching the normalised text and then slicing the
    raw text with that index reads the wrong lines, because collapsing
    whitespace shifts every offset. A skills list was classified STRONG as a
    result. The index must come from the raw string.
    """
    if not quote:
        return -1
    i = source.find(quote)
    if i != -1:
        return i
    pattern = r"\s+".join(re.escape(tok) for tok in quote.split())
    m = re.search(pattern, source, flags=re.IGNORECASE)
    return m.start() if m else -1


def classify_strength(quote: str | None, source: str) -> EvidenceStrength:
    if not quote:
        return EvidenceStrength.NONE

    idx = _raw_index(quote, source)
    if idx == -1:
        return EvidenceStrength.WEAK

    # A bare comma-separated list is a skills list whether or not it has a heading.
    if quote.count(",") >= 3 and len(quote) < 200 and not _DATE_NEARBY.search(quote):
        return EvidenceStrength.WEAK

    # Which heading does this line sit under? Walk backwards and stop at the
    # FIRST heading of either kind - the nearest one wins.
    preceding = source[max(0, idx - 1200): idx]
    lines = [l.strip() for l in preceding.splitlines() if l.strip()]
    for line in reversed(lines):
        if _STRONG_SECTION.match(line):
            return EvidenceStrength.STRONG
        if _WEAK_SECTION.search(line):
            return EvidenceStrength.WEAK

    # A quote sitting next to a date is almost always a real role.
    if _DATE_NEARBY.search(quote) or _DATE_NEARBY.search(preceding[-150:]):
        return EvidenceStrength.STRONG

    return EvidenceStrength.STRONG


def verify_batch(assessments: list[Assessment], source: str,
                 threshold: float = 0.95, confidence_threshold: float = 0.70
                 ) -> tuple[list[Assessment], list[ExceptionRecord]]:
    exceptions: list[ExceptionRecord] = []

    for a in assessments:
        if a.verification_method == "computed":
            continue          # resolved in code from the CV's own dates
        ok, method, score = verify_quote(a.evidence_quote, source, threshold)
        a.evidence_verified = ok if a.evidence_quote is not None else None
        a.verification_method = method

        # Contract rule 2: a judgment without evidence is not a judgment.
        if a.status in (Status.MET, Status.NOT_MET) and a.evidence_quote is None:
            a.needs_review = True
            a.review_reason = "No supporting quote was provided for this judgment."
            exceptions.append(ExceptionRecord(
                type="MISSING_EVIDENCE", field=a.criterion_id, severity="high",
                detail=f"'{a.criterion_id}' was marked {a.status.value} with no quote."))

        if not ok:
            # An honesty failure is not retried until it passes. It is downgraded.
            a.status = Status.NOT_STATED
            a.evidence_quote = None
            a.needs_review = True
            a.review_reason = (
                f"The supporting quote could not be found in the document "
                f"(closest match {score:.0%}). Downgraded - please check this one yourself.")
            exceptions.append(ExceptionRecord(
                type="UNVERIFIED_EVIDENCE", field=a.criterion_id, severity="high",
                detail=f"Quote not present in source (similarity {score:.0%})."))
            continue

        a.evidence_strength = classify_strength(a.evidence_quote, source)

        # Failure #3 fix: MET requires STRONG evidence.
        if a.status == Status.MET and a.evidence_strength == EvidenceStrength.WEAK:
            a.needs_review = True
            a.review_reason = ("Listed as a skill but not demonstrated in any dated role. "
                               "Confirm with the candidate.")
            exceptions.append(ExceptionRecord(
                type="WEAK_EVIDENCE", field=a.criterion_id, severity="medium",
                detail="Evidence came from a skills list or summary, not a role."))

        if a.status == Status.NOT_STATED:
            exceptions.append(ExceptionRecord(
                type="MISSING_FIELD", field=a.criterion_id, severity="medium",
                detail="The CV does not state this. Ask the candidate."))

        if a.confidence < confidence_threshold and not a.needs_review:
            a.needs_review = True
            a.review_reason = f"Low confidence ({a.confidence:.0%}) - worth a second look."

    return assessments, exceptions
