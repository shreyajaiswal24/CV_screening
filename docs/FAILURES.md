# Failure Analysis

Eleven defects were found and fixed during the build. **All eleven were in the
system's own code — none were model errors.** Five were found by the target user
operating the interface, not by the developer testing it.

The most instructive ones are grouped first: three failures in the parts of the
system whose entire job is to catch other failures.

---

## Category A — failures in the checking machinery

### A1. The verifier rejected honest quotes

**Symptom.** Assessments were flagged `UNVERIFIED_EVIDENCE` and downgraded to
NOT STATED, but the quotes were genuinely present in the CV.

**Root cause.** Exact substring matching is too brittle against real PDFs. Text
extraction breaks sentences across lines, so an honest quote fails a naive test.

**Fix.** Tiered verification: exact → whitespace-normalised → despaced → fuzzy
(≥95%). The tier used is recorded per judgment, so reliability can be described
rather than asserted.

**Regression.** Three false fabrication flags → zero. A deliberately injected
fake quote was still caught, confirming the check had not simply been loosened.

**Why it matters.** A verifier that raises false alarms destroys trust faster
than having no verifier at all.

---

### A2. PDF extraction drops spaces; verification could not see past it

**Symptom.** A qualified candidate's criteria were silently downgraded. Four
`UNVERIFIED_EVIDENCE` exceptions on one CV, all at 88% similarity.

**Root cause.** The PDF extracted as `"decision systemusing LangChain-based
multi-agent orchestrationand RAG"` — spaces missing from the **source**. The
model helpfully reinserted them when quoting. Whitespace-collapsing cannot fix
that, because the space is absent from the document, not the quote.

**Fix.** A `despaced` tier that removes all whitespace from both sides before
comparing.

**Regression.** Four exceptions → zero on that CV. Control test: a quote with
`at Google` inserted still fails at 0.735, so the fix did not become permissive.

---

### A3. The evaluation seeder preserved stale machine output

**Symptom.** After the criteria changed, re-seeding the ground truth produced a
file full of criterion IDs and verdict names that no longer existed.

**Root cause.** The seeder preserved prior values so a re-seed would not
overwrite human corrections — but it preserved them unconditionally, including
machine-generated ones nobody had checked.

**Fix.** Values carry forward only when `verified_by_human` is true.

**Why it matters.** Undetected, this would have meant labelling twelve cases
against criteria that no longer existed and producing evaluation numbers that
meant nothing. **A bug in the measuring instrument is worse than a bug in the
thing being measured, because it is invisible in the results.**

---

## Category B — wrong judgments, correct mechanisms

### B1. A keyword list accepted as proof of experience

**Symptom.** A CV listing a dozen technologies under `Skills:` was marked as
meeting an experience requirement, quoting that list.

**Root cause.** The criterion did not distinguish *mentioned* from
*demonstrated*. The quote was real and the verifier passed it correctly — the
definition of evidence was wrong, not the extraction or the checking.

**Fix.** Evidence carries a strength. A quote from a skills list or summary is
WEAK; from a dated role or project it is STRONG. Only STRONG evidence counts
toward the fit score.

**Regression.** The case passes. The career-changer case was re-checked and
still passes, confirming the fix did not over-correct against candidates whose
evidence sits in unusual places.

---

### B2. Section-heading precedence

**Symptom.** A quote from a dated role under `EXPERIENCE` was classified WEAK.

**Root cause.** Walking backwards for a heading, the code returned WEAK on the
first weak heading found anywhere in the preceding lines — even when a STRONG
heading sat between the quote and it.

**Fix.** The nearest heading of either kind wins.

---

### B3. Offsets from the wrong string

**Symptom.** A skills list classified STRONG.

**Root cause.** The code searched the *normalised* text and then sliced the
*raw* text with that index. Collapsing whitespace shifts every offset, so it
read the wrong preceding lines.

**Fix.** Locate the quote in the raw source with a whitespace-flexible regex.

---

## Category C — infrastructure and reliability

### C1. Rate limiting on the wrong dimension — three attempts

The most instructive failure in the project.

| Attempt | Believed constraint | Reality |
|---|---|---|
| 1 | requests/minute | The request budget is 1,000/day — never binding |
| 2 | tokens/minute (8,000) | Real, but not what was failing |
| 3 | input tokens | A reasoning model emits 1,400+ output tokens against the same budget |
| **Actual** | — | **tokens per DAY: 200,000, and 199,977 were used** |

**Why it took three attempts:** the daily cap appears in **no response header**.
Every rate-limit header read healthy — 992/1000 requests, 7,857/8,000 tokens —
while requests were being refused. The cap exists only in the 429 body.

**Root cause.** Diagnosing from the available instrumentation rather than from
the error message, when the instrumentation was silent on the actual constraint.

**Fix.** A token-aware limiter, plus detection of the daily cap specifically —
which cannot be waited out, so retrying is pointless. The system now falls back
to a model with its own separate daily budget and reports which model served the
request. The user sees *"Today's free usage allowance is used up. Everything
already screened is saved. It resets in a few hours."* rather than
`RATE_LIMITED`.

**Measured consequence.** Free-tier throughput is ~200,000 tokens/day at ~5,000
tokens per CV — about **40 CVs per day at zero cost**, which is enough for one
open role.

---

### C2. A batch died partway through

**Symptom.** A usage limit at candidate 23 ended a 40-CV run and lost all
completed work.

**Fix.** Each CV is processed in isolation, results are written as they
complete, and the run reports how many succeeded and how many failed.

---

### C3. Model unavailable on the account

**Symptom.** The first end-to-end run failed immediately.

**Root cause.** The configured model was not available on this Groq account.

**Fix.** Already correct by design — a typed error handler named the exact
remedy: *"The model isn't available on your account. Change 'model' in
config.yaml."* This is the error-message design working on the developer.

---

## Category D — found by the user, not the developer

These five surfaced within minutes of the target user operating the interface.
None would have been found by the developer testing his own build.

| # | Symptom | Root cause | Fix |
|---|---|---|---|
| D1 | "Why can't I click Export?" | Button disabled until a CV is screened, with no explanation | Live label and tooltip stating why; survives page reload |
| D2 | Same three candidates appeared four times in the spreadsheet | Export appended unconditionally | Export keyed on run ID — idempotent |
| D3 | Run log showed `tmp1249hm5_.pdf` | Filename patched *after* the run was saved | Real filename passed in before saving |
| D4 | Six CVs took 30+ seconds before anything was usable | Screening ran strictly one at a time | Concurrent pool, live placeholder cards, pagination |
| D5 | "REVIEW doesn't tell me how good they actually are" | Verdicts were process states, not judgments | Replaced with GREAT / MEDIUM / LOW FIT, scored by criteria met |

**The lesson.** Five of eleven defects were invisible to the person who wrote the
code and obvious to the person trying to use it. This is the argument for the
brief's requirement that the target user runs the system on Day 3, not Day 5.

---

## Model-level observations (not defects)

**Non-determinism at temperature 0.** The same CV screened twice produced
different statuses on one criterion. Distributed inference is not perfectly
deterministic. Reported as a limitation rather than hidden.

**The same person can score differently on two versions of their own CV.**
Discovered when duplicate-person detection matched two files by email address:
one scored LOW FIT, the other MEDIUM FIT. The system judges what is written, so
a well-written CV from a weaker candidate can outrank a poorly-written one from
a stronger candidate. Surfaced to the reviewer rather than hidden.
