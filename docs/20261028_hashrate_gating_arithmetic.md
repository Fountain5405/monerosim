# Can hashrate price the spy fleet out of Monero's P2P layer? Paper arithmetic

*2026-10-28. A note from the spy-relay lab, written against the Monero P2P Observatory's counts of the same day and the network difficulty of 2026-10-27. Nothing here is simulated; the unit costs are stated assumptions and the script that produced every number is `docs/spy_journal/adhoc/hashrate_admission_arithmetic.py`.*

## The idea being priced

"P2P based on weight linked to hashrate: miners have weight, non-miners have to rely on some miners or be a miner." Two readings, both priced here:

1. **Admission.** A node needs attested hashrate (its own workshares, or a miner's voucher) to hold a P2P connection at all. The question is whether a membership priced in hashrate can keep the surveillance fleet out while home nodes stay in.
2. **Weighted selection.** Peers are chosen in proportion to attested hashrate, so a node's share of everyone's outbound slots equals its hashrate share.

The context: the fleet's advantage today is bought with IP addresses. In the lab, untrimmed peer lists hand it 2.2x its address share of outbound slots and rotating front ports eclipse every untrimmed node; a white-list cap of 70 removes both at zero honest cost. On the three mainnet seeds the observatory watches, the flagged fleet's share of outbound connections (14 to 16 %) already sits at or below its white-list share (17 to 23 %), which is where a trimmed list lands.

## Inputs

| Quantity | Value | Source |
|---|---|---|
| Network hashrate | 7.31 GH/s (difficulty 877 G / 120 s) | a mainnet node, 2026-10-27 |
| Honest reachable nodes | 1,854 | observatory `fp_headline`, 2026-10-28 |
| Flagged reachable nodes | 2,645 (1,561 definitive fingerprint + 1,084 pattern) | observatory `fleet_split` |
| One operator's unreachable peer-list entries | 17,636 | observatory `surveillance` table |
| Organic unreachable nodes | 36,000 to 55,000 by estimator (5,335 observed dialing the seeds) | observatory `estimates_history` |
| RandomX per modern core | ~1 kH/s | assumption |
| Rented 32-core server (25 to 35 kH/s) | EUR 100 to 200 per month, i.e. EUR 4 to 8 per kH/s per month | assumption |
| Owned mining hardware, amortised, with power | EUR 1 to 1.5 per kH/s per month before mining revenue | assumption |
| Mining revenue (tail emission 432 XMR/day, XMR at EUR 150 to 400) | EUR 0.27 to 0.71 per kH/s per month | derived |
| A cloud node or leased IPv4 today | EUR 4 to 6 per node per month | assumption |

Two fleet sizes are priced throughout: the **reachable fleet** (2,645 fingerprinted nodes) and the **full footprint** (those plus the 17,636 unreachable entries, 20,281; if the entries are multi-port poisoning at ~2.3 ports per IP the machine count is nearer half of that).

Today's address bill for the fleet, at one IP per entry: EUR 11 to 16 k per month for the reachable fleet, EUR 81 to 122 k per month for the full footprint. That is the bar any new price has to clear by a wide margin.

## 1. Admission: what a membership price costs each side

Let *w* be the hashrate a node must sustain to hold connections. Four prices: one core (1 kH/s), three cores, a pegged desktop (10 kH/s), a small server (30 kH/s).

| *w* per node | Reachable fleet (2,645) | Full footprint (20,281) | All honest nodes (38k to 57k) |
|---|---|---|---|
| 1 kH/s | 2.6 MH/s, 0.04 % of network, **EUR 11 to 21 k/month** | 20 MH/s, 0.28 %, **EUR 81 to 162 k/month** | 36 to 57 MH/s, 0.5 to 0.8 % of network |
| 3 kH/s | 7.9 MH/s, EUR 32 to 63 k | 61 MH/s, 0.83 %, EUR 243 to 487 k | 108 to 171 MH/s, 1.5 to 2.3 % |
| 10 kH/s | 26 MH/s, 0.36 %, EUR 106 to 212 k | 203 MH/s, 2.8 %, EUR 0.8 to 1.6 M | 360 to 569 MH/s, 5 to 8 % |
| 30 kH/s | 79 MH/s, 1.1 %, EUR 317 to 635 k | 608 MH/s, 8.3 %, EUR 2.4 to 4.9 M | 1.1 to 1.7 GH/s, 15 to 23 % |

Reading: the one-core price roughly doubles the reachable fleet's bill and raises the full footprint's by 2x; the desktop price raises them by 10x. Mining revenue earns back 5 to 15 % of rental cost, so it does not change the picture for a renter; it matters only for an attacker who already owns a farm on cheap power (next section).

What the same prices cost a home node:

| *w* | The honest node pays | Who drops out (assumed) |
|---|---|---|
| 1 kH/s | one core busy around the clock, ~10 W | 20 to 40 %: laptops, NAS boxes, phones, nodes on shared hosts |
| 3 kH/s | a quarter of a desktop | 50 to 70 % |
| 10 kH/s | a desktop pegged, 100 to 150 W, EUR 10 to 20 of power and no use of the machine | 80 to 95 %, i.e. nearly the whole unreachable majority |
| 30 kH/s | a dedicated server per node | 97 % and more |

## 2. Admission: can any price keep the fleet out?

The keep-out condition is that the fleet's budget cannot cover *w* for its node count while the honest side can still pay *w*. The highest price each budget can pay, *w*max = budget / (nodes x cost per kH/s):

| Attacker budget per month | Fleet | *w*max, renting | *w*max, owned farm (gross) | *w*max, owned farm net of mining revenue |
|---|---|---|---|---|
| EUR 25 k (a hobbyist or a small vendor) | reachable fleet | 1.6 kH/s | 7.6 | 12 |
| | full footprint | 0.2 | 1.0 | 1.6 |
| EUR 250 k (a surveillance vendor) | reachable fleet | 16 kH/s | 76 | 124 |
| | full footprint | 2.1 | 9.9 | 16 |
| EUR 2.5 M (a state customer) | reachable fleet | 158 kH/s | 756 | 1,240 |
| | full footprint | 21 | 99 | 162 |

Set against the honest drop-out column of section 1:

- **Against a EUR 25 k budget, admission works.** A price of 2 to 5 kH/s per node keeps the reachable fleet out of a rental budget at the cost of half the home nodes. The fleet's observed address spend today (EUR 15 to 35 k per month by the estimate above) says the current operator is at least at this line, and the entity behind 17,636 entries is a company, not a hobbyist.
- **Against a EUR 250 k budget, no price works.** The attacker renting can pay 16 kH/s per reachable node, which is above the desktop price at which 80 to 95 % of honest nodes have already left. With an owned farm the attacker pays 76 to 124 kH/s per node: a server per spy, and no home node at all.
- **The full footprint is the one case that bites**, because entries are cheap today and each would need its own work. A EUR 250 k renter can only afford 2 kH/s per entry, so the 17,636 unreachable entries would have to shrink or consolidate onto fewer machines. That is a defense against peer-list poisoning more than against the reachable fleet, and the fleet's observing power sits in the reachable 2,645.

Why the count does not help: the flagged reachable fleet already outnumbers honest reachable nodes 1.4 to 1. Any price the honest reachable side can pay in aggregate (1,854 x *w*), the fleet matches by spending what every honest reachable node spends together. At the one-core price that is 1.9 MH/s, about 60 rented servers.

**The chain-share ceiling.** Membership priced in chain hashrate can never make the fleet's weight chain-relevant while home nodes can pay it. For the reachable fleet to have to hold even 1 % of the network, *w* must be 28 kH/s per node (a rented server each); 5 % needs 138 kH/s per node; the lab's untrimmed 34 % share needs 940 kH/s, thirty-one servers per spy node. Meanwhile the entire honest population at the one-core price sums to 0.5 to 0.8 % of the network, less than the smallest pool. The honest side's collective weight is noise next to the pools, which is the problem with vouchers.

**Vouchers zero the price.** If non-miners get membership by a miner's voucher, the marginal cost of a voucher is nothing: a pool with 30 % of the network holds 2.2 GH/s of weight and can vouch for 2.2 million memberships at 1 kH/s each without adding a hash. The price of a membership becomes what a pool chooses to charge, with a floor of zero, and the scheme's strength becomes the honesty of the largest pools and the safety of their signing keys. A fleet buys vouchers, or runs the small miner that issues its own.

**Costs on the honest side that no price removes:** miners become gatekeepers of who may join the network, which is a censorship lever larger than the spy problem; a new node needs a connection to mine and a miner to connect, so the network becomes invitation-only in practice; and the sponsor relationship is itself a record of who runs a node, kept by the sponsor.

## 3. Weighted selection: pricing the share instead of the node

If outbound slots are allocated in proportion to attested hashrate, the fleet's slot share equals its hashrate share, and the price is proportional to the share taken rather than to the node count. This is the one place hashrate pricing is strong:

| Fleet slot share | Hashrate needed | Cores | Renting, per month | Owned farm, gross | Owned farm, net of mining |
|---|---|---|---|---|---|
| 1 % | 73 MH/s | 73,000 | EUR 0.3 to 0.6 M | EUR 0.07 to 0.11 M | EUR 0.02 to 0.09 M |
| 5 % | 366 MH/s | 366,000 | EUR 1.5 to 2.9 M | EUR 0.37 to 0.55 M | EUR 0.11 to 0.45 M |
| 15 % (today's share on the seeds) | 1.10 GH/s | 1.1 M | EUR 4.4 to 8.8 M | EUR 1.1 to 1.6 M | EUR 0.3 to 1.4 M |
| 34 % (the lab's untrimmed share) | 2.49 GH/s | 2.5 M | EUR 9.9 to 19.9 M | EUR 2.5 to 3.7 M | EUR 0.7 to 3.1 M |

To keep the 15 % of outbound slots it holds on the seeds today, a renting fleet would pay EUR 4 to 9 million a month against EUR 15 to 35 k now. An attacker who already mines at scale pays far less net, because the hashrate earns, but even then recovering today's share means owning a top-five pool's worth of the network.

What the same rule does to honest nodes:

- **First hops concentrate at the pools.** Mining is concentrated; if the top pools hold around two thirds of the hashrate, two thirds of every node's outbound slots, and therefore of first stem hops, land on pool-operated nodes. Dandelion++ privacy needs the first hop to be diffuse and unpredictable. A few high-weight hubs seeing everyone's first hops is the spy position, handed to whoever runs the pools or compromises them.
- **Weight is lendable.** A pool can attest a thousand front nodes with one hashrate; nothing binds an attestation to one IP without network-wide state. The voucher market of section 2 returns, now selling slot share.
- **Zero-weight nodes become unchoosable.** The graph goes star-shaped around weighted hubs, with load and eclipse risk concentrating there; the observatory's bandwidth panels already show how few peers eat a seed's upload.

A minority-rail variant keeps the strength and drops the hazard: reserve a small fixed number of the twelve outbound slots for workshare-attested peers of distinct keys, never the stem edges, so that eclipsing a node needs hashrate as well as addresses, while selection stays diffuse.

## 4. Against the cheap baseline

The white-list cap at 70 removes the 2.2x amplification (lab: 0.1616 against 0.3369, two seeds) and defeats the rotating-front-port eclipse (0.0248 against 0.9083, one user of forty, replicated) at zero honest cost. After the cap, the fleet's outbound share equals its address share, roughly 15 % on the mainnet seeds, and the only lever left to it is buying addresses.

- Admission pricing lowers that 15 % only by the fraction of the fleet it excludes. Section 2 says that fraction is near zero for a funded fleet at any price home nodes can pay.
- Weighted selection would lower it to the fleet's hashrate share, which is the real win, at the cost of routing most first hops through the pools.
- Neither raises the price of an address, and the address is what the fleet is made of.

## 5. What could still be worth building from the idea

- Attested work as a cap, not a gate: inbound acceptance beyond a per-/16 quota requires workshares (prices the inbound fan-in harvesting the observatory tracks); gray-list promotion requires attested work (prices peer-list poisoning, the one case where section 2's full-footprint row bites). Joining stays free; miners stay out of the gatekeeper seat.
- A reserved minority of outbound slots for attested peers of distinct keys, as an eclipse rail.
- Both can be simulated in the lab's harness; membership itself cannot be, since once a node is in it behaves like today's fleet, which is what the lab has already measured.

## Uncertainties that move the numbers

XMR price and rental rates (each by 2x either way); how many machines sit behind the 17,636 entries; whether the 2,645 flagged reachable nodes are one budget or several; the honest drop-out fractions, which are judgment rather than survey; and the observatory's fleet oracle, a withheld fingerprint that flags 59 % of reachable nodes and so may be broader than a single operator.
