"""Turn real CVs into a shareable test set.

Real CVs are personal data about people who did not consent to this project.
They stay in data/ (gitignored). This produces anonymised copies for eval/cases/,
which IS committed.

This script has now been wrong three times, in three different ways:
  1. Word-boundary anchors missed names inside handles ("jaiswalshreya").
  2. URL redaction ran BEFORE email redaction, so the domain was replaced and
     the local part - the real name - survived as "realname@https://...".
  3. The name was assumed to be the first line. One CV starts with "Objective",
     so a section heading was redacted and the real name, sitting at line 78
     under "NAME :", was left in place.

So verification no longer trusts what the redactor thinks it removed. It
re-reads the ORIGINAL, extracts every identifier from it, and asserts that none
of them survive in the output.

Usage:  python eval/anonymise.py data/real_cvs/*
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sift.ingest import extract_text  # noqa: E402

FIRST = ["Priya", "Arjun", "Meera", "Rohan", "Anaya", "Kabir", "Diya", "Vivaan"]
LAST = ["Sharma", "Nair", "Kapoor", "Iyer", "Malhotra", "Bose", "Rao", "Chawla"]

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
PHONE = re.compile(r"(?<!\d)(?:\+?\d{1,3}[\s-]?)?\(?\d{3,5}\)?[\s.-]?\d{3,4}[\s.-]?\d{3,4}(?!\d)")
ANY_URL = re.compile(r"\b(?:https?://)?(?:www\.)?[\w-]{2,}\.(?:com|org|net|io|dev|co|in|ai|me|edu)"
                     r"(?:\.[a-z]{2})?(?:/[\w./%#?=+-]*)?", re.I)
NAME_LABEL = re.compile(r"\bname\s*[:\-]\s*([A-Za-z][A-Za-z.\s]{2,50})", re.I)

HEADINGS = {"objective", "career", "interest", "academic", "credentials", "software",
            "skill", "sets", "summary", "profile", "experience", "education",
            "curriculum", "vitae", "resume", "name", "contact", "details",
            "personal", "information", "about", "declaration", "projects",
            "technical", "skills", "work", "employment", "the", "and", "for"}


def candidate_names(text: str) -> list[str]:
    """Every token that could be the person's name, from several strategies."""
    tokens: list[str] = []

    # 1. An explicit "Name: X Y" label anywhere in the document.
    for m in NAME_LABEL.finditer(text):
        tokens += [t for t in re.split(r"[^A-Za-z]+", m.group(1)) if len(t) >= 3]

    # 2. The first short line that is not a section heading.
    for line in [l.strip() for l in text.splitlines() if l.strip()][:6]:
        if len(line) > 45 or "@" in line:
            continue
        parts = [t for t in re.split(r"[^A-Za-z]+", line) if len(t) >= 3]
        if parts and not any(p.lower() in HEADINGS for p in parts):
            tokens += parts
            break

    # 3. The local part of the first email - almost always name-derived.
    m = EMAIL.search(text)
    if m:
        local = re.split(r"[._+\d-]+", m.group(0).split("@")[0])
        tokens += [t for t in local if len(t) >= 4]

    seen, out = set(), []
    for t in tokens:
        if t.lower() not in seen and t.lower() not in HEADINGS:
            seen.add(t.lower())
            out.append(t)
    return out[:6]


def anonymise(text: str, idx: int) -> tuple[str, list[str]]:
    first, last = FIRST[idx % len(FIRST)], LAST[idx % len(LAST)]
    tokens = candidate_names(text)

    # No word boundary: names hide inside handles and email local parts.
    for i, tok in enumerate(tokens):
        text = re.sub(re.escape(tok), first if i == 0 else last, text, flags=re.IGNORECASE)

    # ORDER MATTERS, and the replacements must not eat each other.
    # Emails go to a sentinel first (otherwise the URL rule eats the domain and
    # strands the real local part). The sentinel is swapped back at the end so
    # the URL rule cannot chew the placeholder address either.
    SENTINEL = "\x00EMAIL\x00"
    text = EMAIL.sub(SENTINEL, text)
    text = ANY_URL.sub("https://example.com/portfolio", text)
    text = PHONE.sub("+91 90000 00000", text)
    text = text.replace(SENTINEL, f"{first.lower()}.{last.lower()}@example.com")

    lines = text.splitlines()
    for i, l in enumerate(lines):
        if l.strip():
            lines[i] = f"{first} {last}"
            break
    return "\n".join(lines), tokens


def verify(original: str, clean: str) -> list[str]:
    """Check the OUTPUT against the ORIGINAL, not against what we meant to remove."""
    leaks: list[str] = []
    low = clean.lower()

    for e in set(EMAIL.findall(original)):
        for frag in re.split(r"[^A-Za-z]+", e.split("@")[0]):
            if len(frag) >= 4 and frag.lower() in low:
                leaks.append(f"email fragment '{frag}'")

    for u in set(ANY_URL.findall(original)):
        host = re.sub(r"^https?://|^www\.", "", u).split("/")[0]
        if len(host) >= 6 and host.lower() in low:
            leaks.append(f"domain '{host}'")

    for p in set(PHONE.findall(original)):
        digits = re.sub(r"\D", "", str(p))
        if len(digits) >= 8 and digits in re.sub(r"\D", "", clean):
            leaks.append("phone digits")

    for m in NAME_LABEL.finditer(original):
        for t in re.split(r"[^A-Za-z]+", m.group(1)):
            if len(t) >= 4 and t.lower() in low and t.lower() not in HEADINGS:
                leaks.append(f"labelled name '{t}'")

    return sorted(set(leaks))


def main() -> int:
    files = [f for f in sys.argv[1:] if Path(f).is_file()]
    if not files:
        print(__doc__)
        return 1
    out_dir = Path("eval/cases")
    out_dir.mkdir(parents=True, exist_ok=True)
    failed = False
    for i, f in enumerate(sorted(files)):
        original, _, meta = extract_text(f)
        clean, tokens = anonymise(original, i)
        leaks = verify(original, clean)
        name = meta["filename"][:38]
        if leaks:
            failed = True
            print(f"FAIL {name:<40} {'; '.join(leaks[:3])}")
            continue
        dest = out_dir / f"R{i+1}_{FIRST[i % len(FIRST)].lower()}.txt"
        dest.write_text(clean, encoding="utf-8")
        print(f"ok   {name:<40} -> {dest.name}  ({len(tokens)} identifiers redacted)")
    if failed:
        print("\nFiles that failed verification were NOT written.")
        return 1
    print("\nAll files verified against their originals.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
