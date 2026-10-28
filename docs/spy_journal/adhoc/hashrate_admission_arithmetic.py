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
