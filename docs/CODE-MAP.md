# Code Map

Where everything lives, and which pipeline stage it belongs to.

```
CV_Screening_Code/
│
├── README.md              start here — setup and how to use it
├── setup.sh               3-step install (handles a machine with no python3-venv)
├── run.sh                 starts the web interface on localhost:8000
├── requirements.txt       dependencies
├── config.yaml            model, thresholds, email settings   (no secrets)
├── criteria.yaml          WHAT YOU SCREEN FOR — the user edits this
├── .env.example           every secret key, all values blank
│
├── sift/                  ← the system
├── static/index.html      ← the entire interface, one file, no build step
├── eval/                  ← the evaluation package
├── docs/                  ← architecture, failures, limitations, case study
└── samples/               anonymised example CVs
```

## `sift/` — the pipeline, one file per stage

| Stage | File | Owner | What it does |
|---|---|---|---|
| 1 | `ingest.py` | code | PDF / DOCX / TXT → text + SHA-256 |
| 2 | `preflight.py` | code | rejects empty, not-a-CV, duplicate file; scans for prompt injection |
| 3 | `extract.py` | **model** | pulls the facts the document states — no judgment |
| 4 | `graph.py` (identity node) | code | has this **person** applied before, under a different file? |
| 5 | `assess.py` | **model** | per criterion: MET / NOT MET / NOT STATED + a quote |
| 6 | `verify.py` | code | **is that quote actually in the document?** ← no model here |
| 7 | `decide.py` | code | fit tier from the user's own thresholds |
| 8 | *(the UI)* | **human** | approve / edit / override |
| 9 | `db.py` | code | run log, judgments, exceptions, human overrides |

## `sift/` — supporting modules

| File | Purpose |
|---|---|
| `graph.py` | The LangGraph state machine wiring stages 1–9, including the verify → repair → re-assess cycle |
| `schemas.py` | **The data contract.** Four rules that stop the system inventing evidence |
| `filters.py` | Compiles the structured criteria form into criteria; resolves code-checked ones (years of experience) |
| `llm.py` | Groq client, JSON output, repair retries, token-aware rate limiting, daily-cap fallback |
| `prompts.py` | Prompts. The CV is always fenced and labelled as untrusted data |
| `dates.py` | Experience arithmetic — deliberately in code, with overlapping roles merged |
| `emailer.py` | Interview invitations. Five gates. Template, not model output |
| `config.py` | Secrets, settings, criteria loading. Resolves a Windows-visible export folder under WSL |
| `db.py` | SQLite. The `assessments` table is also the evaluation dataset |
| `api.py` | FastAPI endpoints |
| `cli.py` | `python -m sift.cli <file>` |
| `observability.py` | Optional Langfuse tracing; no-op without keys |
| `integrations/gsheets.py` | Writes the shortlist to a Google Sheet, or CSV as a fallback |
| `integrations/gdrive.py` | Reads CVs from a Drive folder — **built, then cut from v1.** Kept as the head start on the two-week plan |

## `eval/` — the evaluation package

| File | Purpose |
|---|---|
| `cases/` | The 12-case test set — 6 real anonymised CVs, 3 edge, 3 failure |
| `ground_truth.json` | The correct answers, verified by a human. Unverified cases are excluded from scoring |
| `run_eval.py` | `--seed`, `--tag <name>`, `--compare before after` |
| `review.py` | Scan all 12 with their evidence; `--fix`, `--accept-all` |
| `label.py` | Case-by-case labelling with the CV in front of you |
| `run_baseline.py` | Arm B — a plain single-prompt LLM, same model, no system around it |
| `baseline_prompt.txt` | The prompt used for the chat-window baseline |
| `anonymise.py` | Turns real CVs into a shareable test set, and verifies its own output |

## `docs/`

| File | Contents |
|---|---|
| `WHY-THIS-PROJECT.md` | Why this problem, the attention-decay finding, why verification not generation |
| `ARCHITECTURE.md` | The 9 stages, code/model/human split, the two defining decisions |
| `DATA-FLOW.md` | What leaves the machine, what is stored, permission boundaries |
| `FAILURES.md` | 11 defects with root causes and regressions |
| `LIMITATIONS.md` | 16 limitations, including the fairness caveat |
| `EVALUATION.md` | Test set, rubric, three-arm baseline, results |
| `RUNBOOK.md` | For whoever maintains it |
| `DEMO-SCRIPT.md` | Timed 5-minute script |
| `DAY-1` … `DAY-5` | The sprint record, day by day |
| `metrics.sql` | Adoption and quality queries against the run log |

## The rule that shapes the whole codebase

> Deterministic work is code. Reading messy prose is the model. Deciding is the
> human.

Three things were **taken away from the model** during the build after they
failed: date arithmetic (`dates.py`), the verdict rules (`decide.py`), and
evidence verification (`verify.py`). Each is now plain Python.

`verify.py` is the file to read first. It is the reason the system can claim
zero fabricated evidence — a model is never asked to confirm its own honesty
about something checkable.
