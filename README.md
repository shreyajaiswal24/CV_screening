# CV Screening

Screens CVs against your criteria and shows you **the evidence for every
judgment**, quoted from the CV itself.

It does not decide who to hire. It reads each CV, checks it against the
criteria you wrote, quotes the line that proves each answer, and clearly says
**NOT STATED** when the CV is silent — it never guesses.

You approve, edit, or override everything before it counts.

---

## Setup — 3 steps, about 5 minutes

**1. Install**

```
git clone <this repo> && cd cv-screening
./setup.sh
```

**2. Add your key**

Open the file called `.env` and paste your key after `GROQ_API_KEY=`
Get a free one at <https://console.groq.com/keys>.

**3. Start**

```
./run.sh
```

Then open <http://localhost:8000> in your browser.

---

## Your first run

1. Click **Criteria** and write what you're looking for, in plain English.
   Tick "Must have" for anything a candidate cannot be without.
2. Drag some CVs onto the page — PDF, Word or text. Several at once is fine.
3. Read the results. Approve, change, or skip each one.
4. Click **Export results** when you're done.

There are two example CVs in `samples/` if you want to try it before using
real ones.

---

## Reading the results

| What you see | What it means |
|---|---|
| **MET** + a quote | The CV says so. The quote is checked against the document. |
| **NOT MET** + a quote | The CV shows the candidate does *not* meet this. |
| **NOT STATED** | The CV doesn't say. Nothing was assumed. **You need to ask.** |
| `strong — from a role` | The quote came from a dated job or project. |
| `weak — from a skills list` | The word appears in a keyword list only. Not proof. |
| ⚠️ **Needs your attention** | Something is uncertain. Read this one yourself. |

**Verdicts**

- **ADVANCE** — every required criterion met with solid evidence.
- **REVIEW** — something is missing, weak, or uncertain. Your call.
- **REJECT** — a required criterion is clearly not met.
- **SKIPPED** — the file couldn't be read. The message tells you why.

---

## What you must check before approving

1. **Anything with a ⚠️ flag.** Always.
2. **Anything marked NOT STATED.** The system will never guess, so it's on you
   to ask the candidate.
3. **Your top few candidates, in full.** The system reads the words on the
   page. It cannot see that three previous employers all folded, or that
   someone's trajectory is unusual. That judgment is still yours.

---

## Changing what you screen for

Click **Criteria** in the app, or edit `criteria.yaml` directly. Write
requirements the way you'd say them out loud:

```
- id: llm_experience
  description: "Hands-on experience building with large language models"
  required: true
```

Vague criteria produce vague assessments. "Good with data" will not work as
well as "has built and shipped an ETL pipeline in Python".

---

## What it will NOT do

- It never rejects a candidate. It recommends; you decide.
- It doesn't find or source candidates.
- It doesn't send email or schedule anything.
- It doesn't write to your ATS.
- It doesn't rank candidates against each other.
- It doesn't judge soft skills or culture fit.
- English CVs only.
- Scanned or photographed CVs are detected and handed back to you — it will
  not try to read an image.

---

## When something goes wrong

| Message | What to do |
|---|---|
| No readable text — looks like a scan | Ask the candidate for a text PDF, or paste the text in. |
| This doesn't look like a CV | Check the file — it may be the wrong attachment. |
| Matches a CV already screened | It's a duplicate. The earlier result stands. |
| Missing API key | Open `.env`, add your Groq key, restart. |
| Can't write to the results sheet | Share the sheet with the address shown in the message. |
| Hit the usage limit | Wait a minute and run again. Finished candidates are saved. |
| Couldn't confirm the supporting quote | The system wasn't sure the quote was real, so it downgraded it. Check that one yourself. |
| ⚠️ Text trying to instruct the system | The CV contains an attempt to manipulate screening. It was ignored. **Review this candidate manually.** |

---

## Data handling

- CVs are processed on your machine. Only the extracted text is sent to the
  model, over an encrypted connection.
- Real CVs live in `data/`, which is excluded from version control. They are
  never committed.
- The example CVs in `samples/` and the test set in `eval/cases/` are
  anonymised — names, emails, phone numbers and links replaced.
- Nothing is used to train any model.
- To delete everything: remove the `data/` folder.


---

## Running it online (optional)

The app can be deployed so it is reachable from anywhere.

**Render** (free): New → Web Service → connect this repo. It reads `render.yaml`
automatically. Then set these in the dashboard under Environment:

| Variable | Value |
|---|---|
| `GROQ_API_KEY` | your Groq key |
| `APP_PASSWORD` | **required** — a password only you know |
| `SMTP_USER` | your Gmail address |
| `SMTP_PASSWORD` | your Gmail **App Password** (16 characters, no spaces) |

You get a URL like `cv-screening.onrender.com`, which asks for the password
before it shows anything.

### Why the password is required

The deployed app sends interview invitations **from your own Gmail account**.
Without a password, anyone who found the URL could upload a CV with any address
in it and send mail as you — which is a spam vector on your personal account.

So the rule is enforced in code: **a hosted instance without `APP_PASSWORD` stays
in dry-run and will not send anything.** Set the password, and real sending works
exactly as it does locally — GREAT FIT only, address taken from the CV, and two
explicit clicks.

### Two other things to know

- **The free tier sleeps after ~15 minutes idle.** The first request after a
  quiet period takes about 30 seconds to wake up.
- **The run log resets when the instance restarts**, because the free tier has
  no persistent disk. For real day-to-day use, run it locally or add a paid disk.
