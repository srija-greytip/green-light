## The problem

greytHR's expense module (Penex) lets employees submit expense claims — amount, category, bill details, and supporting attachments. Today, **every** claim goes through **manual approval**, even routine, obviously-genuine ones. This **slows** reimbursements for employees and consumes reviewer time for admins.

Our product backlog contains a planned feature (EC-1062): the system should compute a **genuineness score** for each submitted claim, and claims scoring above an admin-defined threshold should be **auto-approved** — only the rest go for manual review.

We can set this auto approve/reject from rules defined in policies but there we cannot define it based on genuineness. Also we need to give a statement or **reason** on the score.

The feature is not scoped yet. Before the team builds it, we need research that answers the hard questions.

## The questions
1. **Signals** — Given historical claim data, which patterns actually indicate whether a claim is genuine or suspicious? What can you derive from the data that isn't obvious from a single claim on its own?
2. **Scoring** — How should a 0–100 score be computed? What are the candidate techniques, and what are the trade-offs between them? Keep in mind this is a finance/audit feature: decisions must be **explainable** (an admin will ask "why was this flagged?") and **consistent** (the same claim must get the same score every time).
3. **Thresholds** — The ticket suggests auto-approving above "60 or 70." That's a guess. What _should_ the threshold be, and how would you prove it? What are the measurable consequences of setting it higher or lower?
4. **Build vs API** — Could we skip building anything and simply send each claim to an LLM API with a good prompt? Under what conditions is that better or worse? Answer with evidence, not intuition.
5. **Evaluation** — We have no labeled fraud data. How do you measure whether your scorer works at all? Design an evaluation strategy and be honest about its limitations.

## What you'll deliver
1. **A problem summary** (early) — the problem restated in your own words, plus an inventory of what data is available.
2. **An exploration report** — what the historical claim data looks like and what it can/cannot support.
3. **A working prototype** — something that takes a claim and returns a score with human-readable reasons. Local is fine; no deployment needed.
4. **An evaluation with numbers** — how well it catches bad claims, at what cost to genuine ones, across candidate thresholds.
5. **A comparison** — your approach vs the "just call an LLM API" approach, measured on the same test data.
6. **A design document + demo + final presentation** — the team should be able to pick up EC-1062 later and find the design questions already answered with evidence. You'll present to Vinay, Surya, and the PM.

## How we'll work
- **Design-first:** before writing significant code for any phase, write a short note (half a page is fine) on what you plan to do and why — we review it together, then you build. Expect your first plan to change after review; that's the process working.
- **Weekly pairing session** (30–60 min): design reviews, debugging together, or walking through your analysis.
- **Daily check-in** (15–20 min): unblock, review progress, adjust.
- **Everything in Git** from day one; work is reviewed PR-style with comments explaining _why_.
- **Keep a running log** of what you learned and where you got stuck each week — we'll use it in retros.
- **Ask questions early.** Ambiguity in this brief is intentional in places — identifying what needs clarification is part of the job.
## What success looks like
Not "shipped a model." Success is: the team can make confident, evidence-backed decisions about EC-1062 because of your work — which signals to use, which technique, which threshold, and whether to build in-house at all. If your research changes what we build (or stops us from building the wrong thing), that's the win.

