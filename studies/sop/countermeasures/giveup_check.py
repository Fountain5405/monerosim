"""Independent check: a hand-written deep-reorg strategy (not the MDP).
Mine privately from the fork; publish when a > h >= 11; give up (adopt) when h - a >= D.
Reports 11+ reorgs per main-chain block. gamma plays no role (no ties used)."""
import random, sys
def run(alpha, D, blocks_target, seed=1):
    r = random.Random(seed); a = h = 0; main = 0; deep = 0
    while main < blocks_target:
        if r.random() < alpha: a += 1
        else: h += 1
        if a > h >= 11:
            deep += 1; main += a; a = h = 0   # attacker publishes all a blocks
        elif h - a >= D:
            main += h; a = h = 0
    return deep / main
for alpha in (0.25, 0.30, 0.35, 0.40, 0.45):
    best = max((run(alpha, D, 3_000_000), D) for D in (1, 2, 3, 4, 6, 8, 12))
    print(f"alpha {alpha}: best give-up rule D={best[1]} -> {best[0]:.3e} deep reorgs/block", flush=True)
