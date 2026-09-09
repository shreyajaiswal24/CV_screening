# Day 5 — Handoff, Value, and Case Study

---

## Part 1 — Case Study

### The user and the problem

[NAME] is [ROLE] at [COMPANY], a [SIZE]-person company. When a role opens, [X] applications arrive over about two weeks. Each one is a different shape — a PDF, a Word file, a portfolio link, a rambling email. She reads each, holds four criteria in her head, decides, and records almost nothing.

Timing five consecutive CVs showed the real problem. The first received four minutes of attention; the fifth received forty seconds. The criteria never changed, but the evaluation did. Two weeks later, asked why a particular candidate was rejected, she could not say.

### The existing workflow and the bottleneck

An application arrives by email. She opens the attachment, reads it, checks it against criteria she is holding from memory, sometimes opens LinkedIn to find something the CV omitted, decides, and moves on. There is no approval step, no record of reasoning, and no consistency check.

The bottleneck is not reading. It is **deciding alone, from memory, without recording why** — which makes the process inconsistent within a single batch and impossible to audit afterwards.

### Scope decisions and non-goals

The system produces evidence and a recommendation. **It never decides.** Beyond that: no sourcing, no scheduling, no email, no writes to any system of record, no ranking candidates against each other, no assessment of soft skills or culture fit, English only, and no handling of scanned documents — which are detected and routed to a human instead.

The first of these is the load-bearing one. It is the fairness boundary, the accountability boundary, and the reason the interface is built around approval rather than automation.

### Architecture and the major trade-offs

Eight stages: ingest, pre-flight, extract, assess, verify, decide, approve, record. Code handles parsing, validation, arithmetic, verification, rules and logging. The model handles reading messy prose and citing evidence. The human approves, resolves gaps, and reads the shortlist.

**Verification contains no model.** The model returns a quote claiming to come from the CV; code checks that the quote actually appears there. A model cannot be trusted to audit its own honesty about a verifiable fact. This one decision turns hallucination from an anxiety into a measured, logged event, and it is the reason the system can make a zero-fabrication claim at all.

**Extraction and assessment are separate calls.** Extraction asks what the document says; assessment asks whether that meets the bar. Splitting them costs an extra model call per CV and buys traceable failures and a model that cannot bend facts toward a verdict it has already chosen.

**A simple stack was chosen over a sophisticated one.** Sequential functions rather than an agent framework, a single-file database rather than a server, one HTML page rather than a front-end build. The flow is linear; the complexity would have been decorative.

### Work delegated to AI, judgment retained by humans

| Delegated to the model | Retained by a human |
|---|---|
| Reading unstructured CVs of any format | Defining what the criteria mean |
| Extracting the facts the document states | Deciding whether to interview |
| Judging a criterion and citing its evidence | Resolving anything marked NOT STATED |
| Drafting the recommended next action | Overriding any verdict |
| — | Reading the shortlist in full |

Notably, three things were taken **away** from the model during the sprint: date arithmetic, verdict rules, and evidence verification. Each moved into deterministic code after it failed.

### Failures, changes and results

Three failures shaped the final system. Duration calculations were wrong until date arithmetic was moved out of the model. The verification logic raised false alarms on honest quotes until matching was made tiered. A keyword list was accepted as proof of experience until evidence gained a strength dimension — a failure where the model, the extraction and the verifier were all working correctly, and the definition of evidence was wrong.

The full test set was re-run after every fix. Pass rate moved from 8 of 12 to 12 of 12 with no regression on previously passing cases.

| Result | Before | After |
|---|---|---|
| Median human attention per CV | [X] min | [X] s |
| Cases passing the rubric | [8]/12 | [12]/12 |
| Fabricated evidence | [X] | 0 |
| Decisions with a recorded reason | [X]/12 | 12/12 |
| Cost per CV | labour | $[X] |

### Limitations

1. **It cannot read what is not written.** Where a CV omits something, the system flags it — it does not go and find it.
2. **It judges evidence, not people.** No signal on trajectory, communication, or whether a pattern of short tenures is meaningful. The human still reads the shortlist.
3. **English only.** Other languages are flagged, not assessed.
4. **No scanned documents.** Detected and routed to manual; OCR is out of scope.
5. **Only as good as the criteria.** Vague criteria produce vague assessments, and the system will not tell you your criteria are poor.
6. **Validated on 12 CVs for one role.** Accuracy at other seniorities or in other functions is unmeasured.
7. **Evidence-strength detection is heuristic** and may mis-tier unusually formatted CVs.
8. **Cost scales linearly.** Fine at current volume; a 500-applicant role would need a cheaper first pass.
9. **This is not a fairness audit.** The system reduces inconsistency, which is one source of unfairness, but it has not been tested for demographic bias and must not be presented as a debiasing tool.

---

## Part 2 — Adoption and Quality Metrics

### What actually happened

The user has been running the system since Wednesday.

| Since deployment | |
|---|---|
| CVs screened | [X] |
| Separate sessions | [X] |
| Outputs approved unedited | [X]% |
| Overrides | [X] |
| Exceptions raised / resolved | [X] / [X] |
| Total cost | $[X] |
| Estimated time saved | [X] hours |
| Runs where the author was present | [X] |

