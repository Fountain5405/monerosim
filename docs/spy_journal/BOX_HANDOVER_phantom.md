# BOX_HANDOVER.md — phantom (192.168.1.22)

Written 2026-10-24 14:30 UTC by the antiproxy spy-node lab's agent (coordinator box 192.168.1.140, user `antiproxy`) for the
selfish-mining project's agent (same coordinator box, user `selfishmining`), which takes this box over. The lab ran its Shadow
cells here from 2026-10-21 to 2026-10-24 08:11 and has stopped; nothing of the lab's runs here and nothing will be queued again.

**One thing is still in flight:** the lab's archive pool `/mnt/ssdpool/monerosim_archives/` (304 GB, 38 finished runs, 100k files)
is being copied to the Threadripper's array (`/spinny/readfrom/20261024_monerosim_research_effort/archives/`, mounted here at
`/mnt/research`). `~/queue/pool_copy.done` reads `EXIT 0` when the copy has finished; the lab's journal then records the
verification. **Do not delete or move that folder before then.** Running your own sims beside the copy is fine.

## The box
- 32 threads, 31 GB RAM, Ubuntu 24.04.5, kernel 6.8.0-146. Root 442 GB (80 GB free), `/mnt/ssdpool` 440 GB (118 GB free; 304 GB
  of it is the lab's pool above).
- This is the owner's workstation, not a bare sim box: dozens of the owner's projects live in `~` (monero trees, llama.cpp and
  models, explorers, analyses, `Cline`, …). Treat everything not listed under "the lab's" as the owner's and leave it alone.
- A real **testnet `monerod` (FCMP++ stressnet, unpruned, internet-facing, port-forwarded) and `msnm-sidecar`** run as systemd
  services, both `active`. They take CPU, RAM, disk and network continuously; the lab ran 384-daemon cells beside them.
- Other logins are usually present (`user` and `lever65` sessions from 192.168.1.128). Kill only your own processes, by pid.
- KSM is on by hand (`run=1`, `pages_to_scan=20000`, `sleep_millisecs=20`), lost on reboot; Ubuntu's default 200 ms sleep is too
  slow for Shadow runs of hundreds of monerod. No tmpfiles rule was added.
- The lab's Shadow runs used 16 workers here; a 384-daemon, 30 h cell took 3 h 45 m with ~10.6 GB free RAM at the lowest point.
  The lab's driver refused to start below 1.5 GB free RAM or 30 GB free disk.

## The lab's footprint
- `/mnt/ssdpool/monerosim_archives/` (304 GB): the pool, copying out (see above). Reclaimable after the verification line.
- `~/monerosim/` (82 GB): the owner's clone of the monerosim repo, which the lab's earlier sessions worked in (branch
  `feat/spy-relay-log`, clean at `f91d855a`; the coordinator pushes into it, `receive.denyCurrentBranch updateInstead`). 77 GB of it is
  `archived_runs/` (gitignored): 173 runs dated 2026-09-20 to 10-21 named `selfish_*`, `gamma_eclipse_*`, `ecl*`, `pop_*`, i.e. the
  selfish-mining/PoP project's own earlier output, **not the lab's**; yours to keep or prune. **Owner's checkout: do not delete.**
  Check out `main` or make your own clone elsewhere for the PoW work.
- `~/.monerosim/` (772 MB): the lab's `setup.sh --sim-binary` install (monerod-sim with ten vendored patches, Shadow v0.2.5,
  calibration). Your own `setup.sh` run overwrites it; that is fine. `~/.monerosim/calibration.json` here (md5 `e5276ee0`) is the
  reference the lab's cell generator pins; the lab keeps its own copy.
- `~/queue/`: the lab's queue driver (`x0_queue.sh`, `x0_queue2.sh`), its events log and `old_session/` logs. Nothing runs.
  Deletable after the pool copy (it holds `pool_copy.log`/`.done`); the events are snapshotted in the lab's journal.
- `/tmp/claude-1002/-home-lever65-monerosim/`: the earlier lab sessions' scratch (Claude Code session dirs). Deletable.
- `/mnt/research` NFS mount and its `/etc/fstab` line: the shared research array, harmless to keep.
- `~/install_sim_fixseed.log`: a lab build log, deletable.

## Reaching it
`lever65@192.168.1.22`, passwordless sudo. The coordinator's `antiproxy` account reaches it as `ssh phantom`; set up your own key.
The lab's journal is `docs/SPY_EXPERIMENT_JOURNAL.md` on branch `feat/spy-relay-log`.

*Verified 2026-10-24 16:05 UTC:* the pool copy finished (rsync exit 23 came only from directory-timestamp lines on folders the NFS pass had created), a dry-run rsync against the array lists nothing left to send, and both sides hold 100,813 files in 38 runs. The lab needs nothing further from `/mnt/ssdpool/monerosim_archives`; it may be deleted when the owner says so. The lab also stopped pushing into `~/monerosim` (its `phantom` remote removed), so that checkout is the owner's alone from here.
