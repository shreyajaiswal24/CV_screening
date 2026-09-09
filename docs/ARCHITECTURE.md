# Architecture

## The pipeline

```
CV file (PDF / DOCX / TXT)
   │
   ▼
1  INGEST        code    extract text, detect format, SHA-256 the content
2  PRE-FLIGHT    code    reject empty | not-a-CV | duplicate file | scan for injection
3  EXTRACT       model   the facts the document states - no judgment
4  IDENTITY      code    has this PERSON applied before, under a different file?
5  ASSESS        model   per criterion: MET / NOT MET / NOT STATED + a quote
6  VERIFY        code    ★ is that quote actually in the document?  NO MODEL HERE
7  DECIDE        code    fit tier from the user's own thresholds
8  APPROVE       human   ★ approve / edit / override - nothing skips this
9  RECORD        code    run log, export, optional interview invitation
```

Stage 6 can send the run **back** to stage 5 once with corrective feedback.
That cycle, plus pre-flight's ability to terminate before any model call, is why
this is a LangGraph state machine and not a sequence of function calls.

## Who owns what

| Owner | Responsible for |
|---|---|
| **Code** | Parsing, validation, duplicate detection, date arithmetic, quote verification, tier rules, logging, rate limiting, email gates |
| **Model** | Reading unstructured prose and citing the line that supports a judgment |
| **Human** | Approving, resolving NOT STATED, overriding, sending any email, reading the shortlist |

Three things were **taken away from the model** during the sprint after they
failed: date arithmetic, the verdict rules, and evidence verification. Each moved
into deterministic code.

## The two decisions that define the system

**Verification contains no model.** The model returns a quote claiming to come
from the CV; code checks with a text search that it is actually there. A model
cannot be trusted to audit its own honesty about a verifiable fact. This turns
hallucination from an anxiety into a counted, logged event, and it is the only
reason a zero-fabrication claim can be made at all.

Verification runs in tiers, because exact matching proved too brittle against
real PDFs:

| Tier | Handles |
|---|---|
| `exact` | the quote is character-for-character present |
| `normalised` | whitespace and case differ (PDF line breaks) |
| `despaced` | the source is missing spaces entirely - common in PDF extraction |
| `fuzzy` (≥95%) | trivial differences |
| `not_found` | fabricated - the judgment is downgraded and flagged |

**Extraction and assessment are separate calls.** Extraction asks what the
document says; assessment asks whether that meets the bar. Splitting them costs
one extra model call per CV and buys traceable failures plus a model that cannot
bend the facts toward a verdict it has already chosen.

## Evidence strength

A quote can be real and still prove nothing. A technology named in a
`Skills:` list is not evidence of having used it. Every quote is therefore
classified by where in the document it sits:

- **STRONG** - from a dated role, project or achievement
- **WEAK** - from a skills list, keyword line or summary

Only STRONG evidence counts toward the fit score. WEAK evidence downgrades the
criterion to human review with the note *"listed as a skill but not demonstrated
in any role."*

## Fit tiers

| Condition | Tier |
|---|---|
| any **required** criterion NOT MET | **LOW FIT** — regardless of count |
| 0–1 criteria met | **LOW FIT** |
| 2–3 criteria met | **MEDIUM FIT** |
| 4+ criteria met | **GREAT FIT** |

Thresholds live in `criteria.yaml` and are editable by the user.

## Interfaces

| Layer | Choice | Rationale |
|---|---|---|
| Model | `openai/gpt-oss-20b` on Groq (free tier) | Config value, not a constant - the primary model changed twice during the sprint, once because it was unavailable on the account and once because its daily quota was exhausted |
| Output | Schema-constrained JSON + Pydantic validation | Two layers: the schema constrains what the model can emit, Pydantic catches contract drift |
| Orchestration | LangGraph | The flow has a cycle and a conditional early exit |
| Storage | SQLite, one file | Zero setup, directly queryable for the evaluation |
| Interface | FastAPI + one HTML page, no build step | The user never opens a terminal |
| Configuration | Structured filters in `criteria.yaml` | Compiled into criteria at load time; the user sets a role once instead of writing prose per requirement |
