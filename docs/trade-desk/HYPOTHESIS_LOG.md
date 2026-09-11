# Astra hypothesis log

**Initial state: empty.** This file contains instructions and a reusable
template only. No market hypothesis has been entered.

Add an entry only after Astra independently identifies a possible
relationship in prospective Trade Desk episodes. Follow the Blind Discovery
and outside-memory boundary in [MANDATE.md](MANDATE.md). Operator beliefs or
remembered outside conclusions are OPERATOR PRIOR, not evidence, and must
not be imported as starting hypotheses.

Link supporting and contradictory episodes to their frozen T0 decisions
and later T1 reviews. Include WAIT, NO TRADE, mistakes, and losses where
relevant. Record how the sample was selected and counted; do not count only
successful examples or silently change the claim to fit known outcomes.
Confidence is a current judgment, not proof or automatic trading authority.

Keep the live trader's model/effort separate from the hypothesis author's or
reviewer's. Identify mixed-model and interrupted episodes in supporting and
contradictory samples; do not pool them as clean Medium or Ultra evidence.
Ultra's post-episode observations must retain their review provenance and may
not be backdated into Medium T0 reasoning. Model superiority is not a seeded
hypothesis and must not be assumed.

For every emerging belief, ask what would disprove it, which episodes
contradict it, whether another variable explains the result, and whether
the interpretation changed after seeing the outcome. Finding that a
hypothesis is wrong is useful research progress.

Use one status:

- `EXPLORATORY`
- `DEVELOPING`
- `CHALLENGED`
- `REJECTED`
- `ROBUST_ENOUGH_FOR_FURTHER_TEST`

Never label a hypothesis “proven.” Keep rejected hypotheses and contradictory
evidence. Append dated revisions or status updates, preserving the previous
statement and reasoning; materially changed claims should receive a linked
new ID. No status converts a hypothesis into a deterministic trade rule.

## Reusable entry template — not an active hypothesis

- **Hypothesis ID:** [unique ID]
- **Statement:** [Astra-generated claim and its stated scope]
- **First observed:** [date, episode ID and decision / review links]
- **Author / review provenance:** [model and reasoning effort; prospective observation or later review]
- **Supporting episodes:** [IDs and relevant observations, or none]
- **Contradictory episodes:** [IDs and relevant observations, or none yet identified]
- **Approximate sample count:** [count; unit, selection basis and review cutoff]
- **Live-model sample breakdown:** [model/effort counts; mixed-model and interruption flags; comparison inclusion/exclusion basis]
- **Current confidence:** [assessment and limitations]
- **Open questions:** [uncertainties and alternative explanations]
- **What would falsify it:** [observable counterevidence; define before evaluating later episodes]
- **Status:** [one status from the list above]

### Dated update template

- **Update date / hypothesis ID:** [timestamp and reference]
- **New episode evidence:** [supporting, contradictory and ambiguous observations]
- **Updated count / confidence / status:** [values and reason for change]
- **Remaining questions / next prospective observation:** [what remains unresolved]
- **Statement revision or linked successor (if any):** [preserve original wording and explain the change]
