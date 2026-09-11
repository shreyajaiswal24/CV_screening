# CV Screening

**🔗 Live demo:** <https://cv-screening-2.onrender.com/> — no install needed. Drop a CV, write your criteria, read the evidence. *(Free hosting: the first load can take ~30 s while the server wakes up.)*

Screens CVs against your criteria and **shows you the line from the CV that
proves every judgment** — checked by code, not by another AI.

It never decides who to hire. It reads each CV, checks it against criteria you
wrote in plain English, quotes the evidence, and says **NOT STATED** when the CV
is silent. It never guesses.

---

## The problem

Screening 40–70 applications for one role takes an evening. Worse, it isn't
consistent: the first CV gets three minutes of careful reading, the fortieth
gets twenty seconds. Same criteria, different attention — and two weeks later
nobody can say why a particular candidate was rejected, because nothing was
written down.

The obvious fix is to paste the CV into ChatGPT. It answers in 25 seconds. But
give it a CV that never mentions where the candidate lives, ask whether they
meet a location requirement, and **it says yes** — it fills the gap, because a
plausible answer feels more useful than admitting ignorance.

> **Generation is already solved. Verification is not.**
>
> The expensive part of screening is not writing an assessment. It is knowing
> whether to believe it. That is what this system does.

---

## What you get back

```
  Priya Sharma                                    GREAT FIT
  priya_sharma_cv.pdf · Noida, India              4/5 criteria met

  ✅ MET          Python
     "Built and deployed a document question-answering system in Python"
     ✓ found in the CV (exact)   strong — from a role   confidence 96%

  ✅ MET          LangChain
     "Implemented a hybrid RAG + LLM pipeline using campaign history"
     ✓ found in the CV (exact)   strong — from a role   confidence 95%

  ❓ NOT STATED   Shipped to production
     The CV does not say. Nothing was assumed.

  ⚠️ WEAK         AWS
     "Backend & Infra: FastAPI, PostgreSQL, Docker, Redis, AWS"
     Listed as a skill but not demonstrated in any role.

  → Strong match. Confirm production experience, then invite to interview.

  [ Approve ]  [ Change this ]        9.1s · $0.002 · 2,700 tokens
```

Every quote is checked against the document by a text search before you see it.

---

## How it works

```
  CV file (PDF · DOCX · TXT)
        │
   1  INGEST         code     extract text, hash the content
        │
   2  PRE-FLIGHT     code     reject empty · not-a-CV · duplicate
        │                     scan for hidden instructions
   3  EXTRACT       model     the facts the document states — no judging
        │
   4  IDENTITY       code     has this person applied before, under another file?
        │
   5  ASSESS        model     per criterion: MET / NOT MET / NOT STATED + a quote
        │
   6  VERIFY         code   ★ is that quote actually in the document?
        │                     ↺ if not, one corrective retry
   7  DECIDE         code     fit tier from your own thresholds
        │
   8  APPROVE       human   ★ approve · edit · override — nothing skips this
        │
   9  RECORD         code     run log · Excel export · interview invitation
```

**Stage 6 is the point of the whole system.** The model returns a quote claiming
to come from the CV. Code then searches the document for it. If it isn't there,
the judgment is thrown away.

The instinct is to ask a second model to check the first — but a model
confirming its own honesty about a checkable fact isn't a check. So it's a text
search. Boring, deterministic, and the only reason this can claim **zero
fabricated evidence**.

### Who does what

| | Responsible for |
|---|---|
| **Code** | Parsing, validation, duplicate detection, date arithmetic, quote verification, tier rules, logging |
| **Model** | Reading messy prose and citing the line that supports a judgment |
| **Human** | Approving, resolving gaps, overriding, sending any email |

Three things were **taken away from the model** during the build after they went
wrong: date arithmetic, the verdict rules, and evidence verification. All three
are plain Python now.

---

## Setup — 3 steps, about 5 minutes

**1. Install**
```bash
git clone https://github.com/shreyajaiswal24/CV_screening.git
cd CV_screening
./setup.sh
```

**2. Add your key**

Open the file called `.env` and paste your key after `GROQ_API_KEY=`
Get a free one at <https://console.groq.com/keys>.

**3. Start**
```bash
./run.sh
```

Open <http://localhost:8000>.

---

## Using it

**Set what you're screening for** — click **Criteria**. Plain English, no code:

```
  Job title:   AI Engineer            Minimum experience: 2 years
  Must have:   [Python] [LangChain]
  Nice to have:[AWS] [Docker]
  Location:    India
```

**Drop CVs on the page.** PDF, Word or text. Several at once.

**Read the results.** Each judgment carries its quote. Approve, edit, or
override — nothing counts until you do.

**Export.** Downloads a formatted Excel file: fit tier colour-coded, evidence
included, filterable. Your co-founder can read it without opening the app.

**Invite.** For a GREAT FIT, the system drafts an interview email addressed to
the address it read from the CV. You read it and click send. It never guesses an
address, never sends below GREAT FIT, and never sends twice.

### Reading the results

