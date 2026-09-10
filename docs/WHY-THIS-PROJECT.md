# Why this project

The reasoning behind SIFT, written as answers to the questions that get asked.

---

## Why did you choose CV screening?

Because it is the clearest example of a problem where **the bottleneck is not
producing the work, it is checking it** — and because it fails a real person on
both sides.

Three things made it the right choice:

**It recurs, and it never gets easier.** Every open role brings 40 to 70
applications. That happens again for the next role, and the next. Most tasks get
faster with experience. This one does not, because the expensive part is not
judgment — it is holding four criteria in your head, applying them consistently,
and recording why. That cost is the same on your hundredth CV as your first.

**It has an objective answer.** "Does this CV state three years of Python?" is
checkable. That matters enormously for a five-day sprint: it means the system
can be evaluated properly instead of assessed on taste. A problem you cannot
measure is a problem you cannot prove you solved.

**It fails two people at once.** The recruiter loses an evening. The candidate
loses a fair hearing. That second one is the part most people skip past, and it
is the reason the project is worth building.

---

## What is the actual human problem?

Not slowness. **Inconsistency caused by attention decay.**

When I timed the manual process, the pattern was immediate: the first CV got
several minutes of careful reading. By the sixth, it was seconds. The criteria
had not changed. The attention had.

Follow that to its conclusion. The person who applied on Monday morning gets a
careful reading. The person who applied at 3pm on Friday, when the reviewer is
on candidate number forty, gets twenty seconds. Same role, same criteria,
completely different hearing — decided by when their email happened to arrive.

Nobody intends that. It is a physical limit on human attention. But the effect
on the applicant is real, and it is invisible, because nothing is recorded.

That is the second half of the problem: **no memory**. Ask two weeks later why
a particular person was rejected, and the honest answer is usually "I don't
remember." The decision existed for about four seconds and then evaporated.

---

## Why build a system instead of just using ChatGPT?

This is the question the whole project turns on, and the answer came from
testing it properly rather than assuming.

ChatGPT writes an excellent candidate assessment in about ten seconds. Fluent,
well-structured, confident.

Then I gave it a CV that never mentions where the candidate lives, and asked
whether they meet a location requirement. **It said yes.** It did not lie —
it filled a gap, the way a helpful assistant does, because a plausible answer
felt more useful than an admission of ignorance.

That is the whole thesis in one example:

> **Generation is solved. Verification is not.**
>
> A language model will write a beautiful, confident, unverified assessment.
> The expensive and risky part of screening is not writing the assessment —
> it is knowing whether to believe it. That work is still entirely on the human,
> and it is exactly the work that gets skipped under time pressure.

So the system is not a better writer. It is a **checking layer**. That reframing
is the reason it exists, and everything in the architecture follows from it.

---

## What does that mean in the design?

**The verifier contains no model.** The model produces a quote claiming to come
from the CV. Code then searches the document for that text. If it is not there,
the judgment is rejected.

This sounds obvious. It is not what most systems do. The instinct is to ask a
second model to check the first — but a model asked to confirm its own honesty
about a checkable fact is not a check, it is a second opinion from the same kind
of thing that made the mistake. So the check is a text search. Boring,
deterministic, and it is the only reason "zero fabricated evidence" is a claim I
can actually defend.

**NOT STATED is a first-class answer.** Most systems have two states: meets, or
does not meet. This one has three. If the CV is silent, the answer is "the CV
does not say" — never an inference.

That distinction is the difference between rejecting someone and asking them a
question. My own evaluation caught the system getting this wrong: it was marking
candidates NOT MET while quoting a skills list that contained the very skill.
On a required criterion, NOT MET is a hard rejection. NOT STATED is an email.
Same candidate, completely different outcome.

**Evidence has strength.** A technology named in a `Skills:` list is not proof
that anyone used it. A quote from a dated role is. Only the second kind counts
toward the score. This came from a real CV that listed a dozen frameworks and
had used none of them in any job.

**The system never decides.** It produces evidence and a recommendation; a human
decides. That is not modesty or hedging — it is the correct allocation. The
model is good at reading unstructured prose and finding the relevant line. It is
not good at knowing whether a gap in someone's CV is a red flag or a maternity
leave. Keeping the decision human is not a limitation of this version; it is the
design.

---

## What actually changes for the person using it?

**Candidate 40 gets the same reading as candidate 1.** The criteria do not get
tired. This is the real improvement, and it is a fairness improvement more than
an efficiency one.

**Every decision has a reason attached to it.** Not a score — the actual quoted
line from the CV. Two weeks later, "why did we reject him?" has an answer that
took two seconds to find.

**Gaps become questions instead of silent rejections.** When a CV does not
mention something, the system says so and drafts the question. Previously that
candidate was either guessed about or quietly dropped.

**The evening comes back.** That is the headline number, and it is the least
interesting of the four.

---

## What did you deliberately not build, and why?

**No sourcing, no scheduling, no ATS integration, no candidate ranking.** Each
of those is a different product.

**No cloud intake.** I built the Google Drive integration and then cut it. The
user receives CVs on one laptop, so drag-and-drop already solved intake, and
adding it would have meant a service account and a folder ID for no gain. It is
first in the two-week plan for when CVs start arriving from LinkedIn into a
shared folder. Building the pipeline before the pipeline exists would have been
speculative.

**No retrieval or vector store.** A CV is two to four pages and fits in the
model's context whole. Adding retrieval would have been decoration.

Cutting things is not what is left over after running out of time. It is the
part of the work that decides whether the rest is any good.

---

## What did you learn that you did not expect?

**Eleven defects, and all eleven were in my own code.** None were the model
being wrong. That was not what I expected going in.

**Three of them were in the checking machinery itself** — the verifier raising
false alarms on honest quotes, the evaluation seeder quietly preserving stale
answers, the rate limiter enforcing a budget the API does not have. A bug in the
thing that measures is worse than a bug in the thing being measured, because it
is invisible in the results.

**Five were found by someone using the interface, not by me testing it.** They
surfaced within minutes: a disabled button with no explanation, an export that
duplicated rows, a log full of temp filenames, six CVs taking half a minute
before anything was usable, and a verdict label that told the user nothing about
how good the candidate actually was. I would have shipped every one of them.

That is the strongest argument for putting the system in a real user's hands on
day three rather than day five.

---

## Where does it still fall short?

**It reads what is written.** It cannot see that a candidate's three previous
employers all failed, or that a two-year gap was caring for a parent. I still
read the top five candidates myself. The system exists to give me the time to do
that properly, not to replace it.

**The same person can score differently on two versions of their own CV.** I
found this when duplicate detection matched two files by email address: one
scored LOW FIT, the other MEDIUM. A well-written CV from a weaker candidate can
outrank a badly-written one from a stronger candidate. The system surfaces this
when it happens. It cannot correct for it.

**It has not been tested for demographic bias.** It reduces inconsistency, which
is one source of unfairness, and that is a genuine improvement. It does not
prove the absence of others. It reads names, universities and locations, and I
have not measured whether those influence its judgments. A bias audit comes
before anyone else uses it.

I would rather state that plainly than let a screening tool imply a fairness
guarantee it has not earned.
