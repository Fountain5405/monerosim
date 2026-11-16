# Moved: the countermeasure MDP code

On 2026-11-16 the code that was here (the MDP framework for proof-of-work
countermeasures: reorg tags, the revenue / disruption objectives, the exact
average-reward solver, the Nakamoto and SoP models) moved to its own
repository, licensed GPL-3.0 to match the reference implementations it ports
from:

<https://github.com/Fountain5405/pow-countermeasure-mdp>

Its last state here is monerosim commit `e093a4d7`; the docs and data that
cite `studies/sop/countermeasures/...` refer to that commit. Results stay in
monerosim: `studies/sop/docs/20261113_countermeasure_mdp_plan.md` and
`studies/sop/data/countermeasures/`.
