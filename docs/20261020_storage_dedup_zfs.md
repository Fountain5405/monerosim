# Per-node chain and log storage: compress it, dedup doesn't pay

Status: an idea for scaling hardware, measured (2026-10-20); nothing is built.
The question was whether the per-node blockchains can be shared the way KSM
shares the RandomX cache, because 1k-node runs have used 300-500 GB of disk.
Short answer: page-level dedup of the chains falls to ~1.2x once transactions
flow, but a compressing filesystem under the run (ZFS or btrfs, created per run
if wanted) would cut the logs ~20x and the chains ~1.4x.

## The problem

Every monerod keeps its own LMDB (`data.mdb`) under the run's
`/tmp/monerosim-<run>/monero-<node>/`. A chain grows by about **3.2 KB per
transaction per node**: the 32 GB box's 500 rung ended at 9.9 MB for 2,982
transactions. At the 128-core ladder's transaction counts that gives:

| Rung | User txs | Chain per node | All nodes' chains | Logs (doc budget) |
|---|---|---|---|---|
| 1k | 18,953 | ~60 MB | ~60 GB | ~130 GB |
| 2k | 33,586 | ~107 MB | ~215 GB | ~180 GB |
| 3k | 39,969 | ~128 MB | ~385 GB | ~365 GB |

