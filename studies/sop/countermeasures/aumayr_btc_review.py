# Record of the 2026-11-16 review run (lane box, ~/smcm). It reads Aumayr et al.'s
# incentive_compatibility/Bitcoin/output.json and, per point, solves our cap-30 lower
# bound (pto) and upper bound (sop_mdp_crosscheck.py btc --bound upper, run by file
# path from a pre-reorganisation checkout because `-m` fails on its import).
# Output: studies/sop/data/countermeasures/aumayr_bitcoin_review_20261116.jsonl
"""Review: Aumayr's shipped Bitcoin values vs our cap-30 lower (pto) and upper (crosscheck) bounds."""
import contextlib, json, os, subprocess, sys
sys.path.insert(0, os.path.expanduser("~/smcm/monerosim"))
from studies.sop.countermeasures.nakamoto import NakamotoModel
from studies.sop.countermeasures.vendor.blockchain_mdps import PTOSolver
from studies.sop.countermeasures.vendor.blockchain_mdps.base.blockchain_mdps.sparse_blockchain_mdp import SparseBlockchainMDP
data = json.load(open(os.path.expanduser("~/smcm/aumayr_bitcoin_output.json")))
for key in sorted(data, key=lambda k: [float(x) for x in k.split("_")]):
    a, g, cap = (float(x) for x in key.split("_"))
    m = NakamotoModel(a, g, int(cap))
    with contextlib.redirect_stdout(sys.stderr):
        p, _, _, _ = PTOSolver(m, expected_horizon=10**5).calc_opt_policy(epsilon=1e-7, max_iter=400000)
    lower = SparseBlockchainMDP(m).calc_policy_revenue(p)
    upper = None
    if 0 < a < 0.5:
        out = subprocess.run([os.path.expanduser("~/mdpcheck/venv/bin/python"), "scripts/sop_mdp_crosscheck.py", "btc",
                              "--alpha", str(a), "--gamma", str(g), "--T", str(int(cap)), "--T-policy", "0",
                              "--no-library", "--bound", "upper"], cwd=os.path.expanduser("~/monerosim"),
                             capture_output=True, text=True).stdout.strip().splitlines()
        upper = json.loads(out[-1])["hand_written"] if out else None
    theirs = data[key]
    print(json.dumps({"alpha": a, "gamma": g, "cap": cap, "theirs": theirs, "our_lower": lower, "our_upper": upper,
                      "theirs_minus_lower": theirs - lower}), flush=True)
