#!/usr/bin/env python3
"""Model B's simulate() (scripts/sop_race_model.py), copied line for line with
the same RNG draws, plus instrumentation: shares found vs embedded per side,
and the shape of every reveal (attacker blocks a, honest blocks h, per-block
embedded shares). For comparison with the sim's reveal_shapes.json.

Usage: modelb_shapes.py D YEARS SEED OUT_JSON
"""
import json
import random
import sys

sys.path.insert(0, '/scratch/monerosim_dev/monerosim')
from scripts.sop_race_model import SECONDS_PER_DAY, SimConfig, T_BLOCK_S


def simulate_shapes(cfg: SimConfig):
    rng = random.Random(cfg.seed)
    rate = cfg.w / T_BLOCK_S
    n_objects = int(cfg.days * SECONDS_PER_DAY * rate)
    hon_blocks, att_blocks = [], []
    hon_pending = att_pending = 0
    found = {'att_shares': 0, 'hon_shares': 0, 'att_embedded_final': 0, 'att_embedded_any': 0,
             'hon_embedded_any': 0, 'att_blocks': 0, 'hon_blocks': 0}
    reveals = []
    for _ in range(n_objects):
        is_attacker = rng.random() < cfg.alpha
        is_block = rng.random() < (1.0 / cfg.w)
        if not is_block:
            if is_attacker:
                att_pending += 1
                found['att_shares'] += 1
            else:
                hon_pending += 1
                found['hon_shares'] += 1
            continue
        if is_attacker:
            embed = att_pending if cfg.attacker_embeds else 0
            att_blocks.append(embed)
            found['att_embedded_any'] += embed
            found['att_blocks'] += 1
            att_pending = 0
        else:
            hon_blocks.append(hon_pending)
            found['hon_embedded_any'] += hon_pending
            found['hon_blocks'] += 1
            hon_pending = 0
        a, h = len(att_blocks), len(hon_blocks)
        if (a == 0 and h > 0) or (h - a >= cfg.d):
            hon_blocks.clear()
            att_blocks.clear()
            att_pending = 0
            continue
        if h == 0:
            continue
        att_objects = sum(1 + n for n in att_blocks)
        hon_weight = sum(1 + m for m in hon_blocks)
        if att_objects >= cfg.K_objects and att_objects > hon_weight:
            reveals.append({'a': a, 'h': h, 'att': list(att_blocks), 'hon': list(hon_blocks)})
            found['att_embedded_final'] += sum(att_blocks)
            hon_blocks.clear()
            att_blocks.clear()
            hon_pending = 0
            continue
    return found, reveals


def main():
    d, years, seed, out = int(sys.argv[1]), float(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
    cfg = SimConfig(alpha=0.33, d=d, rule='sop', attacker_embeds=True, days=years * 365.25, seed=seed)
    found, reveals = simulate_shapes(cfg)
    json.dump({'d': d, 'years': years, 'found': found, 'reveals': reveals}, open(out, 'w'))
    print(json.dumps(found), len(reveals))


if __name__ == '__main__':
    main()