These are estimates; real files also carry LMDB free pages from mined-out
txpool entries. The disk budget in `PERFORMANCE_AND_SCALE.md` ("~97% of run
bytes are `net.p2p.msg` lines") counts archived run directories, which keep 1%
of the chains, so it leaves these out. Peak disk during a run is logs plus
chains, and at 2k-3k nodes the two are about equal.

It is a disk problem, not a RAM one. On the X0 no-churn pilot (455 daemons,
sim 1.5 h) relay-001's `data.mdb` took 1.6 MB of RAM against 17.6 MB of PSS for
the whole process, and the pages are evictable page cache because `/tmp` is on
ext4.

## Measured (2026-10-20)

**Identical 4 KiB pages across nodes' `data.mdb`:**

| Chain state | Nodes | Pages | Distinct | Dedup | Pages in every node |
|---|---|---|---|---|---|
| X0 no-churn pilot, sim 1.5 h, before any user tx | 40 | 59.7 MB | 2.5 MB | 23x | 249 of ~382 |
| same run, sim 6.5 h, 1.5 h of user txs | 40 | 88.1 MB | 42.8 MB | 2.06x | 227 of ~564 |
| box32 500 rung, end of run (2,982 txs) | 3 | 29.4 MB | 24.1 MB | 1.22x | 491 of ~2,512 |

(X0 run: `archived_runs/20261020_165536_x0_legacy_none_s12345_nochurn`; 500
rung: `archived_runs/20261019_125036_box32_500_100u_400r`, its three archived
chains.)

**The data is identical; the bytes are not.** On the 500 rung's three
chains, `mdb_dump` of every chain table (blocks, block_info, txs_pruned,
txs_prunable, tx_indices, output_amounts, spent_keys) matches exactly, and even
the txpools hold the same 26 entries. Records are also grouped onto pages the
same way:

| Plain leaf pages, 3 nodes (3x is the most possible) | Dedup |
|---|---|
| same set of keys on the page | 2.99x |
| same keys and values, ignoring pointers to other pages | 2.79x |
| same keys and values as stored | 2.46x |
| whole raw 4 KiB page | 1.22x |

What differs is page numbers. A page's header holds its own page number,
records point to overflow pages (large values: blocks, proofs) and sub-tables
by page number, and a page's free gap keeps bytes from its earlier versions.
LMDB is copy-on-write: every write takes a page from that node's freelist,
which depends on its whole write history (when its write transactions
committed, what its txpool added and removed, which old snapshots RPC readers
held), so the same page lands at a different number in each file. Only free
space is stale: 179 of 2,512 pages. Byte-identical files would need
deterministic page placement (the txpool in its own file, chain writes
committed at the same block boundaries on every node, no reader-dependent
reuse), which is too fragile to build on; sharing has to be logical (the
shared base below). With about a fifth of the raw pages common to all nodes,
page dedup can't pass ~1.25x however many nodes there are.

**Compressibility** (zstd -3):

| File | Ratio |
|---|---|
| `bitmonero.log` at `monitor` (miner-001, 9.3 MB; user-001, 1.5 MB; X0 churn pilot) | 24x, 19x |
| `txrelay.jsonl` (miner-001) | 7x |
| `data.mdb` before user txs / after 1.5 h of txs / end of the 500 rung | 3.6x / 2.6x / 1.4x |

Whole-file ratios; per-record compression in a filesystem is somewhat lower.

## Why KSM and Shadow can't share the chains

- **KSM merges only private anonymous memory.** LMDB maps its file shared, and
  the page cache is per file, so 455 identical files are cached 455 times.
- **Shadow never sees the data.** With `db-sync-mode: fastest` monerod opens
  LMDB with `MDB_WRITEMAP` (the mapping is `rw-s`), so every read and write is a
  memory access into the mapping, not a syscall. Shadow sees `open`, `mmap` and
  the occasional `msync`, nothing to reroute.
- **Shadow could change what backs the mapping**, handing monerod private
  anonymous memory loaded from the file so that KSM merges identical pages. The
  measurements above cap what that could merge at ~1.2x for transaction-heavy
  chains, and the database would vanish at process exit (turnover restarts, the
  chain archive).

## The proposal: a compressing filesystem under the run's data

Put the daemons' data directories (`general.daemon_data_dir`) and Shadow's data
(`run_sim.sh --data-dir`) on a filesystem that compresses as it writes: a ZFS
dataset with `compression=zstd`, or btrfs mounted with `compress=zstd`. No
change to monerod, Shadow or monerosim. Record sizes for ZFS:
- **logs: 1M**, appended text.
- **chains: ~16K.** LMDB writes 4 KiB pages at random offsets, so large records
  mean read-modify-write of the whole record, but with 4K sectors a 4K record
  cannot shrink at all, so 4K records would give no compression.

btrfs compresses in 128K extents and is copy-on-write, so LMDB files fragment
on it; it suits the logs better than the chains. At the 3k
rung's numbers, ~365 GB of logs would become ~20-30 GB and ~385 GB of chains
~275 GB, so the chains become most of what is left.

**Dedup is not worth it.** At ~1.2x it would not pay for ZFS's dedup table
(~320 bytes of RAM per unique record in ZFS 2.2: the 3k rung's chains in 4K
records would need ~25 GB of table). Dedup would handle forks without special cases (shared history
stored once, each branch's pages separately), but forks don't matter to
compression either, which works per file.

**Costs and risks.** CPU for compression; memory-mapped files on ZFS sit in
both the page cache and the ARC, so the ARC needs a cap (`zfs_arc_max`); wall
time is unmeasured.

## Per-run pools

The filesystem need not be part of the system: a run can create one and tear
it down, as `run_sim.sh --ramdisk` already does with a tmpfs (sudo mount, a
cleanup trap that also fires on Ctrl-C). Ubuntu's kernel ships the ZFS module
(the 32-thread box has `zfs.ko` 2.2.2), so only `zfsutils-linux` is missing;
btrfs needs only `mkfs.btrfs` on a loop device. A `--zfs` (or `--compress`)
option would:
1. create a sparse file (say 1 TB nominal; it holds only what is written,
   after compression);
2. `zpool create` on it, or `mkfs.btrfs` on a loop device, with the settings
   above;
3. point `daemon_data_dir` and `--data-dir` at it, and run;
4. archive, then destroy the pool (or unmount and detach) and delete the file,
   also from the trap.

Points to settle:
- **Archiving decompresses.** Copying results back to ext4 writes them at full
  size, so the archive would undo the logs' ~20x. Either compress during
  archiving or keep archives on a compressed dataset.
- **A long-lived pool with per-run datasets** (`zfs create` / `zfs destroy`)
  is cheaper than a pool per run and keeps concurrent runs apart. A pool per
  run is the most self-contained.
- **Sudo**, as for `--ramdisk`.
- **A file-backed pool writes through ext4 underneath.** A spare LVM volume
  avoids that layer for big runs (the 32-thread box has ~26 GB free in
  ubuntu-vg and ~40 GB in sharevg).

## Test plan

1. Install `zfsutils-linux` (or use btrfs); create a pool on a spare LV or a
   file.
2. Run one small config twice, on ext4 and on the compressed filesystem.
   Compare wall time, `zfs get compressratio` per dataset, the ARC size, and
   peak disk.
3. If that holds, a 1k run on the big box against an ext4 run.

## Considered and set aside

- **Dedup** (ZFS, or the Shadow-plus-KSM variant above): ~1.2x on
  transaction-heavy chains.
- **A shared read-only base LMDB plus a per-node delta** (a monerod
  storage-layer patch): it saves only the shared base, which today is a
  236 KB warm-start snapshot. It would pay off for a large prebuilt history,
  e.g. a realistic output set for decoy selection, and would need a base
  height below every fork point.
- **Reflink copies** (XFS, btrfs) share blocks only at copy time, writes break
  the sharing, and ext4 has none.
- **overlayfs** copies the whole file up on the first write.
- **`--prune-blockchain`** never prunes the newest 5,500 blocks; these runs stay
  under 2,000.
- **One shared writable LMDB** would let nodes see blocks and transactions that
  never reached them over the simulated network, and LMDB allows one writer.