| | Meaning |
|---|---|
| **MET** + a quote | The CV says so, and the quote was found in the document |
| **NOT MET** + a quote | The CV shows the candidate does *not* meet this |
| **NOT STATED** | The CV is silent. **You need to ask.** |
| `strong — from a role` | Quoted from a dated job or project |
| `weak — from a skills list` | The word appears in a keyword list. Not proof |
| ⚠️ flag | Something is uncertain. Read this one yourself |

**Fit tiers:** GREAT FIT (4+ criteria met) · MEDIUM FIT (2–3) · LOW FIT (0–1, or
any must-have not met).

### What you must check before approving

1. **Anything flagged.** Always.
2. **Anything NOT STATED.** The system won't guess, so it's on you to ask.
3. **Your top few candidates, in full.** The system reads the words on the page.
   It cannot see that three previous employers all folded.

---

## Results

Measured on a 12-case test set — six real CVs, three edge cases, three designed
to fail — with answers written by hand before running anything.

| | By hand | Plain ChatGPT | This system |
|---|---|---|---|
| **Time per CV** | 3 min 00 s | 25 s | 49 s *(4.6 s unthrottled)* |
| **Scannable at a glance** | yes | no — a wall of prose | yes |
| **Evidence traceable to a line** | in your head | no | **yes, checked in code** |
| **Fabricated evidence** | 0 | not checkable | **0 of 26 quotes** |
| **Decision + reason recorded** | no | no | **yes** |
| **Cost per CV** | your evening | — | **$0.0017** |

**Rubric pass rate: 8/12.** The four failures and their root causes are in
[the failure analysis](docs/Case-study/failure%20analysis.docx).

ChatGPT is faster. It also hands back paragraphs you still have to read and
verify line by line. **Twelve of its answers can't be put side by side. Twelve
of these can.**

---

## What it will not do

- **It never rejects anyone.** It recommends; you decide.
- No sourcing, no calendar access, no interview booking.
- No writes to any applicant tracking system.
- No ranking candidates against each other.
- No judging soft skills or culture fit.
- English CVs only.
- Scanned or photographed CVs are detected and handed back, not guessed at.

**It has not been tested for demographic bias.** It reduces *inconsistency*,
which is one source of unfairness. That is not the same as proving the absence
of others. Full list in [the limitations document](docs/Case-study/limitations.docx).

---

## Data handling

- Processing is local. Only the extracted text goes to the model, over TLS.
- Real CVs live in `data/`, excluded from version control.
- The test CVs in `eval/cases/` are anonymised by a script that verifies its own
  output against the original and fails if any identifier survives.
- Nothing is used to train anything. Delete `data/` and nothing is left.

---

## Documentation

### The case study

| | |
|---|---|
| [Why this project](docs/Case-study/Why%20this%20Project.docx) | Why this problem, and why verification rather than generation |
| [Architecture](docs/Case-study/Architecture.docx) | The nine stages and the decisions behind them |
| [Failure analysis](docs/Case-study/failure%20analysis.docx) | 11 defects with root causes and regressions |
| [Limitations](docs/Case-study/limitations.docx) | What it cannot do, stated plainly |
| [Evaluation](docs/Case-study/evaluation.docx) | Test set, rubric, three-arm baseline |
| [Data flow](docs/Case-study/data%20flow.docx) | What leaves the machine, what is stored |
| [Code map](docs/Case-study/code%20map.docx) | Where everything lives |
| [README and runbook](docs/Case-study/readme%20and%20runbook.docx) | For whoever maintains it |
| [Demo script](docs/Case-study/demo%20script.docx) | The five-minute walkthrough |

### The five-day record

| | |
|---|---|
| [Day 1 — Discover, map, baseline](docs/All%205%20Days/DAY-1-discovery.md) | User, workflow, evidence of pain, baseline, test set |
| [Day 2 — Design](docs/All%205%20Days/Day%202-%20design.docx) | Architecture, data contracts, rubric |
| [Day 3 — Build](docs/All%205%20Days/Day%203-%20build.docx) | The working core, integrations, first user run |
| [Day 4 — Evaluate](docs/All%205%20Days/Day%204%20-%20evaluate.docx) | Results, failures, hardening, regression |
| [Day 5 — Handoff](docs/All%205%20Days/Day%205%20-%20handoff.docx) | Case study, metrics, next iteration |

Word documents download rather than preview on GitHub. Day 1 is markdown and
reads in the browser.

---

## Running it online

Deploy on [Render](https://render.com): New → Blueprint → point it at this repo.
It reads `render.yaml`. Set `GROQ_API_KEY` in the dashboard, plus `SMTP_USER`,
`SMTP_PASSWORD` and `ALLOW_EMAIL=1` if you want it to send invitations.

There is no login, so anyone with the link can use it — deliberate, so it can be
tried without credentials. Remove `ALLOW_EMAIL` and it drafts invitations without
sending them. The free tier sleeps after ~15 minutes idle, so the first request
takes about 30 seconds to wake.

---

**Built with** Python · FastAPI · LangGraph · Groq (`openai/gpt-oss-120b`) ·
SQLite · vanilla JS, no build step.
