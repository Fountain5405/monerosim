"""At each REVEAL in the race model (perish rule, param_stubborn), the same accounting the honest
daemons' SIM-SoP-DEC records give at the attacker's reveals: blocks per side, objects per block
(attacker: blocks + embedded shares; honest: blocks + embedded + pending), pending shares.
Usage (from a tree with scripts/): python model_reveal_objects.py ALPHA K W DAYS SEED KNOBS..."""
import statistics as st
import sys

sys.path.insert(0, ".")
from scripts.sop_policy import REVEAL, param_stubborn      # noqa: E402
from scripts.sop_rl import legal_fallback, race_env        # noqa: E402

alpha, K, w, days, seed = float(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), float(sys.argv[4]), int(sys.argv[5])
knobs = {k: int(v) for k, v in (kv.split("=") for kv in sys.argv[6:])}
env = race_env(alpha, days, seed, K=K, w=w, perish=True)
W = env.window_obs
rec = []
o = env.obs()
while not env.done:
    act = legal_fallback(param_stubborn(o, W=W, **knobs), env.legal())
    if act == REVEAL:
        rec.append((len(env.att_blocks), len(env.hon_blocks), env.att_w, env.hon_w, env.hon_pending, env.att_pending))
    o, _, _ = env.step(act)
a = sum(r[0] for r in rec); h = sum(r[1] for r in rec)
print(f"alpha {alpha} K={K} w={w} window {W}: {len(rec)} reveals, share {env.stats.attacker_revenue_share:.3f}")
print(f"  blocks attacker/honest: {a / len(rec):.2f} / {h / len(rec):.2f}")
print(f"  embedded shares per block attacker/honest: {sum(r[2] - r[0] for r in rec) / a:.2f} / {sum(r[3] - r[1] for r in rec) / max(1, h):.2f}")
print(f"  pending at reveal attacker/honest: {st.mean(r[5] for r in rec):.2f} / {st.mean(r[4] for r in rec):.2f}")
print(f"  objects per block attacker (blocks + embedded) / honest (blocks + embedded + pending): "
      f"{sum(r[2] for r in rec) / a:.2f} / {sum(r[3] + r[4] for r in rec) / max(1, h):.2f}")
print(f"  objects attacker / honest: {st.mean(r[2] for r in rec):.1f} / {st.mean(r[3] + r[4] for r in rec):.1f}")
print(f"  reveals with fewer attacker blocks: {sum(1 for r in rec if r[0] < r[1])} of {len(rec)}")
