#!/usr/bin/env python3
"""Paper arithmetic for hashrate-priced P2P membership and hashrate-weighted
peer selection, against the Monero P2P Observatory's 2026-10-28 counts and
the 10-27 network difficulty (docs/20261028_hashrate_gating_arithmetic.md).
Every unit cost is an assumption stated in ASSUMPTIONS; change them there.
"""
NET_HS = 877_233_282_455 / 120          # network hashrate, H/s (difficulty / 120 s, 2026-10-27)
HONEST_REACH = 1_854                     # fingerprint-aware honest reachable nodes (fp_headline)
FLEET_REACH = 2_645                      # flagged reachable nodes (definitive 1,561 + pattern 1,084)
FLEET_ENTRIES = 17_636 + 2_645           # + the one operator's unreachable peer-list entries
UNREACH_LO, UNREACH_HI = 36_000, 55_000  # organic unreachable nodes, estimator range
ASSUMPTIONS = {
    "core_khs": 1.0,                # RandomX kH/s per modern core
    "rental_eur_per_khs_month": (4.0, 8.0),   # rented 32-core server, 25-35 kH/s, EUR 100-200/month
    "farm_eur_per_khs_month": (1.0, 1.5),     # owned hardware amortised + power, before mining revenue
    "xmr_eur": (150.0, 400.0),      # XMR price range used only for the revenue offset
    "tail_xmr_per_day": 432.0,      # 0.6 XMR per 120 s block
    "ip_eur_per_node_month": (4.0, 6.0),      # a cloud droplet / leased IPv4 per node today
    "attacker_budgets_eur_month": (25_000, 250_000, 2_500_000),
    "honest_drop_fraction": {1: (0.2, 0.4), 3: (0.5, 0.7), 10: (0.8, 0.95), 30: (0.97, 0.995)},
}
rev_lo = ASSUMPTIONS["tail_xmr_per_day"] * 30 / (NET_HS / 1e3) * ASSUMPTIONS["xmr_eur"][0]  # EUR per kH/s-month
rev_hi = ASSUMPTIONS["tail_xmr_per_day"] * 30 / (NET_HS / 1e3) * ASSUMPTIONS["xmr_eur"][1]
print(f"network {NET_HS/1e9:.2f} GH/s; mining revenue {rev_lo:.2f}-{rev_hi:.2f} EUR per kH/s-month")
print(f"today's fleet address bill: reachable {FLEET_REACH*4/1e3:.0f}-{FLEET_REACH*6/1e3:.0f} kEUR/month; "
      f"full footprint {FLEET_ENTRIES*4/1e3:.0f}-{FLEET_ENTRIES*6/1e3:.0f} kEUR/month (one IP per entry)")

print("\n== A. admission price w per node: what the fleet pays (rental), what the honest side needs")
for w in (1, 3, 10, 30):
    for name, n in (("reachable fleet", FLEET_REACH), ("full footprint", FLEET_ENTRIES)):
        hs = n * w * 1e3
        lo, hi = ASSUMPTIONS["rental_eur_per_khs_month"]
        print(f"w={w:>2} kH/s  {name:15s} {hs/1e6:7.1f} MH/s = {100*hs/NET_HS:5.2f}% of network, "
              f"EUR {n*w*lo/1e3:6.0f}-{n*w*hi/1e3:6.0f} k/month; honest reachable total {HONEST_REACH*w/1e3:.1f} MH/s, "
              f"all honest {UNREACH_LO*w/1e3:.0f}-{(UNREACH_HI+HONEST_REACH)*w/1e3:.0f} MH/s "
              f"({100*(UNREACH_HI+HONEST_REACH)*w*1e3/NET_HS:.1f}% of network at the high end)")

print("\n== B. keep-out: the highest price each attacker budget can still pay (w_max, kH/s per node)")
print("budget    fleet            rental   farm(gross)  farm(net of mining at 150-400 EUR/XMR)")
for B in ASSUMPTIONS["attacker_budgets_eur_month"]:
    for name, n in (("reachable fleet", FLEET_REACH), ("full footprint", FLEET_ENTRIES)):
        r = B / (n * sum(ASSUMPTIONS["rental_eur_per_khs_month"]) / 2)
        f = B / (n * sum(ASSUMPTIONS["farm_eur_per_khs_month"]) / 2)
        net = max(0.05, sum(ASSUMPTIONS["farm_eur_per_khs_month"]) / 2 - (rev_lo + rev_hi) / 2)
        fn = B / (n * net)
        print(f"{B/1e3:6.0f}k   {name:15s} {r:7.1f}   {f:9.1f}    {fn:9.1f}")
print("honest nodes dropping out at w (assumed): " + ", ".join(f"{w} kH/s: {a*100:.0f}-{b*100:.0f}%" for w, (a, b) in ASSUMPTIONS["honest_drop_fraction"].items()))

print("\n== C. the chain-share ceiling: price needed to make the reachable fleet hold x% of the network")
for pct in (1, 5, 15, 34):
    w = pct / 100 * NET_HS / FLEET_REACH / 1e3
    print(f"{pct:>2}% of network -> w = {w:8.0f} kH/s per node (~{w/30:.0f} rented servers per node)")

