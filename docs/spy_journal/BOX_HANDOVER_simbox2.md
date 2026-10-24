# BOX_HANDOVER.md — lithium (192.168.1.25, `simbox2`)

Written 2026-10-24 14:20 UTC by the antiproxy spy-node lab's agent (runs on the coordinator box 192.168.1.140 as `antiproxy`)
for whoever drives this box next: the selfish-mining project's agent (same coordinator box, user `selfishmining`). The lab has
stopped using this box. Nothing of the lab's runs here and nothing will be queued here again.

## The box
- Ryzen 9 5900XT, 32 threads, 31 GB RAM (no swap worth counting), 931 GB NVMe (`/` 885 GB, 187 GB free before the lab's cleanup).
- Ubuntu 24.04.5 (upgraded from 22.04 on 2026-10-22), kernel 6.8.0-147, glibc 2.39, gcc 13. Passwordless sudo for `lever65`.
- Login: `lever65@192.168.1.25`. The coordinator's `antiproxy` account reaches it with `~/.ssh/simbox2_ed25519`; set up your own key.
- KSM is on by hand (`run=1`, `pages_to_scan=20000`, `sleep_millisecs=20`) and is lost on reboot; no tmpfiles rule was added.
  Ubuntu's default `sleep_millisecs` 200 is far too slow for a Shadow run of hundreds of monerod; raise it again if you reboot.
- Real-time clock and network are plain; nothing is firewalled between the lab boxes.

## Not the lab's: leave alone unless the owner says otherwise
- A real **testnet `monerod` and `msnm-sidecar`** run as systemd services under user `monero` (both `active` at handover). They use
  CPU, RAM and disk continuously; the lab ran its sims beside them without touching them.
- `~/mininghooks`, `~/msnm-sidecar-src`, `~/msnm-sidecar.bak-*`, `~/logtrial*`, `~/dns_work.md`, `~/THISBOXISCLEAN.txt`,
  `~/fullupgrade.log`, `~/relupgrade.log`: the owner's.
- `aznfs` (Azure NFS helper) is installed.

## The lab's leftovers (yours to delete once the owner confirms the archives verified on the array)
- `~/monerosim_archives/` (172 GB, 21 finished Shadow runs). Being copied to the Threadripper's array
  `/spinny/readfrom/20261024_monerosim_research_effort/archives/` (mounted here read/write at `/mnt/research`, fstab) on 2026-10-24
  from 14:17 UTC; `~/queue/pool_copy.done` says `EXIT 0` when the copy finished and the lab's journal records the verification.
  **Until that line exists, do not delete the folder.** After it, the 172 GB are free to reclaim.
- `~/monerosim/` (1.3 GB): a clone of the lab's branch `feat/spy-relay-log` at `7612d25f`, three local uncommitted files (scratch).
  Not the PoW project's `main`. Delete or replace with your own clone.
- `~/.monerosim/` (511 MB): the lab's `setup.sh --sim-binary` install (monerod-sim with nine vendored patches, Shadow, calibration).
  Your `setup.sh` run will overwrite it, which is fine. `~/.monerosim.feb2026` (188 MB) is an older backup, deletable.
- `~/queue/`: the lab's queue driver (`x0_queue.sh`, events log, scoring outputs). Nothing runs. Deletable; the events log is
  already snapshotted into the lab's journal.
- Stray files in `~`: `est_half_w24.*`, `spy_share_vs_time.py`, `install_sim_fixseed.log`, `setup_sim.log`. Deletable.
- `/mnt/research` NFS mount and its `/etc/fstab` line: harmless to keep (it is the shared research array); remove if unwanted.

## What the lab learned about running Shadow here (for whatever you run)
- ~70 monerod-sized daemons per 31 GB without KSM; with KSM at the setting above the lab ran 384-daemon cells with ~11 GB free at
  the lowest point. The lab's driver refused to start below 1.5 GB free RAM or 30 GB free disk.
- The testnet monerod beside you is a real network peer: do not bind Shadow or any sim to the host's ports it uses, and expect it
  to take a core or two.
- Cell configs resolve timing from the box's core count and `~/.monerosim/calibration.json`; a config generated here is not
  byte-identical to one generated on a 64-thread box. Generate where you run, or pin the inputs.

Questions: the lab's journal is `docs/SPY_EXPERIMENT_JOURNAL.md` on branch `feat/spy-relay-log` (GitHub, same repo as `main`);
the coordinator-side notes are in the `antiproxy` account there.

*Verified 2026-10-24 15:48 UTC:* the copy finished (`EXIT 0`), a dry-run rsync against the array lists nothing left to send, and both sides hold 58,373 files. The lab needs nothing further from this folder; it may be deleted when the owner says so.