**Stated plainly:** two weeks of post-deployment data cannot exist five days into a five-day sprint. The figures above cover three days of genuine usage. What follows is the instrumentation, which already exists and already runs against real data.

### How the two-week measurement works

Four measurements run against the existing run log, with no additional instrumentation required:

- **Adoption** — screenings per day and distinct sessions per day. Does she keep using it?
- **Trust** — the proportion of outputs approved without edits. Rising means growing trust; falling means quality has drifted.
- **Quality drift** — every case where her decision differed from the system's, grouped by criterion. This is the important one: **it converts her disagreements into the next iteration's backlog automatically.**
- **Cost** — spend per day and per role.

That third measurement is the learning loop. Every override she makes becomes a candidate test case, which means the evaluation set grows from real use rather than from imagination.

### Next two weeks

| Week | Action | Reason |
|---|---|---|
| 1 | Run a full live role of 40–60 candidates; produce a weekly override report | Real volume surfaces failures twelve cases cannot |
| 1 | Add every disagreement to the evaluation set | Grows the test set from reality |
| 1 | Compare the current model against a cheaper one on the expanded set | If quality holds, cost falls substantially — but this must be measured, not assumed |
| 2 | Ship the highest-value item from her feedback | Adoption |
| 2 | Add lookup by candidate name: "why was this person rejected?" | Her own stated need |
| 2 | **Automated intake:** CVs collected from LinkedIn into a shared Drive folder, picked up on a schedule, shortlist written straight to the tracker | Deferred from v1 deliberately — the current user receives CVs on one laptop, so drag-and-drop already solved intake. Building the pipeline before the pipeline exists would have been speculative |
| 2 | Expand the evaluation set to 30 cases across two roles | Current confidence rests on 12 cases for one role |
| Later | OCR for scanned documents; a bias audit before any wider rollout | Known gaps, explicitly deferred rather than forgotten |

---

## Part 3 — AI Collaboration Note

### Tools and their roles

| Tool | Role |
|---|---|
| Claude Code | Scaffolding, boilerplate, first drafts of prompts and interface markup |
| Claude Opus 5 (production) | Extraction and assessment inside the system |
| A second model call | Rubric grading at scale, validated against hand-written labels |

### Delegated to AI

Repository scaffolding, document parsing, integration boilerplate, the interface markup and styling, first drafts of the prompts, and the database schema.

### Retained by me

The choice of problem and user. The decision that verification must be deterministic code. The rubric and its two critical criteria. All twelve test cases and their ground truth, hand-written before any code existed. The decision that the system never rejects a candidate. The interpretation of every result.

### How AI output was verified

All twelve cases were hand-labelled before the system was built, so the ground truth was never model-generated. Every generated function was read before it was used. Where a model was used to grade at scale, its agreement with my own hand labels was measured at [X] of 12 and is reported as a number — the judge was never treated as ground truth.

### Results rejected or corrected

1. **A self-reported accuracy field was removed.** The first design had the model state whether its own quote was accurate. A model asserting its own honesty is not a check. Replaced with a text search in code — which is what subsequently caught the fabrications.
2. **Calculated figures were taken away from the model.** The generated prompt asked for a years-of-experience number. It handled open-ended and overlapping dates incorrectly. All date arithmetic moved into code; the model now extracts only literal date strings.
3. **A confidence score was removed from the interface.** The first version showed it prominently. The user read 0.82 as "probably fine" and stopped checking. The evidence quote became the primary element; confidence now only routes cases internally.
4. **A free-text status field was constrained to three values.** This is what made NOT STATED a real state rather than a phrasing choice — and it is the behaviour that most distinguishes the system from a chat tool.

Item 3 came from watching a real person misread the interface, and it changed the design more than any technical finding.

### Core decisions I owned

Choosing a recruiting screening workflow with a real, recurring bottleneck. Refusing to let the system make reject decisions. Making deterministic verification the centre of the architecture. Writing the rubric and the ground truth before building anything. Setting fabrication as an instant failure rather than one criterion among seven. Measuring against plain ChatGPT rather than only against manual work. Reporting the cases where the human still outperforms the system.

---

## Part 4 — Demo Video Outline

| Time | Content |
|---|---|
| 0:00–0:40 | The user and the baseline: four minutes of attention for the first CV, forty seconds for the fifth |
| 0:40–1:10 | Plain ChatGPT reporting a location requirement as met on a CV that states no location — generation is solved, verification is not |
| 1:10–2:40 | A live run on a real CV: every judgment with its quote, checked by code; a genuine gap shown as NOT STATED |
| 2:40–3:20 | The user running it herself, unassisted, from Wednesday's recording |
| 3:20–4:10 | The evaluation table, then the injection case live — ignored, flagged, and blocked from export without acknowledgement |
| 4:10–5:00 | Measured results, then the most important limitation: it reads what is written. She still reads the top five herself — the system exists to give her the time to do that properly |

---

**Key question answered:** the repository runs from a clean clone in three steps, the README serves the user and the runbook serves an operator, the evaluation set is the diagnostic tool for anyone who inherits the system, and every limitation is stated rather than discovered.
