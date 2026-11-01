# Share or Perish (selfish mining mitigation)

https://github.com/monero-project/research-lab/issues/146 — tevador, 2025-09-25T06:22:27Z

## Share or Perish

The previously proposed Publish or Perish [1] (PoP) has some shortcomings. With the default parameter `k=3`, it cannot prevent deeper reorgs, like those that happened recently. Increasing `k` comes with a risk of nontrivial chain splits. Even with `k=3`, partition recovery with PoP might take over 20 blocks in some cases [2].

This is a new proposal "Share or Perish" (SoP), partly based on PoP and combined with the idea of workshares [3], which I previously dismissed due to their high cost, but this proposal presents parameters with acceptable costs. Similarly to PoP, SoP is a soft-forking proposal that only introduces a new fork choice rule but doesn't affect rewards or other consensus rules. SoP should be much more resilient to long reorgs and has better partition recovery time than PoP.

### Parameters

SoP defines three security parameters `w` (workshare ratio), `d` (network propagation delay, same as PoP) and `k` (partition recovery, same as PoP).  

| Parameter | Description | Recommended value |
|-----------|-------------|-------------------|
| `w`       | workshare ratio | 16 |
| `d`       | network propagation delay | 5 |
| `k`       | partition recovery | 3 |

(Table 1)

### Work objects

Let's recall Monero's PoW header format:

| Field | Type | Size (B) |
|-------|------|------|
| version_major | varint | 1 |
| version_minor | varint | 1 |
| timestamp | varint | 5 |
| prev_id | hash | 32 |
| nonce | int | 4 |
| tx_tree_hash | hash | 32 |
| num_transactions | varint | 1-2 |
| **Total**|| 76-77 |

(Table 2)

Miners take this PoW header (also called the hashing blob) and search for a nonce value that meets the current block difficulty.

Normally, only the block header itself is used as a proof-of-work. SoP introduces an additional work object called "workshare", which is defined as a distinct PoW header that meets at least `1/w` of the current block difficulty and has the same `prev_id` value as the containing block.

#### Extra block data

Valid workshares are included in blocks. On average, a block will contain `w-1` workshares. A workshare can be serialized with only 4 fields from Table 2: `timestamp`, `nonce`, `tx_tree_hash` and `num_transactions`. The remaining values are implicit.

There are two ways how workshares can be included in a block:

1) They are placed in tx_extra of the miner transaction. This is the simplest backwards-compatible solution with guaranteed data availability. However, this introduces extra non-prunable data into the blockchain (about 170 MB per year with the recommended parameters).
2) Each block contains a commitment to the set of workshares, but the data itself is sent in a separate P2P message. This would be more complex to implement, but allows for workshares to be pruned when they are not needed anymore for verification.

#### Uniqueness of workshares

SoP additionally requires miners to set the `version_minor` block header field to be equal to the number of workshares included in the block. Workshares included in the block must have sequential values of `version_minor` starting from `0` and ending with `block.version_minor-1`.

This rule serializes the mining of workshares and its purpose is to make it harder for malicious miners to withhold their own workshares, while including the workshares published by other miners.

### Chain weight

Let `diff(x)` be a function that returns the difficulty of the block at height `x`. SoP uses a modified weight for the last `10*w` blocks of the blockchain. Let `t` be the chain tip height. The weight of a block at height `h` is equal to the sum of the weights of its work objects according to the following table:

| Block height   | Block header | Workshare |
|----------------|--------------|-------------|
| `h > t - 10*w` | <code>l<sub>b</sub>\*diff(h)/w</code>| <code>l<sub>b</sub>\*l<sub>w</sub>\*diff(h)/w</code> |
| `h <= t - 10*w`| `diff(h)`    | `0`        |

(Table 3)

The lateness factors <code>l<sub>b</sub></code> (for blocks) and <code>l<sub>w</sub></code> (for workshares), which can have a value of `0` or `1`, are described in the next section.

For block heights `t - 10*w` and older, workshares have no impact on the block weight, so they can be ignored and don't need to be verified. This means that the impact of SoP on new nodes downloading the blockchain is negligible.

#### Lateness factors

Similar to PoP, SoP also reduces the weight of "late" blocks to zero. This is accomplished with a block lateness factor <code>l<sub>b</sub></code>.

There is a separate factor <code>l<sub>w</sub></code> which causes the weights of withheld workshares to be zero even if the containing block is not late.

Let <code>h<sub>0</sub></code> be the block height when the node came online.

Let there be an alt-chain that forks off the main chain at height <code>h<sub>f</sub></code> and contains <code>n<sub>f</sub></code> work objects that are not contained in the main chain.

