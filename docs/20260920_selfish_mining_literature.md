# Selfish-mining literature review — moneroresearch.info harvest (2026-09-20)

**Why this exists.** Before branching into selfish-mining experiments, we
swept the Monero Research bibliography (moneroresearch.info, WIKINDX, 287
entries) for everything relevant to selfish-mining *strategies*, *defenses*,
and the *research frontier*, downloaded the relevant set, and ingested it.
PDFs live in `docs/literature/` (untracked — see MANIFEST for source URLs);
this note is the durable digest. Selection criterion: anything that defines a
mining-deviation strategy, quantifies one, defends against one, or supplies
Monero network-layer facts a γ/topology experiment needs.

The audience is us, three months from now, designing experiments on the
apparatus in `docs/SELFISH_MINING.md` (phases 1–4 shipped; γ structurally ≈0
measured). Every section ends with what it changes in our experiment design.

## Part A — The Monero case study: Qubic's 2025 campaign

**Lee, S., & Kim, H. (2025). *Inside Qubic's Selfish Mining Campaign on
Monero: Evidence, Tactics, and Limits.* arXiv:2512.01437.**
(`lee_kim_2025_qubic_selfish_mining_monero.pdf`, read in full)

The only direct empirical study of selfish mining on deployed Monero. The
Qubic pool publicly advertised a "51% takeover" (Aug–Oct 2025). Method: a
pruning node capturing orphan blocks + the Qubic pool's `job_notify` API
polled every 5 s + block attribution via a coinbase `extra_nonce` regex
(`([0-9a-f]{4})0{4}([0-9a-f]{8})([0-9a-f]{8})0{10}$`) validated against
ex-post view-key disclosures.

Findings:

- **Never a sustained majority.** Overall share 22.09%; ten identified
  attack periods (P1–P10, detected by Alg. 1: ≥2 orphans/hour for ≥4 h with
  ≤6 h gaps) averaged 28.02%; brief 6-hour spikes near 50% only.
- **Empirical γ ≈ 0 on real Monero.** Weekly tie-break win rates 0.007–0.059.
  This *externally validates* our simulator's structural γ≈0 finding
  (phases 2–4: fan-out, position, relay all failed to lift it).
- **Mostly unprofitable, as γ=0 theory predicts.** At α=0.2802/γ≈0:
  classical Eyal–Sirer revenue 25.53% < honest 28.02%; Qubic's observed
  P1–P10 average revenue 25.29% — on the curve. Period-level: P6/P9 slightly
  beat honest; the authors attribute wins to fine-grained toggling (Qubic
  attacks only when its effective share spikes: race win rates at ties hit
  0.62 vs α=0.34 in P1, 0.35 vs 0.258 in P8).
- **Conservative release strategy.** In P8 (the most intensive period, 886
  runs) Qubic released private chains at **lead 2**, not lead 1 — avoiding
  ties it structurally loses at γ≈0. They formalize this as a modified
  Markov model (release at lead ≥2, extra state-3→0 transition) with closed
  form R_mod(α,γ) = α(α³γ−3α²γ+α²+3αγ−2α−γ)/(α⁴−2α³+α−1); at α=0.28/γ=0 it
  gives 17.82%, below classical. Their run-length vs orphan-count scatters
  sit between the y=x−1 (lead-1 release) and y=x−2 (lead-2) reference lines.
- **"Private loss, public harm."** Even unprofitable, the campaign caused
  orphan storms and multi-block reorgs (baseline Monero forks are almost
  exclusively length-1; under attack, multi-block forks became common) —
  confirmation reliability degraded regardless of attacker profit.
