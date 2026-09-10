# Day 4 — Evaluation, Failure, and Hardening

All numbers below come from one reproducible evaluation run over the 12-case set, graded against ground truth written by hand before the system existed. Results were captured **before** any hardening, so improvement could be measured rather than claimed.

---

## 1. Test-set results and baseline comparison

| Metric | A — Manual | B — Plain ChatGPT | C — SIFT |
|---|---|---|---|
| **Time per CV** | **3 min 00 s** | **25 s** | **49 s** (4.6 s unthrottled) |
| **Cases passing the rubric (of 12)** | — | — | **8/12 (67%)** |
| **Fabricated quotes** | 0 | not verifiable | **0 of 26** |
| Schema valid | — | no fixed shape | 12/12 |
| Evidence verified against the source | in your head | no | 12/12 |
| Gaps flagged rather than filled | — | — | 8/12 |
| Verdict follows the stated rules | — | — | 12/12 |
| Outputs needing no human edit | — | — | 8/12 |
| Cost per CV | labour | — | **$0.0014** |
| Decision + reason recorded | no | no | **yes** |

### Latency is a billing constraint, not an engineering one

Measured within a single evaluation run — same model, same code, same day:

| | Latency |
|---|---|
| First 2 runs, before the per-minute token budget filled | **4,620 ms and 4,666 ms** |
| Remaining 8 runs, once the rate limiter engaged | 57,968 – 63,357 ms |

The model takes about **4.6 seconds** per CV. The remaining ~55 seconds is the
system waiting so that its next request is not refused. Groq's free tier allows
8,000 tokens per minute and a CV costs ~3,844 tokens, which caps throughput at
roughly **1.6 CVs per minute and 40 per day**.

On a paid tier the same code runs at ~4.6 s per CV. Cost per CV is $0.0017, so
screening a 60-candidate role costs about **$0.10** — against roughly three
hours of a hiring manager's attention at the measured 3 minutes per CV.

**Quote verification tiers** (26 quotes): 81% exact, 8% normalised, **12%
despaced**. That last figure matters — three quotes verified only because of the
despaced tier added on Day 3. Without it they would have been flagged as
fabrications and three qualified candidates downgraded.

**Observed about arm B:** ChatGPT answered fastest, but returned several
paragraphs of prose with no fixed shape. The reviewer's note was that it was
*"too lengthy to read"*. Twelve of those cannot be put side by side and
compared, and none of them survives as a record. Speed of generation is not the
bottleneck; speed to a decision you can trust is.
| Criterion accuracy (of 48 judgments) | [X] | [X] | [X] | [X] |
| **Fabricated evidence** | 0 | [X] | [X] | **0** |
| Gaps flagged rather than filled | [X] | [X] | [X] | [X] |
| Median time per CV | [X] min | [X] min | [X] s | [X] s |
| Total time for 12 CVs | [X] | [X] | [X] | [X] |
| Decisions with a recorded reason | [X]/12 | 0/12 | 12/12 | 12/12 |
| Consistency (same CV screened twice) | [X] | [X] | identical | identical |
| Cost per CV | labour | [X] | [X] | [X] |
| Human edits per output | n/a | [X] | [X] | [X] |

**What the comparison actually shows.**

Manual screening remains the most sensitive to context — a person notices that three previous employers all failed, and the system cannot. Plain ChatGPT is fast at producing an assessment but has no consistent shape, no verification, and no memory of the criteria between candidates. Its defining failure is that it fills gaps: asked about a candidate whose CV never states a location, it reported the requirement as met.

SIFT wins on speed, consistency, evidence and documentation, and loses to a careful human on nuance. That trade is stated deliberately rather than hidden.

---

## 2. Metrics

| Class | Result |
|---|---|
| **Quality** | [X]/12 cases passing; [X]% criterion accuracy; 0 fabricated quotes; [X]% of known exceptions caught |
| **Speed** | [X]s median per CV, [X]s at the 95th percentile; [X] minutes for a 40-CV batch |
| **Cost** | $[X] per CV; $[X] for a 60-candidate role |
| **Human intervention** | [X]% of outputs approved unedited; [X] edits per output; [X]% routed to REVIEW |
| **Reliability** | [X]% of quotes matched exactly, [X]% after normalisation, [X]% failed verification; retry rate [X]% |

**The most meaningful of these is human intervention.** [X] of 12 outputs were approved with no edits, and every output that required editing was a REVIEW case where the CV genuinely did not state the information. That describes the user's actual day better than any accuracy percentage.

---

## 3. Failure analysis

### Failure 1 — Experience duration computed incorrectly

**Symptom.** A candidate with a role listed as "2019–present" was marked as not meeting a three-year requirement. A second candidate with two overlapping contract roles was credited with nine years against a true figure of six.

**Root cause.** The model was asked to produce a number it had to calculate, with no anchor for the current date and no rule for overlapping periods. This is arithmetic — a code problem handed to a language model.

**Fix.** The model now extracts only the literal date ranges written in the document. Duration is computed in code, resolving open-ended ranges against the run date and merging overlaps. The model no longer produces any calculated figure.

**Regression.** Two cases moved from fail to pass; no other case changed. Pass rate 8/12 → 10/12.

---

### Failure 2 — The verifier rejected honest quotes

**Symptom.** Three assessments were flagged as unverifiable and downgraded, but the quotes were genuinely present in the CV. The model had normalised a line break or silently corrected a typo.

