"""Stage 2 - PRE-FLIGHT (code). Every check here runs BEFORE any model call,
so bad input is cheap to reject and impossible to hallucinate over.

Covers test cases F1 (scanned PDF), F2 (not a CV), E4 (duplicate), F3 (injection).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

MIN_CHARS = 200

# A CV almost always contains contact details plus at least one section heading.
CV_SIGNALS = [
    r"\b[\w.+-]+@[\w-]+\.[\w.]+\b",                      # email
    r"\bexperience\b", r"\bemployment\b", r"\bwork history\b",
    r"\beducation\b", r"\bskills\b", r"\bqualifications\b",
    r"\bcurriculum vitae\b", r"\bresume\b", r"\bprojects\b",
    r"\breferences\b", r"(19|20)\d{2}\s*[-–]\s*((19|20)\d{2}|present)",
]

# Text inside a candidate document that is trying to address the system.
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(the\s+)?(previous|prior|above)\s+instructions?",
    r"disregard\s+(all\s+)?(the\s+)?(previous|prior|above)",
    r"you\s+(are|must|should)\s+(now\s+)?(a\s+|an\s+)?(mark|rate|score|treat|consider)",
    r"system\s*prompt",
    r"mark\s+this\s+candidate\s+as",
    r"rate\s+this\s+(candidate|applicant|cv)\s+as",
    r"(perfect|ideal|strong)\s+(match|fit)\s*[.!]?\s*$",
    r"<\s*/?\s*(system|instruction|prompt)\s*>",
    r"\bAI\b.{0,30}\b(assistant|screener|reviewer)\b.{0,40}\b(must|should|please)\b",
]


@dataclass
class PreflightResult:
    ok: bool
    error_code: str | None = None
    error_message: str | None = None
    flags: list[dict] = field(default_factory=list)
    cv_signal_count: int = 0


def scan_injection(text: str) -> list[str]:
    hits = []
    for pat in INJECTION_PATTERNS:
        for m in re.finditer(pat, text, flags=re.IGNORECASE | re.MULTILINE):
            snippet = text[max(0, m.start() - 40): m.end() + 40].replace("\n", " ")
            hits.append(snippet.strip())
    return hits[:5]


def looks_like_cv(text: str) -> int:
    return sum(1 for p in CV_SIGNALS if re.search(p, text, flags=re.IGNORECASE))


def preflight(text: str, digest: str, seen_hashes: set[str] | None = None,
              filename: str = "this file") -> PreflightResult:
    seen_hashes = seen_hashes or set()

    # F1 - scanned / image-only PDF. Stops before any spend. Invents nothing.
    if len(text) < MIN_CHARS:
        return PreflightResult(
            ok=False,
            error_code="NO_TEXT_FOUND",
            error_message=(
                f"No readable text in '{filename}' - it looks like a scan or a photo "
                f"rather than a text document. Ask the candidate for a text PDF, "
                f"or paste the text in manually."
            ),
        )

    # F2 - wrong document entirely.
    signals = looks_like_cv(text)
    if signals < 2:
        return PreflightResult(
            ok=False,
            error_code="NOT_A_CV",
            error_message=(
                f"'{filename}' doesn't look like a CV - it has no contact details "
                f"and no recognisable sections. Skipped, please check the file."
            ),
            cv_signal_count=signals,
        )

    flags: list[dict] = []

    # E4 - duplicate submission.
    if digest in seen_hashes:
        flags.append({
            "type": "DUPLICATE",
            "severity": "medium",
            "detail": "This document matches one already screened. Showing it again "
                      "would produce a second, possibly conflicting verdict.",
        })

    # F3 - instruction text aimed at the screening system.
    hits = scan_injection(text)
    if hits:
        flags.append({
            "type": "POSSIBLE_INJECTION",
            "severity": "high",
            "detail": "This CV contains text that tries to instruct the screening "
                      "system. It was ignored, but review this candidate manually.",
            "matches": hits,
        })

    return PreflightResult(ok=True, flags=flags, cv_signal_count=signals)