- **Defenses discussed:** (1) chain-selection rule changes — Publish-or-
  Perish (Zhang–Preneel), freshness rules (Heilman's Fresh Bitcoins,
  ZeroBlock), StrongChain — actively debated in MRL issues after the
  campaign (issue #144); rejected short-term for relying on propagation-bound
  assumptions. (2) **Detective mining** (MRL issue #140; Lee & Kim, ICT
  Express 2023): because the attacker is a *public pool*, its job API leaks
  the private chain's prev-hash; rational miners can mine on the attacker's
  private tip and out-earn both honest miners and the attacker. Costs: DoS
  (pool may refuse release) and it accelerates honest miners' losses.

**For our experiments.** (a) The lead-2 conservative strategy is a ~20-line
`SelfishStrategy` variant directly matching observed attacker behavior —
call it `qubic_lead2` or a `release_lead` attribute; theory curve exists
(R_mod) to validate against. (b) Fine-grained on/off toggling keyed on
effective hashrate is a second attribute (`toggle_threshold`). (c) Their
damage metrics (orphan rate/hour, reorg-depth distribution, run-length ×
orphan scatter) should be added to `selfish_mining_analysis.py` so we
measure externality, not just revenue. (d) Their Alg. 1 gives us a
detection-experiment detector to run against our own runs.

## Part B — Strategy space beyond Eyal–Sirer

**Hou et al. (2021). *SquirRL: Automating Attack Analysis on Blockchain
Incentive Mechanisms with Deep RL.* NDSS 2021.**
Actions {adopt, override, match, wait} over state (fork ∈ {irrelevant,
relevant, active}, private len, public len, block-limit B) — Sapirshtein's
optimal-selfish-mining action set learned by DRL. Recovers OSM within 1%
for α>0.25 (γ=0.5); **beats OSM when hashrate is stochastic** (real 2019
data, E[α]=0.4: 0.585 vs OSM 0.566 vs SM1 0.540 vs honest 0.398) by waiting
out low-α stretches; OSM is *not* a Nash equilibrium vs a strategic
opponent; with 3 symmetric strategic agents, DRL collapses to honest.
*For us:* the (α, γ=0, relative-revenue) grid with honest/ES/OSM baselines
is the canonical experiment grammar; the stochastic-α result matches
Qubic's toggling behavior and is directly simulable (our hashrates are
declarative).

**Carlsten et al. (2016). *On the Instability of Bitcoin Without the Block
Reward.* CCS 2016.** Fee-regime mining games: undercutting spirals (no
clean equilibrium; Θ(√n) backlog), and **Selfish-Mine(β)** — publish
immediately any block worth ≥ β fees, withhold below — which is profitable
for *arbitrarily small α* and immediately (no difficulty-readjustment
grace), e.g. +13.6% over vanilla SM at α=1/3, γ=0 with optimal β. Also:
PettyCompliant tie-breaking (build on the fork leaving more fees)
effectively raises γ for selfish miners. *For us:* Monero's 0.6 XMR tail
emission keeps the fee share tiny today (β-gating should mostly deactivate
— itself a measurable, Monero-specific result), but the fee-gated variant
is cheap to add if we ever vary the reward mix.

**Gong et al. (2022). *Towards Overcoming the Undercutting Problem.* FC
2022.** Re-does Carlsten with block-size limits and real mempools. Monero
calibration: blocks 2,100,000–2,191,000 (May–Sep 2020, 1.48 M txs): a 35%
Monero pool gains +8.2 pp by undercutting — *especially efficient in
Monero because of its small mempools*. Defense: deliberate underfilling
("undercutting avoidance", ~30-line miner change) restores fair share when
the #2 pool matches. *For us:* the only Monero-fee-calibrated attack
numbers in the set; an undercutter agent is a different axis than
lead-stubbornness and composes with selfish mining (noting neither paper
composed them).

**Kawaguchi & Noda (2021). *Security-Cost Efficiency of Competing PoW
Cryptocurrencies.* SSRN 3974376.** Structural mining-market economics:
hash-supply elasticities (BTC 0.63 vs BCH 5.39), DAA stability thresholds
(original BTC DAA stable iff elasticity <1; CW-144 iff <144), and **SpEC =
5th-percentile hashrate / mean hashrate** as the security metric —
attackers strike at minima, so security is the minimum. *For us:* SpEC is a
one-line addition to our per-block logs and a defense-relevant KPI beyond
revenue share; Monero retargets per-block (LWMA), so DAA-oscillation
failure modes are largely absent — but SM-induced difficulty dips are
exactly the SpEC dips worth measuring.

**Li, Yang & Tessone (2020). *PoW cryptocurrency mining: a statistical
approach to fairness.* IEEE/CIC ICCC-W.** Detection: **Miner Sequence
Bootstrapping** — condition on each miner's realized block count, shuffle
the block-winner sequence 1,000×, z-score each miner's consecutive-block
wins; MSB > 2 flags selfish mining (withholding+release inflates
consecutive wins without inflating total share). Flagged pools exist on
BTC/LTC/ETH/BCH, including small ones. *For us:* MSB is trivially computable
from our ground-truth block logs and turns every run into a detectability
measurement — how fast would a detector catch each strategy at each α, and
what's the honest-run false-positive rate (their admitted confound:
propagation latency alone inflates consecutive wins — we control latency,
so we can decompose it).