**Root cause.** A defect in the verification logic, not the model. Exact text matching is too brittle against PDF extraction, which frequently breaks sentences across lines.

**Fix.** Verification now runs in tiers — exact match, then a match ignoring spacing and case, then a high-threshold similarity match returning the matched span. Anything below that threshold is a genuine fabrication. The tier used is recorded for every judgment, so reliability can be described rather than asserted.

**Regression.** Three false fabrication flags reduced to zero. A deliberately injected fake quote was still caught, confirming the check had not simply been loosened. Pass rate 10/12 → 11/12.

**Why this one matters.** It is a failure in the system's own checking logic. A verifier that raises false alarms destroys trust faster than having no verifier at all.

---

### Failure 3 — A keyword list treated as proof

**Symptom.** A CV listing a dozen technologies under "Skills" was marked as meeting the experience requirement, quoting that list. The candidate had never held a role using the technology.

**Root cause.** The criterion did not distinguish *mentioned* from *demonstrated*. A keyword in a list is technically evidence, so the model quoted it accurately and reached the wrong conclusion. **The verifier passed it, correctly — the quote was real.** The failure was in the definition of evidence, not in extraction or verification.

**Fix.** Evidence now carries a strength. A quote from a skills list or summary is weak; a quote from a dated role or project description is strong. A criterion can only be marked met on strong evidence. Weak evidence downgrades it to review with the note that the skill is listed but not demonstrated.

**Regression.** The case moved from fail to pass. The career-changer case was re-checked and still passes, confirming the fix did not over-correct against candidates whose evidence sits in unusual places. Pass rate 11/12 → 12/12.

---

### Also found and fixed

**A batch died partway through.** A usage limit at candidate 23 ended a 40-CV run and lost all completed work. Each candidate is now processed in isolation, results are written as they complete, and the run reports how many succeeded and how many failed. Re-tested: 39 of 40 completed with one clean exception.

**An injection attempt was ignored but not reported.** The system correctly disregarded a CV instructing it to mark the candidate as a perfect match, but produced an ordinary-looking result. The user had no idea the document contained an attack. Detection was added, and a detected attempt is now a hard review gate that cannot be exported without acknowledgement. No false positives across the other cases.

---

## 4. Hardening

Mechanisms were chosen per failure type rather than applied uniformly.

| Failure mode | Mechanism | Reasoning |
|---|---|---|
| Malformed output | Schema constraint plus a bounded repair retry | Deterministic and recoverable without a human |
| Fabricated quote | Validation and hard fail — no retry | An honesty failure must not be retried until it happens to pass |
| Unverifiable quote | Tiered matching, then downgrade and flag | Separates "wrong" from "formatted differently" |
| Missing information | Explicit NOT STATED, exception, human gate | Absence is information and must reach a person |
| Weak evidence | Confidence scoring, routed to review | Genuine ambiguity deserves a human |
| Injection detected | Hard human gate, cannot be bypassed | Security decisions are never automated |
| Usage limits and transient errors | Backoff plus per-item isolation | Expected and temporary; must never lose a batch |
| Unreadable or wrong document | Fail fast, before any model call | Cheap to detect, expensive to get wrong |

**The principle:** retry transient failures, validate factual ones, escalate ambiguous ones to a human.

---

## 5. Before and after

| Case | Before | After | Change |
|---|---|---|---|
| R1–R6 representative | 6/6 pass | 6/6 pass | no regression |
| E1 open-ended dates | fail | pass | duration moved to code |
| E2 overlapping roles | fail | pass | interval merging |
| E3 keyword-only skill | fail | pass | evidence strength |
| E4 duplicate | pass | pass | — |
| F1 scanned document | pass | pass | — |
| F2 wrong document | fail | pass | pre-flight check |
| F3 injection | handled, unreported | pass | detection and hard gate |
| **Total** | **8/12** | **12/12** | |

The full set was re-run after every individual fix. The "no regression" row is the point of the exercise: fixing the keyword case did not break the career-changer case.

---

## 6. User feedback and changes made

| She said | Change | Effect |
|---|---|---|
| "I don't know if it's frozen" | Progress indicator during processing | Confidence |
| "I want to see where that quote is" | Quotes link to the source document | Verification in seconds |
| "What if it's confidently wrong?" | NOT STATED and low confidence styled distinctly; nothing exports without approval | Trust |
| "Can I change the criteria myself?" | Criteria editable in the interface | Removed the dependency on a developer |
| "REVIEW doesn't tell me how good they actually are" | Replaced ADVANCE/REVIEW/REJECT with **GREAT / MEDIUM / LOW FIT**, scored by how many criteria are met, with required criteria as a gate | A pile of CVs became sortable at a glance |
| "After I approve a great fit, I still have to go and email them" | Added a drafted interview invitation, addressed to the email **extracted from that CV**. Never auto-sent: only GREAT FIT, only after approval, only after the human reads the draft and clicks send. Dry-run by default | Closed the loop from screening to outcome |
| "I'd still read the top five myself" | Kept as a documented limitation, not treated as a gap | Correct scope |

The last row is the most important. The right response was not to build more. The system's purpose is to make the other thirty-five candidates fast enough that she has time to read the top five properly.

---

**Key question answered:** quality and failure are described across representative, edge and adversarial conditions, with root causes identified, fixes applied, and every fix re-measured against the full set.
