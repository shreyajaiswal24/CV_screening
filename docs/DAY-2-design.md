# Day 2 — System Design

---

## 1. Architecture

Eight stages. Each is owned by code, the model, or the human — never blurred.

```
CV file
   │
   ▼
1. INGEST        code    detect file type, extract text, hash
2. PRE-FLIGHT    code    reject empty / not-a-CV / duplicate, flag injection
3. EXTRACT       model   pull the facts stated in the document
4. ASSESS        model   judge each criterion, quote the supporting line
5. VERIFY        code    ★ is that quote actually in the document?
6. DECIDE        code    apply the user's rules → verdict + next action
7. APPROVE       human   ★ approve, edit, or override — nothing skips this
8. RECORD        code    run log + export
```

**Division of labour**

| Owner | Responsible for |
|---|---|
| **Code** | Parsing, validation, duplicate detection, date arithmetic, quote verification, verdict rules, logging |
| **Model** | Reading messy prose and extracting stated facts; judging a criterion and citing its evidence |
| **Human** | Approving, resolving anything marked NOT STATED, overriding, and reading the shortlist in full |

---

## 2. The two design decisions that define the system

**Verification contains no model.** The model returns a quote claiming to come from the CV. Stage 5 checks, using a plain text search, that the quote actually appears in the document. If it does not, the result is rejected. A model cannot be trusted to audit its own honesty about a verifiable fact — so that check is code. This converts hallucination from a vague worry into a counted, logged event.

**Extraction and assessment are separate steps.** Extraction asks *what does this document say*. Assessment asks *does that meet the bar*. Splitting them means a failure can be traced to one stage, and it stops the model bending the facts to fit a verdict it has already reached. The cost is one extra model call per CV — accepted deliberately.

---

## 3. Data contract

Every run produces the same structure, whatever the input looked like:

- **Profile** — name, location, years of experience, roles, companies, skills, links. Anything absent is null, never an empty string and never a guess.
- **Assessments** — one per criterion, each carrying a status, the supporting quote, whether that quote was verified, a confidence value, and the reasoning.
- **Verdict** — ADVANCE, REVIEW or REJECT, with the reason stated.
- **Next action** — a specific instruction, not "review further".
- **Exceptions** — everything the system could not determine.
- **Metadata** — model, tokens, cost, latency, retries.

**Four rules the contract enforces:**

1. Status is exactly one of MET, NOT MET, or NOT STATED. There is no fourth value and no free text.
2. MET or NOT MET must carry a quote, and that quote must appear verbatim in the source.
3. NOT STATED must carry no quote. *(This single rule prevents the most dangerous failure — inventing evidence to justify a gap.)*
4. Anything the document does not state is null.

---

## 4. Choices and trade-offs

| Layer | Choice | Why | Rejected |
|---|---|---|---|
| **Model** | `openai/gpt-oss-120b` on Groq | 131k context, so a 6-page CV never needs splitting, and reliable JSON output. Groq's free tier removes cost as a constraint on the evaluation, which means the test set can be re-run as often as needed | `openai/gpt-oss-20b` — kept as the fallback. Llama 3.3 was the first choice but is not available on this account, which is why the model is a config value rather than a constant |
| **Output** | Schema-constrained JSON | Guarantees a parseable shape, so everything downstream is deterministic | Free-form text plus pattern matching — fragile and unfixable when it breaks |
| **Documents** | Text extracted locally, then sent to the model | The raw text is needed anyway to verify quotes against, and lets empty files be caught before any spend | Sending the file directly to the model — leaves nothing local to verify against, which removes the system's main feature |
| **Orchestration** | LangGraph state machine | The flow is not linear: verification can send the run **back** to assessment with corrective feedback, and pre-flight can terminate before any model call. That cycle plus conditional termination is what a state machine is for | Plain sequential functions — simpler, but the repair cycle would become hand-rolled control flow with no visible graph |
| **Storage** | SQLite plus one file per run | Zero setup, a single file, and directly queryable for evaluation | A database server (setup burden) or spreadsheet-only (no history, not queryable) |
| **Interface** | One web page: drop file, run, review, approve | Works on her laptop, no build step, no terminal | A command-line tool — fails the non-developer requirement |
| **Configuration** | Criteria in a plain-English file the user edits | Criteria change per role and must not require a developer | Criteria written into the prompt — makes the system single-use |

**Measured cost:** ~$0.0013 per CV (about 2,700 tokens across two calls), roughly $0.08 to screen a 60-candidate role. Actual spend on Groq's free tier is $0; the figure uses published rates so the metric stays comparable.

**Measured latency:** 3.5–5.2 seconds per CV.

---

## 5. Human approval, privacy, permissions

**Approval points**

| Where | What the human does |
|---|---|
| Every assessment | Approve, edit any field, or override the verdict |
| Any REVIEW verdict | Must be resolved manually before export |
| Any exception | Must be acknowledged, not defaulted |
| Before export | An explicit action — nothing leaves on its own |
| **Before any email is sent** | **The strictest gate.** Only GREAT FIT candidates, only where an address was found in the CV, only after the screening result was approved, and only after the human has read the draft in full and clicked send. Default is dry-run |

Every override is logged with the original value, the human's value, and a timestamp. That log is the audit trail and the input to the next iteration.

**Privacy.** CVs are personal data about people who did not consent to this project. Processing is local; only extracted text leaves the machine, over an encrypted connection. Real CVs are excluded from the repository; the shared test set is anonymised — names, contact details and employers replaced. Retention is configurable and nothing is used to train anything.

**Permission boundaries.** Read-only access to the CV folder. No calendar access and no booking. Outbound mail is send-only, one message at a time, never in bulk, and off by default (dry-run). No writes to any system of record. The only thing that leaves is a file the human explicitly exports. Access is granted by sharing a folder with a single identity and can be revoked in one click.

---

## 6. Evaluation rubric

Written before any results existed.

| # | Criterion | Passes when |
|---|---|---|
| 1 | Schema valid | Output matches the contract exactly |
| 2 | Evidence verified | Every quote appears verbatim in the source |
| 3 | **No fabrication** | Zero quotes absent from the source *(critical)* |
| 4 | Correct status | Each criterion matches the hand-written ground truth |
| 5 | **Gaps flagged, not filled** | Everything absent is NOT STATED, never inferred *(critical)* |
| 6 | Verdict correct | Follows the stated rules from the statuses |
| 7 | Next action usable | Specific and actionable |

**Pass rule:** a case passes only if both critical checks pass **and** at least 6 of 7 checks pass. Any fabricated quote or inferred fact fails the case outright, however good the rest of the output.

That severity is a deliberate judgment: a fast, well-formatted, confidently wrong screening decision is worse than no system at all.

**Targets for Day 5:** at least 10 of 12 cases passing, zero fabricated quotes, 90% status accuracy, all known exceptions caught, under 30 seconds and under $0.10 per CV.

---

**Key question answered:** the design is repeatable rather than one-off because the contract is fixed, the criteria are configuration rather than code, verification is deterministic, and every run is logged against the same rubric.
