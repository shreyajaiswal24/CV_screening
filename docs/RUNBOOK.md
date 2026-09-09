# Operator Runbook

For whoever maintains SIFT. The user-facing guide is `README.md`.

---

## Architecture in one view

```
CV file
  1 INGEST      code    PDF / DOCX / TXT -> text + SHA-256
  2 PRE-FLIGHT  code    empty | not-a-CV | duplicate | injection scan
  3 EXTRACT     model   facts stated in the document, no judgment
  4 ASSESS      model   per-criterion status + a quote from the CV
  5 VERIFY      code    is that quote actually in the document?   <- no model here
  6 DECIDE      code    verdict from criteria.yaml rules
  7 APPROVE     human   approve / edit / override
  8 RECORD      code    SQLite + export
```

Stage 5 can send the run back to stage 4 once with corrective feedback. That
cycle is why this is a LangGraph state machine rather than a sequence of calls.

**The rule that matters:** a model never verifies its own honesty about a
verifiable fact. Quote checking is a text search in `sift/verify.py`.

---

## Running it

| Task | Command |
|---|---|
| Web interface | `./run.sh` then <http://localhost:8000> |
| One CV | `python -m sift.cli path/to/cv.pdf` |
| Several | `python -m sift.cli data/cvs/*.pdf` |
| Raw JSON | `python -m sift.cli cv.pdf --json` |
| Evaluation | `python eval/run_eval.py --tag <name>` |
| Compare two runs | `python eval/run_eval.py --compare before after` |
| Anonymise real CVs | `python eval/anonymise.py data/real_cvs/*` |

---

## Where things live

| Path | Contents | In git? |
|---|---|---|
| `.env` | API keys | **no** |
| `credentials/` | Google service-account JSON | **no** |
| `data/` | Real CVs, `sift.db`, exports | **no** |
| `config.yaml` | Model, thresholds, folder/sheet IDs | yes |
| `criteria.yaml` | The role being screened for | yes |
| `samples/`, `eval/cases/` | Anonymised examples and test set | yes |
| `eval/ground_truth.json` | Hand-verified correct answers | yes |

---

## Error codes

| Code | Cause | Fix |
|---|---|---|
| `NO_TEXT_FOUND` | Scanned or image-only document | Expected. Routed to manual — no bug. |
| `NOT_A_CV` | Fewer than 2 CV signals in the text | If it misfires on a real CV, add a pattern to `CV_SIGNALS` in `preflight.py`. |
| `UNSUPPORTED_FORMAT` | Not PDF / DOCX / TXT | Convert, or extend `SUPPORTED` in `ingest.py`. |
| `BAD_API_KEY` | Groq rejected the key | Check `.env`. Keys start `gsk_`. |
| `BAD_MODEL` | Model not on this account | List models with the Groq API and update `model:` in `config.yaml`. |
| `RATE_LIMITED` | Free-tier limit hit | Lower `requests_per_minute` in `config.yaml`. Completed CVs are saved. |
| `INVALID_OUTPUT` | Model returned unreadable JSON after retries | Check `max_repair_retries`. Persistent failures usually mean a malformed criteria file. |
| `NO_CONNECTION` | Network | Retry. |
| `UNEXPECTED_ERROR` | Anything else | Stack trace is in the terminal running `./run.sh`. |

---

## Common problems

**Sheets export fails.** The sheet must be shared as Editor with the service
account's `client_email` (inside `credentials/service_account.json`). Same for
the Drive folder, as Viewer.

**Everything comes back NOT STATED.** Almost always the criteria, not the
system. Criteria phrased as abstractions ("strong engineer") give the model
nothing to quote. Rewrite them as things a CV would literally say.

**Lots of UNVERIFIED_EVIDENCE.** The quote check is failing. Look at
`verification_method` in the run log: if quotes are landing on `fuzzy` or
`not_found` for real CVs, the PDF extraction is probably mangling text. Check
the extracted text first — do not raise `fuzzy_match_threshold` to make the
symptom go away.

**Latency spikes to 30s+.** Groq free-tier throttling. The limiter in
`llm.py` paces requests; lower `requests_per_minute` if it's frequent.

**Quality seems worse than it was.** Run the evaluation set first:
`python eval/run_eval.py --tag check` and compare against the last saved
results. Do not tune prompts on a single bad example.

---

## Rotating credentials

**Groq key:** create a new key in the Groq console, replace the value in
`.env`, restart. Delete the old key.

**Google service account:** create a new key in Google Cloud Console, replace
`credentials/service_account.json`, restart. Delete the old key. Folder and
sheet sharing is unaffected — it's tied to the account, not the key.

---

## Adding a test case

1. Put the CV in `eval/cases/` — anonymised. Prefix `R` (representative),
   `E` (edge) or `F` (failure).
2. Run `python eval/run_eval.py --seed` to add a template entry.
3. **Open `eval/ground_truth.json`, correct every field against the CV
   yourself, then set `verified_by_human` to `true`.**

Unverified cases are excluded from scoring by design. Grading the system
against its own output measures nothing.

---

## Changing the model

Edit `model:` in `config.yaml` and add a matching row under `pricing:` so cost
reporting stays accurate. Then re-run the full evaluation set and compare
before switching for real — a cheaper model is only cheaper if quality holds.

---

## Cost and usage monitoring

The SQLite database at `data/sift.db` holds everything. Useful queries are in
`docs/metrics.sql` — daily volume, the proportion of outputs approved without
edits, every case where a human disagreed with the system, and spend per day.

The disagreement query is the important one: it turns overrides into the next
iteration's backlog automatically.
