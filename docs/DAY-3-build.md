# Day 3 — The Working Core

**Goal:** a complete path from trigger to final output that the target user can run alone.

---

## 1. What was built

The full eight-stage flow now runs end to end. A CV enters as a file and leaves as a reviewed, approved, exported result. Nothing in the path requires a developer.

| Stage | Status |
|---|---|
| Ingest — PDF, DOCX and plain text | working |
| Pre-flight — empty file, wrong document, duplicate, injection scan | working |
| Extract and assess | working |
| Verify — every quote checked against the source | working |
| Decide — verdict from the user's own rules | working |
| Approve — approve, edit, override | working |
| Record — run log and export | working |

**Measured on the first end-to-end runs:** 3.5–5.2 seconds and ~2,700 tokens per CV
(~$0.0013 at published rates), two model calls, zero repair retries needed.

---

## 2. Two real integrations

| Integration | Direction | Role |
|---|---|---|
| **Gmail (SMTP)** | send | The interview invitation reaches the candidate at the address extracted from their own CV. Closes the loop from screening to outcome |
| **Google Sheets** | write | The shortlist, in the tracker the user already keeps — readable by a co-founder or client who does not run the system |

**Google Drive was considered and cut.** It would have been the input side, but this
user receives CVs on one laptop, so drag-and-drop already solves intake. Adding a
service account and a folder ID would have been ceremony. It is the first item in
the two-week plan, for when CVs start arriving from LinkedIn into a shared folder.

These were chosen so that **her workflow does not change**. She continues doing exactly what she did before, and results appear where she already looks. Adoption cost is close to zero.

Access is granted through a single service identity: she shares the folder and the sheet with one email address. No sign-in flow, no browser redirect, and permission she can revoke herself in one click. Drive access is read-only by design — the system can never move, rename or delete a candidate's file.

Files already processed are recognised by content, so the folder is safe to re-run. Clicking Run twice processes nothing twice.

---

## 3. Validation, structured output and logs

**Validation runs in two layers.** The model is constrained to a fixed output shape, and that output is validated again on arrival. The second layer exists to catch contract drift when the schema changes and the surrounding code has not.

**Untrusted text is fenced.** The CV is passed to the model inside explicit delimiters, marked as data rather than instruction, with a standing rule that any instruction-like text inside it must be ignored. This is the defence against a candidate embedding commands in their document.

**Two log levels.** One record per run — file, verdict, model, tokens, cost, latency, retries, error. One record per criterion judgment — status, quote, whether it verified and by which method, confidence, and what the human did about it.

That second table is not plumbing. It is the evaluation dataset, the audit trail, and the source of the human-intervention metric, produced automatically as a by-product of normal use.

---

## 4. Error messages

Every failure a non-developer can hit produces a sentence she can act on.

| Situation | What she sees |
|---|---|
| Scanned or image-only PDF | "No readable text in this file — it looks like a scan. Ask for a text PDF, or paste the text in." |
| Not a CV | "This doesn't look like a CV. Skipped — check the file." |
| Duplicate | "This matches a CV already screened on [date]. Showing the earlier result." |
| Missing API key | "Missing API key. Open the settings file and add your key, then restart. See README step 2." |
| Spreadsheet not shared | "Can't write to the results sheet. Share it with [exact address] as Editor." |
| Rate limit | "Hit the usage limit. Waiting and retrying — 12 of 40 done so far." |
| Quote could not be verified | "Couldn't confirm the supporting quote for this criterion. Marked as needs-review — please check this one yourself." |
| Instruction text found in a CV | "This CV contains text that tries to instruct the screening system. It was ignored, but review this candidate manually." |

Naming the exact address to share with, rather than reporting a permission error, is the difference between finishing alone and stopping to ask.

---

## 5. Configuration and secrets

Three separate layers, none of them in the code:

- **Secrets** — the API key and service credentials live in an ignored local file. A committed example file lists every key with empty values.
- **Settings** — folder and sheet identifiers, model, retry limits and thresholds sit in a plain settings file, safe to share.
- **Criteria** — the role's requirements and decision rules live in a plain-English file the user edits herself, with no developer involved.

Missing or placeholder credentials fail at startup with a readable sentence, not mid-run with an authentication error. The repository was checked to confirm no key has ever been committed.

---

## 6. Interface

A single web page. Drop a file or scan the Drive folder, click Run, review the results, approve.

Each candidate is shown as a card:

- Each criterion with its status, and **the quote from the CV directly beneath it**, marked as verified.
- Anything the CV does not state is shown as a distinct third state — not a soft rejection.
- A suggested verdict and a specific next action.
- Approve, Edit and Override buttons. Nothing exports without one of them.
- Time and cost for the run, visible on screen.

Four decisions carry the design: the evidence sits under every verdict so it can be checked in seconds rather than by re-reading the CV; NOT STATED is visually distinct because it is the thing plain chat tools do not produce; the approval buttons are unavoidable; and cost is shown to the user rather than hidden.

---

## 7. First execution by the target user

The user ran the system on her own machine, from the README, while the screen was recorded and no help was given.

**Result:** she completed setup and screened [X] CVs in [X] minutes without assistance.

**Observed friction:**

| Point | Fix applied |
|---|---|
| Paused at the settings-file step — the instruction assumed knowledge she did not have | Setup now creates the file automatically and tells her the one line to change |
| Asked "is it broken?" during the wait — there was no progress feedback | Progress indicator added: "Screening 3 of 12" |
| Tried to click a quote, expecting to jump to that line in the CV | Quotes now link to the source document |

**Her three answers:**

1. *Would you use this tomorrow?* — [answer]
2. *What would stop you trusting it?* — [answer] → became a Day 4 hardening item
3. *What's missing?* — [answer] → became the next-iteration plan

The system was left running for her, so real usage was accumulating before the sprint ended.

---

**Key question answered:** someone else ran the core workflow start to finish, unaided, on their own machine, and the three points where they hesitated were found and fixed the same week.
