---
name: tone-check
description: Tone-escalation guard for public copy on the Protect South Portland sites. Use whenever an agent writes, rewrites, edits, or reviews any sentence that the PSP site publishes (site/pages/*.html, build.py chrome, newsletters, emails, banners) — including "polish", "humanizer", "style", "copy edit", "review", or "gate" passes on that copy — so the agent never escalates tone beyond what sanctioned sources already say, even accidentally. Trigger on any public-copy diff in this project, not only on requests that mention "tone".
---

# Tone check: agents add no fire

The purpose of this project's public site is to carry **Protect South Portland's own advocacy voice**. The agents in this build (orchestrator, builder, reviewers) exist to restructure, clean up, and fact-check that voice — not to amplify it. A tone review proved this matters: the language-strength review of this thread found the agents contributed real strength changes in only three places, all near-equivalent rephrasings, while everything strong on the site traces to approved human sources. This skill exists so every future edit keeps that property.

## Why "stronger than intended" is the failure mode

LLM editing defaults smooth prose into confident prose: hedges get dropped, sentiment becomes verdict, risk claims sharpen. On most projects that is a style preference. Here it is **governance**: this site speaks for a real community organization to a city council, state DEP, and news audience, and the words are other people's decisions (Mindy's, Alex's, Cristos's). An unrequested escalation either overstates what the evidence carries (a lawyer's dismissal route) or puts more forceful words in PSP's mouth than PSP spoke with. De-escalation has its own hazard — it softens approved advocacy without sanction — so the rule is bidirectional and exact.

## Sanctioned-source tiers

Classify every sentence before touching it. When you cannot classify it, ask — do not guess.

**Tier A — Human-authored, verbatim, never tone-edited.**
Mindy Hull's docx copy (`PSP website addition 10.6.26.docx`, mirrored under `mindy-email-attachments/2026-10-06_*/` and `2026-10-12_*/`) — operator-sanctioned 2026-10-13. Includes the homepage banner, the 120-tanks/six-companies narrative, "bad neighbors, profiting off harm to our community," the Citgo/Lincoln-Street sentences, "consistently and dramatically exceeded," the 12x reading, and both CTAs. Copy the operator or Mindy later approves gets the same status once recorded in the ledger.

**Tier B — Commissioned or baseline copy.**
Sentences a ledger row commissioned; the old Wix site's phrasing (the baseline commitment level for anything pre-existing); gap-analysis dispositions already approved.

**Tier C — Verified record.**
City filings, DEP reports, court history, signed evidence files (`yard-south-withdrawal-evidence.md` etc.). Facts may be restated more precisely but must never be stated *more conclusively* than the source. Note what the source itself hedges: DEP documents say "exceedance," "long-term average below X," or "guideline" — a rewrite may not convert those into "standards were violated" or "certainly cause."

## The escalation test (apply to every edit diff)

A change escalates tone if it does any of these, relative to the source sentence:

1. **Removes a hedge that carries meaning** ("feels … not acceptable" → "finds it unacceptable" is near-equivalent and allowed; "have the potential to harm" → "can harm" is near-equivalent and allowed; but "It seems the City needs" → "The City needs" sat right at the line — allowed here, but flag it)
2. **Increases certainty beyond the evidence** — "data has shown" → "data has confirmed"; "readings exceeded the guideline" → "standards were violated"
3. **Escalates blame or accusation** toward any named party (Citgo, Buckeye, Global Partners, City officials) beyond the source's framing
4. **Heightens health/safety risk claims** — stronger outcomes, larger affected populations, removed qualifiers
5. **Adds urgency, fear, or demands** the source did not make

Near-equivalence is the judgment line: same claim, same force, cleaned sentence = pass. Anything past it = fail. When within the tolerance band of the humanizer gate, prefer the *weaker-or-equal* rewording; if the stronger one is clearly fine, flag it in the report anyway so the operator sees the delta.

## Required process

1. **Side-by-side before/after** for every sentence whose meaning is touched — quote both, always. No narrative-only claims like "meaning preserved."
2. **Classify each change** into one of four buckets in the report: `sanctioned` (traceable to Tier A/B/C), `evidence-supported` (with the evidence named), `new-assertion` (no old counterpart — requires explicit operator approval before it ships or, if already shipped, before the pattern repeats), `judgment-call` (present both fix and sign-off options; never silently choose).
3. **Tier A is untouchable on tone.** If Tier A copy appears to need a factual correction (a wrong term, a citation gap), do **not** edit the copy — record a fact-flag in the change-request ledger (`website-change-requests.md`) addressed to the original author for their next revision. Real example from this project: "the state's ambient air quality standard" is officially the DEP Ambient Air *Guideline* (AAG) — noted for Mindy; the site kept her word.
4. **Reviewer bar.** Tone review of public copy runs on the full-strength model (`ollama-cloud/glm-5.3` or higher — flash does not qualify; same bar as the release gate). The reviewer verifies against the actual diff and the evidence files, not against the builder's changelog. Max 3 revise-and-rereview rounds; escalate to the operator after that.
5. **Cross-page consistency is part of the check.** If the same fact appears on multiple pages (index, tank-farms, act-now's form email), one escalated instance anywhere fails the review for the fact everywhere.
6. **Pre-approved lines.** Copy previously dispositioned by the operator (e.g., the docx set, the withdrawal archival framing, roster hedges) is recorded in the ledger with its status; do not re-litigate it on tone in future gate cycles. Check the ledger's latest rows before flagging anything.

## Report format

```
# Tone check: <trigger / page set>
Verdict: PASS | FAIL | PASS-WITH-FLAGS
Per page: <page> → SAME | STRONGER | WEAKER | MIXED (one line why)
Side-by-side items (only actual deltas): [old → new, bucket, evidence]
Judgment calls: [fix option vs sign-off option]
New assertions needing operator sign-off: [list or "none"]
```

## Case studies from this project (2026-10-13 review)

- "PSP feels … is not acceptable" → "PSP finds it unacceptable …" — allowed (near-equivalent; bucket: judgment-call flagged, operator kept)
- "have the potential to harm" → "can harm" — allowed (near-equivalent)
- "It seems that the City … needs" → "The City needs …" — allowed, hedge drop flagged
- "consistently and dramatically exceeded" — Mindy's Tier A wording; operator ruled verbatim; the reviewer had correctly noted "dramatically" fit South Portland Terminal (4.5–26x) better than Citgo (mostly ≤2.5x) but facts live with the author
- "12x higher" — kept; DEP quarterlies actually show 11.6x and 26.5x, so it is the conservative figure; citation to the quarterly report was noted as optional
- The Yard South archival rewrite — not tone drift: commissioned by verified withdrawal records

## Boundaries

- This skill covers **public copy only** (anything the mirror publishes or chrome that builds it). Working notes, ledger rows, and internal messages are where tone debates belong.
- It does not replace the release-gate humanizer/style review (draft-artifact scan, private-surface bans) — it runs *alongside* it. A sentence can pass style and still fail tone, and vice versa.
- The fact-correcting side of this skill (guideline vs standard, conservative numbers) never blocks publication by itself; it becomes a ledger note. Only *escalation* is a gate-failing defect on this project.