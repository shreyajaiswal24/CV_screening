# 5-Minute Demo Video Script

Read this aloud. Practise once. Record on the second or third take.
Keep the browser at http://localhost:8000 and a folder of CVs ready.

---

## 0:00 – 0:45  The problem

**Show:** an inbox or folder full of CVs.

**Say:**
- "When a role opens, 40 to 70 applications arrive over two weeks."
- "Someone has to open each one, check it against the same criteria, and decide."
- "I timed myself doing this by hand. The first CV got [X] minutes of attention.
  The sixth got [X]."
- "The criteria never changed. The attention did."
- "And two weeks later, nobody can say why a particular person was rejected,
  because nothing was written down."

---

## 0:45 – 1:15  Why not just ChatGPT

**Show:** the ChatGPT screenshot, or the arm B baseline output.

**Say:**
- "The obvious answer is to paste the CV into ChatGPT. I tested that properly."
- "It writes a good-looking assessment in seconds."
- "But here — it said this candidate meets the location requirement. The CV
  never states a location. It filled the gap instead of flagging it."
- "It also gives no consistent format, keeps no record, and forgets the criteria
  every session."
- "Generation is already solved. Checking is not. That gap is what I built."

---

## 1:15 – 2:30  Live run

**Show:** drag a real CV in, let it run.

**Say:**
- "This is the system. I drop in a CV."
- "It reads the document, then judges it against each criterion separately."
- "Every judgment comes with the exact line from the CV that proves it."
- "And that quote is checked by code — a plain text search against the
  document. Not by another AI."
- "That matters. A model cannot be trusted to confirm its own honesty about
  something checkable."
- "Here — this criterion says NOT STATED. The CV genuinely doesn't mention it.
  So the system doesn't guess. It tells me to ask the candidate."
- "This one is marked weak evidence: the skill appears in a keyword list, but
  never in an actual role. Listed is not the same as demonstrated."

---

## 2:30 – 3:15  The non-developer experience and the outcome

**Show:** the Criteria editor, then approve a GREAT FIT and send the invitation.

**Say:**
- "Criteria are set once, in plain English. Skills, minimum experience,
  location. No code, no retyping per role."
- "Nothing happens automatically. I approve, edit, or override every judgment."
- "For a great fit, the system drafts an interview invitation — addressed to the
  email it read from the CV itself."
- "It never guesses an address, and it never sends below great fit."
- "I read it, and I click send."

**Show:** the received email in Gmail.

- "That's a real CV in, and a real interview invitation out."

---

## 3:15 – 4:15  Evaluation and failure

**Show:** the evaluation output, then the injection case.

**Say:**
- "I built a 12-case test set: six real CVs, three edge cases, three designed to
  fail. I wrote the correct answers by hand before running anything."
- "Results: [X] of 12 passed. Zero fabricated quotes."
- "Now the failures — this is the interesting part."
- "This CV contains hidden text telling the system to mark the candidate as a
  perfect match. It's ignored, flagged, and forced to human review."
- "This one isn't a CV at all. It's rejected before spending anything."
- "And here's a real bug my evaluation caught: the system was marking
  candidates NOT MET while quoting a skills list that contained the very skill.
  On a required criterion that's a hard rejection. It should have said NOT
  STATED and asked."
- "I found eleven defects while building this. All eleven were in my own code.
  None were the AI getting things wrong."
- "Five of them were found by someone using the interface, not by me testing it."

---

## 4:15 – 5:00  Results, limitation, next

**Show:** the results table.

**Say:**
- "Results: [X] minutes per CV by hand, down to under a minute of attention."
- "Every decision now has a recorded reason. Before, almost none did."
- "Zero fabricated evidence across the test set."
- "The biggest limitation: it reads what is written. It cannot see that a
  candidate's three previous employers all failed. I still read the top five
  myself — the system exists to give me time to do that properly."
- "It has also not been tested for demographic bias. It reduces inconsistency,
  which is one source of unfairness. It does not prove the absence of others."
- "Next: automatic intake from LinkedIn into a shared folder, a clarification
  email for the middle group instead of only the top, and a bias audit before
  anyone else uses it."

---

## Recording notes

- **Script it, don't improvise.** Five minutes goes fast.
- **Show, then say.** Let the screen move first, then explain.
- **Use one real CV throughout** so the viewer follows one story.
- **Have the Gmail tab already open** so the email is instant.
- **Screen-record at 1080p.** OBS or the Windows Game Bar (Win+G) both work.
- **End on the limitation, not the win.** It signals you know exactly what you
  built and what you didn't — and evaluators trust the numbers more because of it.

## Things NOT to say

- Don't claim it "screens candidates automatically" — it never decides.
- Don't say "100% accurate" — give the real number.
- Don't hide that the daily free-tier limit is about 40 CVs. Say it plainly.
