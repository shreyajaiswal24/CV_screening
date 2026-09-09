# Limitations

Stated plainly, because a system whose limits are documented is more useful than
one whose limits have to be discovered.

## What it fundamentally cannot do

**1. It cannot read what is not written.** Where a CV omits something, the
system marks it NOT STATED and tells you to ask — it does not go and find out.
It will not check LinkedIn, a portfolio, or GitHub.

**2. It judges evidence, not people.** No signal on trajectory, communication,
or whether three short tenures is a pattern or bad luck. The human still reads
the shortlist.

**3. It is only as good as the criteria.** Vague criteria produce vague
assessments, and the system will not tell you your criteria are poor. *"Good
with data"* has nothing to quote against; *"has built and shipped an ETL
pipeline in Python"* does.

**4. A candidate's outcome depends on which version of their CV they submit.**
Found in real use: the same person, two CV versions, scored LOW FIT and MEDIUM
FIT. A well-written CV from a weaker candidate can outrank a poorly-written one
from a stronger candidate. Duplicate-person detection surfaces this when it
happens, but cannot correct for it.

## Scope boundaries

**5. English CVs only.** Others are flagged, not assessed.

**6. No scanned or photographed documents.** Detected and routed to a human;
OCR is out of scope.

**7. No calendar access or interview booking.** The system drafts one invitation
asking for availability. Scheduling happens between the two people.

**8. Single user, single role at a time.** No accounts, no multi-tenancy, no
parallel roles.

**9. Intake is drag-and-drop only.** Pulling CVs from cloud storage was built
and then cut — the current user receives CVs on one laptop, so it would have
added a service account and a folder ID for no gain. First item in the two-week
plan.

## Reliability and measurement

**10. Non-determinism at temperature 0.** The same CV screened twice can produce
a different status on one criterion. Distributed inference is not perfectly
deterministic. This puts a real ceiling on reproducibility that no amount of
prompt engineering removes.

**11. Evidence-strength detection is heuristic.** It classifies a quote by the
section heading above it. Unusually formatted CVs can be mis-tiered.

**12. The experience check is only as good as the extracted dates.** Years of
experience is computed in code from the CV's date ranges — more reliable than
asking the model, but a role written without clear dates is invisible to it. One
real CV computed 0.5 years when several roles were present. Since experience can
be a *required* criterion, a missed date range can reject a candidate on
arithmetic rather than judgment.

**13. Validated on 12 cases for one role.** Accuracy at other seniorities, in
other functions, or on CVs from other regions is unmeasured.

## Cost and throughput

**14. Free-tier throughput is about 40 CVs per day.** 200,000 tokens/day at
roughly 5,000 tokens per CV. Enough for one open role; a 500-applicant role
would need a paid tier or a cheaper first-pass model.

**15. Screening takes about a minute per CV** on the current free-tier model,
because the rate limiter correctly waits rather than firing requests that would
be refused. This is infrastructure, not the system.

## The one that matters most

**16. This is not a fairness audit, and must not be presented as one.**

The system reduces *inconsistency* — the same criteria are applied to candidate
40 as to candidate 1, which manual screening demonstrably fails to do. That is
one source of unfairness, and addressing it is a genuine improvement.

But the system has **not** been tested for demographic bias. It reads names,
universities, locations and employers, and no measurement has been made of
whether those influence its judgments. A bias audit is required before any
wider rollout, and is listed in the two-week plan.

The design mitigations that exist are structural rather than measured: the
system never rejects anyone, every judgment carries a quote a human can check,
and gaps are surfaced as questions rather than silently resolved. Those reduce
the opportunity for unexamined bias to become an unexamined decision. They do
not prove its absence.
