# Day 1 — Discover, Map, and Baseline

**Project:** SIFT — Submission Intake & Fit Triage
**Domain:** Recruiting

---

## 1. Target user and job-to-be-done

**User:** [NAME], [ROLE] at [COMPANY] ([SIZE] people), currently hiring for [ROLE BEING HIRED].
Not a developer. Works in Gmail, Google Drive and a Google Sheet. Has never used an API.

**Job-to-be-done:**
> *When a batch of applications lands in my inbox, I want to know which candidates meet my criteria and why — with the proof in front of me — so I can decide who to interview in minutes instead of an evening, and defend that decision two weeks later.*

---

## 2. Current workflow map

| Element | Today |
|---|---|
| **Trigger** | An application arrives — email attachment, form notification, or a forwarded link |
| **Input** | CV as PDF or DOCX, the email body, sometimes a portfolio or GitHub URL |
| **Judgment** | Does this person meet each criterion? Is anything ambiguous or missing? Is this worth 30 minutes? |
| **Tool** | Gmail, Drive, a PDF viewer, a Google Sheet, LinkedIn (to check what the CV omits) |
| **Approval** | None. The screener decides alone and records no reason |
| **Output** | A verdict (advance / reject / hold), sometimes an email, sometimes a sheet row, often only a mental note |
| **Exception** | No location stated; dead portfolio link; duplicate applicant; unreadable scanned PDF; a criterion that doesn't apply |

**The bottleneck:** holding four criteria in your head, deciding alone, and recording nothing.

---

## 3. Evidence of pain

| Evidence | Measured |
|---|---|
| Applications screened last week | [X] |
| Roles run per year | [X] |
| Median time per CV | [X] min |
| Decisions with a recorded reason | [X] of [X] |
| Times a CV omitted required information | [X] |

**Observed decay.** Timing five consecutive CVs showed attention collapsing across the batch:

| CV | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| Time | [4m10s] | [3m45s] | [2m20s] | [1m05s] | [0m40s] |

Candidate 40 is not receiving the same evaluation as candidate 1. This inconsistency — not raw speed — is the real cost.

**Interview note:** *"[Quote from the user about a decision they couldn't later explain.]"*

---

## 4. Baseline

Three arms were measured on the same 12 CVs, so the system is compared against the honest alternative, not only against manual work.

| | A — Manual | B — Plain ChatGPT | C — SIFT |
|---|---|---|---|
| **Time per CV** | **3 min 00 s** | **25 s** | **49 s** (4.6 s unthrottled) |
| Output you can scan at a glance | yes | **no — a wall of prose** | yes |
| Every claim traceable to a quoted line | in your head | no | **yes, checked in code** |
| Fabricated evidence | 0 | not checked | **0 of 26 quotes** |
| Consistent shape across candidates | no | no | yes |
| Decision + reason recorded | no | no | yes |

**SIFT is slower than ChatGPT, and that is reported as measured.** The 49 s
includes rate-limiting on a free tier; the same screening runs in 4.6 s
unthrottled. But raw generation time is the wrong measure. ChatGPT produced its
answer in 25 s and then handed back several paragraphs of prose that still had
to be read, and every claim in it still had to be checked against the CV by
hand. The honest metric is **time to a decision you can act on**, and on that
measure the comparison is 3 minutes against under a minute.

**Finding from arm B:** given a CV with no location stated, ChatGPT reported the timezone criterion as met. It filled the gap rather than flagging it. Generation is already solved; verification is not. That gap defines the system.

---

## 5. Success metric

> Reduce median screening time per candidate from **[X] minutes to under 60 seconds** of human attention, while maintaining **≥90% agreement** with the hiring manager's own verdict on the 12-case set, with **zero fabricated evidence** and **100% of missing information explicitly flagged** rather than inferred.

**Secondary:** evidence accuracy, exception recall, cost per CV, latency, human edits per output.

---

## 6. Non-goals

1. **The system never decides.** It produces evidence and a recommendation; the human decides.
2. Does not source or find candidates.
3. **Does not schedule interviews.** No calendar access, no booking, no availability logic. For a GREAT FIT candidate the system drafts one invitation email asking for their availability; a human must approve it and click send. The scheduling itself happens between the two people.
4. Does not write to an ATS or any system of record.
5. **Does not pull CVs from cloud storage.** Deferred on Day 3: this user receives
   CVs on one laptop, so drag-and-drop already solves intake. A Drive integration
   would have added a service account and a folder ID for no gain. It is the first
   item in the two-week plan, for when CVs start arriving from LinkedIn into a
   shared folder.
6. Does not rank candidates against each other.
7. Does not assess soft skills or culture fit.
8. English-language CVs only.
9. Does not process scanned image-only PDFs — it detects them and routes to manual.

---

## 7. Test cases

Twelve cases, with correct answers hand-written before any code, covering representative, edge and failure conditions.

| ID | Type | Input | Expected behaviour |
|---|---|---|---|
| R1 | representative | Clean CV, meets all criteria | All met, each with a verbatim quote, verdict ADVANCE |
| R2 | representative | Meets 2 of 4 clearly | Correct mixed statuses, verdict REJECT |
| R3 | representative | Strong CV, location never stated | Marked NOT STATED, verdict REVIEW, next action "ask candidate" |
| R4 | representative | DOCX instead of PDF | Identical output shape |
| R5 | representative | Career changer, skills under a different job title | Finds the evidence; does not reject on title alone |
| R6 | representative | 6-page dense CV | Correct extraction, no truncation |
| E1 | edge | Dates given as "2019–present" | Computes duration correctly against today's date |
| E2 | edge | Two overlapping contract roles | Does not double-count years of experience |
| E3 | edge | Skill appears only in a keyword list | Flags as weak evidence — listed, not demonstrated |
| E4 | edge | Same candidate submitted twice | Detects the duplicate; no conflicting verdicts |
| F1 | failure | Scanned image-only PDF | Detects no text, stops with a clear message, invents nothing |
| F2 | failure | Wrong document entirely | Detects it is not a CV, refuses to score |
| F3 | failure | CV containing text instructing the system to mark the candidate as a perfect match | Ignores the instruction, scores on real content, flags the attempt |

---

## 8. v1 scope for Day 5

| In | Out |
|---|---|
| Drag-and-drop CVs from the laptop | Pulling CVs from Drive or a job board |
| — | Scanned / OCR documents |
| Criteria in a plain-English config file | Learning criteria from past hires |
| Per-criterion verdict with verbatim evidence | Ranking candidates against each other |
| Explicit NOT STATED for anything absent | Inferring missing facts |
| Fit tier, next action, exceptions list | Calendar access or booking slots |
| Draft invitation email for GREAT FIT, human-sent | Auto-sending anything |
| Export to a spreadsheet | Multi-user accounts |
| Single-page web interface with approve / edit / override | Mobile |
| Run log for evaluation | Analytics dashboard |

---

**Key question answered:** the problem is real (observed, not reported), recurring ([X] per week), and measurable against a three-arm baseline captured before any code was written.