Let `block_seen` be the unix timestamp when the evaluated block of height `h` was first seen by the node. Let `share_seen` be the unix timestamp when the evaluated workshare was first seen by the node.

Let `main_seen` be the unix timestamp when the main chain block of height `h` was first seen by the node. If the main chain block of height `h` doesn't exist (i.e. the alt-chain is ahead), we set `main_seen = block_seen`.

The lateness factors are then defined as follows:

| Condition | <code>l<sub>b</sub></code> |
|------------------------|----------------------------------------|
| if <code>h<sub>0</sub> < h<sub>f</sub> && n<sub>f</sub> < k*w && block_seen - main_seen > d</code>                | `0` |
| else               | `1` |

(Table 4)

| Condition | <code>l<sub>w</sub></code> |
|------------------------|----------------------------------------|
| if <code>h<sub>0</sub> < h<sub>f</sub> && n<sub>f</sub> < k*w && main_seen - share_seen <= d</code>                | `0` |
| else               | `1` |

(Table 5)

The lateness factors can be distinct from `1` only if the node was online before the fork height and the two chains differ by fewer than `k*w` work objects.

By Table 4, a block is considered to be late if it's seen more than `d` seconds after the main chain block of the same height.

By Table 5, a share is considered to be late if it's not seen more than `d` seconds before the main chain block of the same height.

Note that the lateness factors are subjective; different nodes can calculate different values of <code>l<sub>b</sub></code> and <code>l<sub>w</sub></code> for the same block, which can lead to different chain weights.

#### Tie breaking

If a node sees two chains of the exact same weight, it makes a random selection.

### Security

We will evaluate the security of SoP with the recommended parameters of `w = 16`, `d = 5` and `k = 3` against an attacker with `α = 0.33`, i.e. a minority hashrate attacker.

#### Short forks

A selfish miner can decide to withhold blocks or both blocks and workshares.

If only blocks are withheld (i.e. the attacker still publishes mined workshares for the public chain tip), SoP behaves similarly to PoP for block races of length 1. Once the attacker starts mining on top of a secret block, his workshares can no longer be relayed and will have <code>l<sub>w</sub> = 0</code>, so the attacker's chain is always at a disadvantage.

For withholding shares, the attacker has a dilemma. A workshare must be published at least 6 seconds before its containing block to be counted (Table 5). On the contrary, the attacker's withheld block must be published at most 5 seconds after the corresponding honest block (Table 4). Therefore any witholding strategy will always have either <code>l<sub>w</sub> = 0</code> or <code>l<sub>b</sub> = 0</code>.

Additionally, when withhoding shares, the attacker typically won't be able to include honest workshares in his first private block due to duplicate `version_minor` values.

#### Long forks

If the attacker can mine at least 48 work objects faster than the honest majority, he can avoid the lateness penalties.

The probabilty of this happening is < 0.06% with `α = 0.33`. The attacker can expect to achieve this on average once per 10 days of selfish mining (these numbers are based on the formulas from [4]) and the result will be, on average, a 3-block reorg. This can be compared with Nakamoto consensus, when the `α = 0.33` attacker can effect a 3-block reorg on average once per hour.

For deeper reorgs of 10+ blocks, the situation is more complicated, but Monte Carlo simulations show that the attacker can achieve on average about 1 such reorg per 3 years of stubborn mining (see [5] for details about stubborn mining strategies). With Nakamoto consensus, the attacker can expect to achieve several 10-block reorgs per day.

Note that by Table 3, blocks with 160+ confirmations will use the standard block difficulty as their weight. The SoP chain weight will converge to this value with a sufficient number of blocks.

#### Partition recovery

Since the subjective block weights are limited to forks of fewer than 48 work objects (Tables 4 and 5), network partitions will on average resolve after 3 blocks, when the objective chain weights kick in. The same applies to offline nodes joining the network (which can be considered a special case of a network partition).

### References

[1] [Selfish mining mitigations (Publish or Perish)](https://github.com/monero-project/research-lab/issues/144) (github issue)

[2] [Publish or Perish: A Backward-Compatible Defense Against Selfish Mining in Bitcoin](https://www.researchgate.net/publication/312184074_Publish_or_Perish_A_Backward-Compatible_Defense_Against_Selfish_Mining_in_Bitcoin) (PDF paper)

[3] [FruitChains: A Fair Blockchain](https://eprint.iacr.org/2016/916) (PDF paper)

[4] [Success probability of a double-spend attack with minority hashpower share](https://github.com/monero-project/research-lab/issues/102#issuecomment-2402750881) (github comment)

[5] [Stubborn Mining: Generalizing Selfish Mining and Combining with an Eclipse Attack](https://eprint.iacr.org/2015/796) (PDF paper)