**Miller et al. (2015). *Nonoutsourceable Scratch-Off Puzzles.* CCS 2015.**
Puzzle redesign to make pool outsourcing unenforceable (workers can steal
winning tickets). Not simulable in monerosim; justifies the threat model —
pool-formable hashrate is what makes α≈0.3+ plausible (Monero's top pool
~35% per Gong's data).

## Part C — Foundations and quantitative attack models

**Garay, Kiayias & Leonardos (2015). *The Bitcoin Backbone Protocol.*
Eurocrypt 2015.** The formal backbone: common prefix, chain quality, chain
growth under (α, γ, f) — their γ is "uniquely successful round" probability,
not Eyal–Sirer tie-breaking. Chain quality provably *not* ideal: adversary
can exceed its hashrate share; the bound is tight under worst-case
propagation (effectively Eyal–Sirer γ=1) — an upper envelope, not a
prediction for our γ≈0 network. Flags fast chains (f large) as precarious.
*For us:* chain-quality window semantics for our share metrics; keep f
(propagation/block-interval) explicit in experiment configs.

**Gervais et al. (2016). *On the Security and Performance of PoW
Blockchains.* CCS 2016.** The quantitative bridge: a network simulator
yields the **stale-block rate r_s**, an MDP (Sapirshtein actions) consumes
r_s and computes optimal-attack revenue/double-spend values. Bitcoin r_s
0.41% vs Ethereum 6.8% (uncles); Ethereum needs ≥37 confirmations to match
Bitcoin's 6 at α=0.3. Selfish-mining revenue rises sharply with r_s;
recommended levers are network-layer (unsolicited push, relay, sendheaders)
— *no* DAA formula here. *For us:* r_s is the single scalar connecting our
Shadow network runs to attack analysis — log stale rate per run and we can
sit our results on their (α, γ, r_s, k) grid; their γ semantics ("fraction
of honest miners that adopt the attacker's tie block") matches exactly what
our realized-γ estimator measures at ≈0.

**Jiang & Zhang (2024). *Profitability of Time-Restricted Double-Spending
with Multiple Attack Types.* IEEE TIFS.** Closed-form E(profit) for
double-spending with give-up depth L, combined with eclipse (ω) and
propagation delay (r_s). Selfish mining *not* included (secret-branch race
only). Notable: max profit at α=0.25 with small L (short repeated races
beat long ones for weak attackers); once α>0.35, *more* confirmations
increase attacker profit (branch mining pays while the merchant waits).
*For us:* the (α, ω, r_s, Z, L) grid and the E(R) accounting
(reward×share − cost×blocks + v×P_success) is a drop-in profit metric for
our monitor output; the give-up depth L is a natural strategy knob shared
with our `trail_depth`.

**Budish (2025). *Trust at Scale: The Economic Limits of Cryptocurrencies
and Blockchains.* QJE.** Majority-attack economics: honest security is a
*flow* (p_block must exceed V_attack/(A·t(A)) at all times); attackers pay
rental flows, not capital stocks, unless capital is specialized and
destroyed by the attack (ASICs ⇒ ~2500× cheaper security; explains why
BTC/ETH haven't been attacked). Zero-net-cost theorem: with no DAA response
and no price collapse, block rewards exactly reimburse attack cost. Monero
angle: CPU-mineable RandomX has *no* specialized capital — the rental-flow
regime, the economically fragile one; tail emission keeps p_block constant
(no halving cliffs). *For us:* the DAA-response term (D′ > D\* cuts attacker
reimbursement) makes per-block LWMA a first-class economic channel —
Monero retargets every block, so withholding's difficulty feedback is fast
and measurable in our runs (see NATIVE_MINING.md §7 for the window
formula our DAA analysis already implements).

## Part D — Monero network layer (γ levers, topology realism, detection)

**Shi et al. (2025). *Eclipse Attacks on Monero's P2P Network.* NDSS
2025.** monerod v0.18.3.1: graylist stuffing (5,000 trash records via timed
sync), whitelist stuffing (cycle >1,000 IPs for fresh `last_seen`), and a
connection-reset primitive (double-spend anti-DoS disconnects; Dandelion++
stem/fluff race, 82% of fluff spans exceed the 2.4 s stem delay). Full
eclipse in avg 156 s, ≈$0.01/round. Defaults: 12 out-conns, unlimited
in-conns, whitelist 1,000/graylist 5,000, out-peer selection = top-20
whitelist by freshest `last_seen` with /16 diversity, 1 conn/IP, anchors
cleared on out-conn drop. Fixed in v0.18.3.2 (no disconnect on double-spend
conflict). *For us:* we already reproduce this attack; the peer-selection
semantics are the spec for any peer-pinning knob (SELFISH_MINING.md §9.4's
named next lever) — and eclipse of an honest subset is lever (a) for
raising effective γ (their §"eclipse+stubborn strictly increases revenue",
per Franzoni's synthesis of Nayak).

**Franzoni & Daza (2022). *SoK: Network-Level Attacks on the Bitcoin P2P
Network.* IEEE Access.** The taxonomy paper. Selfish-mining algebra in one
place: profitable at α>0.009 when γ=0.99; α≥1/3 at γ=0; **delaying 2
consecutive blocks to 50% of the network lowers the bound to α≥0.26**;
<34% "network superiority" can emulate 50%. Eclipse+stubborn strictly
increases revenue (Nayak). *For us:* the two γ-lifting levers consistent
with our phases 2–4 negative results are exactly theirs: (a) eclipse a
victim set, (b) delay honest blocks (TendrilStaller-style, 50–85% feasible
at RTT<80 ms) — both are *network-layer* additions to the attacker, not
consensus changes; both are buildable in monerosim (we have the eclipse
harness; delay = bridge/host shaping).

**Gao et al. (2025) ×2 (arXiv:2504.15986, 2504.17809). Monero P2P topology.**
Inferred graph (4,837 nodes): 14 "supernodes" touch 82.1% of the network;
degree assortativity −0.28 (disassortative); periphery sits at exactly
out-degree 8; LCC collapses at 9–12% targeted removal. Note the literature
disagrees on default out-peers (Shi/Kopyciok: 12; Gao: 8) — pin
`--out-peers` explicitly in configs. *For us:* a hub-and-spoke generator
recipe for attacker-relevant topologies — bridges placed as supernodes are
*empirically grounded* adversarial placements; percolation thresholds give
partition-experiment targets.

**Kopyciok, Schmid & Victor (2025). *Friend or Foe? Identifying Anomalous
Peers in Monero's P2P Network.* arXiv:2509.10214.** 240 h of PCAPs from 5
vantages: 14.74% of reachable peers non-standard; one entity runs ≥1,582
nodes across 7 /24s (so multi-bridge attacker infrastructures exist in the
wild); community ban-list + 32 out-peers cuts adversarial outbound
saturation 20.4%→7.1%. Key negative result: monerod's offense tracker only
penalizes *invalid* data — a protocol-compliant withholding attacker is
invisible to it. *For us:* defense-knob realism (ban lists, out-peer
sizing) and the confirmation that no network-layer detector flags
withholding — the detection gap our MSB/orphan-rate metrics can fill.

**Wijaya et al. (2019). *On the Unforkability of Monero.* AsiaCCS 2019.**
Cross-fork key-image reuse → traceability. Not mining-strategy relevant;
kept for the fork-timeline record only.

**Purkovic et al. (2021). *Empirical Analysis of Silent Mining Operation in
the Monero System.* SIC 30(4).** "Silent mining" = covert ASIC deployment
between PoW forks (Bitmain X3 era), regression-detected; economically
punished by forks (cost-benefit ≈1:2). Not selfish mining despite the name;
hasbroute-composition shock calibration only.

## Part E — Synthesis: what this changes in monerosim

1. **γ≈0 is not a simulator artifact — it's Monero's measured reality.**
   Lee & Kim's empirical γ (0.007–0.059 weekly) matches our structural
   finding (phases 2–4) and Franzoni's algebra. The scientific move is not
   to force γ>0 with consensus changes (deliberately rejected, §9.4) but to
   add the two network-layer levers the literature says are the real ones:
   **eclipse of an honest subset** (Shi; we already own the harness) and
   **honest-block delay** (TendrilStaller-class, α threshold 1/3 → ~0.26).
2. **Strategy backlog, literature-grounded, in build-order of cheapness:**
   - `release_lead: 2` (Qubic's observed conservative policy; R_mod
     closed-form exists to validate against) — ~20 lines in
     `agents/selfish_strategy.py`.
   - Fine-grained toggling on effective hashrate (Qubic; SquirRL's
     stochastic-α optimality) — a `toggle_alpha` attribute.
   - Fee-gated Selfish-Mine(β) (Carlsten) — meaningful only if we vary
     reward mix; with tail emission expect deactivation (a result).
   - Optimal-SM actions (adopt/override/match) — the Sapirshtein/SquirRL
     action set as a `generic` strategy engine (already noted as the
     unbuilt `generic(lead_k, publish_n, trigger)` in §8.7).
3. **Metrics to add to `selfish_mining_analysis.py`:** orphan rate/hour
   time series + Lee & Kim Alg. 1 period detection; reorg-depth
   distribution; run-length × orphan scatter; MSB z-scores (Li 2020); SpEC
   (Kawaguchi); stale rate r_s (Gervais) — each is cheap and each converts
   existing runs into detectability/externality measurements.
4. **Defense experiments the literature motivates:** detective mining
   (MRL #140; needs a leaky-pool model — our bridge can play the public
   pool), Publish-or-Perish/freshness rules (consensus change: out of
   scope per our no-consensus-patch stance, but a sim-only flag could
   measure what it would buy), undercutting avoidance (Gong's underfill
   patch), network hardening (ban lists, out-peer sizing, Shi's whitelist
   rules — all pure config).
5. **Economics framing:** report every attack run with a Budish-style
   flow-cost ledger and note the DAA-feedback channel (per-block LWMA cuts
   attacker reimbursement during withholding — a Monero-specific effect
   Bitcoin's 2016-block DAA wouldn't show, measurable via our existing
   `native_daa_analysis.py` machinery).

## MANIFEST

Downloaded 2026-09-20 from moneroresearch.info (WIKINDX resource ids in
parentheses); local copies in `docs/literature/` (untracked; URLs here are
the durable reference).

| File | Paper | Resource id |
|---|---|---|
| lee_kim_2025_qubic_selfish_mining_monero.pdf | Lee & Kim 2025, arXiv:2512.01437 | 293 |
| hou_2021_squirrl_automated_attack_analysis.pdf | Hou et al., NDSS 2021 | 121 |
| gervais_2016_security_perf_pow_blockchains.pdf | Gervais et al., CCS 2016 | 67 |
| garay_2015_bitcoin_backbone_protocol.pdf | Garay et al., Eurocrypt 2015 | 71 |
| carlsten_2016_instability_without_block_reward.pdf | Carlsten et al., CCS 2016 | 77 |
| gong_2022_overcoming_undercutting.pdf | Gong et al., FC 2022 | 87 |
| kawaguchi_2021_competing_pow_cryptocurrencies.pdf | Kawaguchi & Noda 2021, SSRN 3974376 | 23 |
| budish_2025_trust_at_scale_qje.pdf (+2 appendices) | Budish, QJE 2025 | 101 |
| jiang_2024_time_restricted_double_spend_multi_attacks.pdf | Jiang & Zhang, IEEE TIFS 2024 | 239 |
| miller_2015_nonoutsourceable_scratchoff_puzzles.pdf | Miller et al., CCS 2015 | 24 |
| shi_2025_eclipse_attacks_monero_p2p_ndss.pdf | Shi et al., NDSS 2025 | 248 |
| franzoni_2022_sok_network_attacks_bitcoin_p2p.pdf | Franzoni & Daza, IEEE Access 2022 | 232 |
| wijaya_2019_unforkability_of_monero.pdf | Wijaya et al., AsiaCCS 2019 | 45 |
| gao_2025_monero_p2p_landscape.pdf | Gao et al., arXiv:2504.15986 | 267 |
| gao_2025_monero_p2p_topology_analysis.pdf | Gao et al., arXiv:2504.17809 | 278 |
| kopyciok_2025_anomalous_peers_monero_p2p.pdf | Kopyciok et al., arXiv:2509.10214 | 280 |
| purkovic_2021_silent_mining_monero.pdf | Purkovic et al., SIC 2021 | 161 |
| li_2020_pow_mining_statistical_fairness.pdf | Li et al., IEEE/CIC ICCC-W 2020 | 59 |

All retrievable from moneroresearch.info resource pages
(`index.php?action=resource_RESOURCEVIEW_CORE&id=<id>`) or their arXiv/
DOI homes. Deliberately *not* downloaded (adjacent, on-catalog): pure
double-spend race papers (Rosenfeld 2014 #191; Grunspan & Perez-Marco 2018
#192, 2022 #238; Zheng et al. 2021 #240), Monero privacy papers, and
energy/economics studies — none change experiment design above.