print("\n== D. hashrate-weighted selection: slot share = hashrate share; what a share costs the fleet")
for share in (0.01, 0.05, 0.15, 0.34):
    hs = share * NET_HS
    lo, hi = ASSUMPTIONS["rental_eur_per_khs_month"]; flo, fhi = ASSUMPTIONS["farm_eur_per_khs_month"]
    print(f"share {share:4.0%}: {hs/1e9:5.2f} GH/s = {hs/1e3:,.0f} cores; rental EUR {hs/1e3*lo/1e6:.1f}-{hs/1e3*hi/1e6:.1f} M/month, "
          f"farm gross {hs/1e3*flo/1e6:.2f}-{hs/1e3*fhi/1e6:.2f} M, net of mining {max(0,hs/1e3*(flo-rev_hi))/1e6:.2f}-{(hs/1e3*(fhi-rev_lo))/1e6:.2f} M")
print(f"voucher capacity of a 30% pool at w=1 kH/s: {0.3*NET_HS/1e3:,.0f} memberships")

# ---- E. attested work as a cap, not a gate (section 5 of the note), observatory 10-28 feeds ----
SEED_INBOUND = 38 + 71 + 64          # a seed's inbound peers: reachable + unreachable + anon (timeseries medians)
SEED_IN_FLEET_PCT = 4.2              # fleet share of a seed's inbound connections (seed_fleet_hist medians 3.7-4.6)
FANIN_IPS, FANIN_GROUPS = 47, 31     # fp8 inbound fan-in harvesting sources at the seeds (latest)
POISON_TOTAL = 53_892                # cumulative poison ip:port footprint still in gray lists (poison_history)
PEG_ENTRIES, PEG_IPS = 5_154, 1_548  # one poisoner: entries and IPs (3.33 ports per IP)
LL_ENTRIES = 17_636                  # the surveillance operator's unreachable entries
LAB_SWEEP = 42 * 300 / 300 * 3600    # lab eclipse: 42 spies x 300 reachable nodes per 300 s, handshakes per hour
HONEST_HS_PER_H = 5                  # an honest node's handshakes per hour at steady state (12 at start, churn after)
print("\n== E1. inbound beyond a per-/16 quota pays a workshare of D hashes per handshake")
print(f"fleet inbound at a seed today: {SEED_INBOUND*SEED_IN_FLEET_PCT/100:.0f} of {SEED_INBOUND} connections; fan-in harvesters {FANIN_IPS} IPs in {FANIN_GROUPS} groups")
for D in (1e5, 1e6, 1e7):
    core_s = D / 1e3                                  # 1 kH/s per core
    honest_cores = HONEST_HS_PER_H * core_s / 3600
    sweep_cores = LAB_SWEEP * core_s / 3600
    fan_cores = FANIN_IPS * 10 * core_s / 86400       # ~10 handshakes per harvester per day
    lo, hi = ASSUMPTIONS["rental_eur_per_khs_month"]
    print(f"D={D:.0e}: honest node {honest_cores:5.2f} cores | lab sweep at 300 s {sweep_cores:7.0f} cores = EUR {sweep_cores*lo/1e3:4.1f}-{sweep_cores*hi/1e3:4.1f} k/month "
          f"(60 s sweeps x5) | fan-in harvesters {fan_cores:5.2f} cores; attacker/honest ratio {LAB_SWEEP/HONEST_HS_PER_H:,.0f}x")
print("\n== E2. gray-list entries carry attested work: D_e hashes per ip:port per day; unreachable nodes pay nothing")
for honest_cores in (0.1, 1.0):
    De = honest_cores * 1e3 * 86400                     # hashes per day per entry
    lo, hi = ASSUMPTIONS["rental_eur_per_khs_month"]
    cost = lambda n: (n * honest_cores * lo / 1e3, n * honest_cores * hi / 1e3)   # kEUR/month renting
    print(f"honest reachable node spends {honest_cores} core ({De:.1e} hashes/day): PEG {PEG_ENTRIES:,} entries EUR {cost(PEG_ENTRIES)[0]:.0f}-{cost(PEG_ENTRIES)[1]:.0f} k/month "
          f"(per-IP pricing would cut it to {PEG_IPS:,} entries, {PEG_ENTRIES/PEG_IPS:.1f}x); operator {LL_ENTRIES:,} entries EUR {cost(LL_ENTRIES)[0]:.0f}-{cost(LL_ENTRIES)[1]:.0f} k; "
          f"cumulative footprint {POISON_TOTAL:,} entries EUR {cost(POISON_TOTAL)[0]:.0f}-{cost(POISON_TOTAL)[1]:.0f} k = {100*POISON_TOTAL*honest_cores*1e3/NET_HS:.2f}% of network; "
          f"honest reachable total {HONEST_REACH*honest_cores/1e3:.1f} MH/s; entries per honest reachable node {POISON_TOTAL/HONEST_REACH:.0f}:1")
