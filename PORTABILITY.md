# Monerosim Linux Distro Portability Audit & Remediation Plan

**Date:** 2026-05-08
**Scope:** Native cross-distro portability (no containerization).
**Method:** Five parallel investigation passes (shell, Rust, Python, build/deps,
cross-cutting) plus targeted verification reads. Prior audit/planning files were
flagged and skipped (see Open Questions).

---

## 1. Executive summary

Monerosim was developed on Ubuntu since summer 2025 and the documentation
explicitly recommends Ubuntu 22.04+. The actual code, however, is **closer to
distro-agnostic than the docs suggest** — the Rust crate is pure-Rust (no
sys-crates), the Python agent code uses `#!/usr/bin/env python3` and POSIX
APIs, and `setup.sh` already branches across `apt-get`, `yum`, and `pacman`.

What's broken is at the **edges**:

1. **`setup.sh` package-manager dispatch is incomplete and buggy.**
   - `dnf` (modern Fedora/RHEL 8+ default), `zypper` (openSUSE), and `apk`
     (Alpine) are not detected — the script `exit 1`s on those distros.
   - Several `yum` and `pacman` package names are **wrong** (e.g.
     `sodium-devel` should be `libsodium-devel`; `pgm-devel` should be
     `openpgm-devel` from EPEL; pacman's `sodium` should be `libsodium`).
     RHEL/Fedora users following the docs would hit a hard failure.
   - The Python venv install branch on yum/pacman installs the wrong package
     entirely (`python3-virtualenv` is the third-party `virtualenv` tool, not
     stdlib `venv`; on RHEL/Arch, `venv`+`ensurepip` ship inside `python3`).
   - A control-flow quirk in `setup.sh:270-287` means the full dev-library
     install only runs when `gcc` itself is missing — so an RHEL minimal box
     with `gcc` already installed but no `boost-devel` will silently skip the
     dep install and fail at compile time.

2. **User docs claim "Debian and Arch also supported"** but the README install
   block (`README.md:239-240`) is `apt-get`-only with no alternative and the
   recommended `sudo adduser monerosim` is the Debian interactive helper —
   distinct from `useradd` on RHEL/Arch/openSUSE.

3. **A handful of small portability hazards in shell scripts:** `grep -oP`
   (Perl regex; not in BusyBox), `pgrep -xf` (not on Alpine minimal), `bc`
   (not on Alpine minimal), `sort -V`, `readlink -f` — all in non-critical
   monitoring/dashboard scripts. Top-level scripts are `#!/bin/bash` so the
   bashisms inside them are correct, just gated on bash being installed.

4. **Rust code has minor cosmetic Ubuntu-isms:** generated agent wrapper
   scripts use `#!/bin/bash` and a hardcoded `PATH=/usr/local/bin:/usr/bin:/bin:...`
   prefix (Debian-style ordering), and a `GLIBC_TUNABLES` env var is set
   unconditionally (harmless on musl, just ignored).

5. **Alpine (musl) is the only target that requires structural work.**
   Shadow itself and the Monero daemons are typically built against glibc;
   the sibling repos may need patches we don't control. PyYAML's musl wheel
   exists in modern releases, so the Python side is fine.

**Bottom line:** Debian/Ubuntu, RHEL/Fedora/Rocky/Alma (with EPEL), Arch, and
openSUSE are reachable with **modest, mostly mechanical fixes** (Wave 1+2
below — order of an afternoon's work for someone with all the test VMs in
hand). Alpine/musl is a deliberate choice — out of scope unless someone
commits to validating the sibling Shadow and Monero builds on musl.

### Verified end-to-end (2026-05-12)

Following the Wave 1+2 fixes (now merged), the following distros were
verified by running `./setup.sh` to completion and successfully running
the quickstart simulation end-to-end:

| Distro          | Status |
|-----------------|:------:|
| Ubuntu 24.04    | ✅     |
| Fedora 43       | ✅     |
| Debian 13       | ✅     |
| Rocky 10        | ✅     |
| openSUSE 16     | ✅     |

This supersedes the unknown / "probably works" markings for these distros
in §2 below. RHEL/Rocky/Alma **9** remains unsupported (see §5).

---

## 2. Distro coverage matrix

Legend: ✅ works · 🟡 probably works · ❌ breaks · ❓ unknown

| Module / Component                         | Debian/Ubuntu | RHEL/Fedora/Rocky/Alma | Arch | openSUSE | Alpine (musl) |
|--------------------------------------------|:-------------:|:----------------------:|:----:|:--------:|:-------------:|
| Rust crate (`cargo build`)                 | ✅ | ✅ | ✅ | ✅ | 🟡 (musl target works for Rust; see below) |
| `monerosim` CLI runtime (config gen)       | ✅ | ✅ | ✅ | ✅ | 🟡 |
| Python agent runtime (inside Shadow)       | ✅ | ✅ | ✅ | ✅ | 🟡 (PyYAML wheels exist; needs verification) |
| `setup.sh` — package manager detection     | ✅ | ❌ (no dnf branch) | ✅ | ❌ (no zypper) | ❌ (no apk) |
| `setup.sh` — apt package list              | ✅ | n/a | n/a | n/a | n/a |
| `setup.sh` — yum package list              | n/a | ❌ (`sodium-devel`, `pgm-devel`, `qt5-linguist` wrong) | n/a | n/a | n/a |
| `setup.sh` — pacman package list           | n/a | n/a | 🟡 (`sodium` should be `libsodium`) | n/a | n/a |
| `setup.sh` — Python venv branch            | ✅ | ❌ (installs wrong package) | ❌ (installs wrong package) | ❓ | ❌ |
| `setup.sh` — full build (Shadow + Monero)  | ✅ | 🟡 (untested; deps OK once names fixed) | 🟡 (untested) | ❓ | ❌ (musl rebuild needed) |
| `start_here.sh` (interactive bootstrap)    | ✅ | 🟡 (bash present; same dep issues as setup.sh) | 🟡 | ❓ | ❌ (bash not default) |
| `run_sim.sh`                               | ✅ | 🟡 | 🟡 | 🟡 | ❌ (bash, `lsof`) |
| `scripts/check_sim.sh` (dashboard)         | ✅ | 🟡 (`grep -oP` is GNU-only — works on RHEL/Arch/SUSE) | 🟡 | 🟡 | ❌ (BusyBox grep, no `pgrep`) |
| `scripts/scaling_test.sh`, `prune_archives.sh` | ✅ | 🟡 | 🟡 | 🟡 | ❌ |
| Shadow (sibling repo) build                | ✅ | 🟡 | 🟡 | ❓ | ❌ (musl) |
| Monero (sibling repo) build                | ✅ | 🟡 | 🟡 | ❓ | ❌ (musl) |
| Documentation (README / QUICKSTART)        | ✅ accurate | ❌ inaccurate (`adduser`, no per-distro install block) | ❌ | ❌ | ❌ |

---

## 3. Findings

Each finding lists `file:line — what — breaks where — effort`.

### 3.1 Package management & system dependencies

**F-PKG-1 · Incomplete package-manager detection**
- `setup.sh:245-256` — Detects only `apt-get`, `yum`, `pacman`. Missing `dnf`
  (modern Fedora/RHEL ≥8 use dnf, not yum; yum is a compatibility symlink on
  RHEL 8/9 but the canonical CLI is dnf), `zypper` (openSUSE), `apk` (Alpine).
  Same gap repeats at `setup.sh:320-329` (Python venv branch),
  `setup.sh:412-422` (Shadow deps), `setup.sh:633-656` (Monero deps).
  - Breaks on: Fedora ≥22 (dnf-only systems where `yum` is missing);
    openSUSE; Alpine.
  - Effort: **small** (add `elif command -v dnf/zypper/apk`).

**F-PKG-2 · Wrong yum package names**
- `setup.sh:281` —
  - `sodium-devel` → should be **`libsodium-devel`**.
  - `pgm-devel` → should be **`openpgm-devel`** (and is in EPEL, not base
    repos; users need EPEL enabled).
  - `qt5-linguist` is the Fedora package; on RHEL/CentOS Stream it ships as
    part of `qt5-qttools-devel`. Verify per-distro.
  - `libusbx-devel` is correct on RHEL ≤7 / older Fedora; current Fedora and
    RHEL 9 ship `libusb1-devel`. Verify and pick.
  - Breaks on: RHEL/Fedora/Rocky/Alma. Effort: **trivial**.
- `setup.sh:644` (Monero deps yum branch) — same `sodium-devel` and missing
  `pgm-devel` issues. Effort: **trivial**.

**F-PKG-3 · Wrong pacman package names**
- `setup.sh:283` —
  - `sodium` → should be **`libsodium`**.
  - `qt5-tools` is correct (good).
  - Breaks on: Arch / Manjaro. Effort: **trivial**.
- `setup.sh:650` (Monero deps pacman branch) — same `sodium` typo.

**F-PKG-4 · Python venv branch installs wrong package on non-Debian**
- `setup.sh:325-328`:
  - yum branch: `sudo yum install -y python3-virtualenv` — this installs the
    third-party `virtualenv` tool, not Python's stdlib `venv`. On RHEL ≥8 and
    Fedora, `python3` ships with `ensurepip`/`venv` built in; the failure
    case the script is reacting to (missing `ensurepip`) typically doesn't
    happen on modern RHEL/Fedora at all.
  - pacman branch: `sudo pacman -S --noconfirm python-virtualenv` — same
    issue. Arch's `python` package includes `venv` natively.
  - Breaks on: RHEL/Fedora/Arch — at minimum, installs an unnecessary package;
    if `ensurepip` is genuinely missing for some reason, this won't fix it.
  - Effort: **small** — replace yum/pacman branches with a no-op + clearer
    error, since on those distros the venv module is part of `python3`.

**F-PKG-5 · "Bulk dev libs only install when gcc is missing"**
- `setup.sh:269-287` — The case arm at line 276 (`gcc|g++`) is the only one
  that installs the full development library list (`libssl-dev libzmq3-dev …`).
  If a user has `gcc` already installed but is missing, say, `libssl-dev`,
  the loop will only install the named single packages (`git`, `cmake`, etc.)
  and silently skip the bulk list. The Shadow/Monero compile then fails
  later with cryptic linker errors.
  - Breaks on: any distro where `gcc` is preinstalled but library headers
    aren't (very common on RHEL minimal, Arch base, Fedora cloud images).
  - Effort: **small** — restructure to install the bulk list whenever any
    library dep is in `MISSING_DEPS`, or always install the bulk list when
    bulk-install mode is needed.

**F-PKG-6 · pkg-config not guaranteed installed**
- `setup.sh:397` — `pkg-config --exists "glib-2.0 >= 2.58"`. If `pkg-config`
  itself isn't installed (RHEL minimal, Alpine without `pkgconf`), this
  command fails and the script then tries to install glib2-dev — but since
  the conditional triggered correctly, this works incidentally. Still, the
  initial dep-checking at `setup.sh` start should include `pkg-config`/
  `pkgconf` as a required tool.
  - Effort: **trivial**.

**F-PKG-7 · Python C-extension wheels**
- `pyproject.toml:33` — `PyYAML>=6.0`. PyYAML ships with a C-accelerated
  parser; modern releases (≥6.0.1) publish manylinux2014 (glibc ≥2.17) and
  musllinux wheels, so wheel availability is fine on RHEL 8+, Arch, openSUSE,
  and modern Alpine. Older Alpine (pre-2023 wheel rollout) would compile
  from source and need `build-base python3-dev libyaml-dev`.
  - Effort: **trivial** (document only).
- Other deps (`requests`, `networkx`, `dnslib`) are pure Python — no
  cross-distro concerns.

### 3.2 Init system & service management

**No findings.** No `systemctl`, `journalctl`, `loginctl`, `sd_notify`,
socket-activation, systemd-timer, or unit-file drops anywhere in the project.
Monerosim does not register itself as a system service. ✅

### 3.3 glibc / libc & native libraries

**F-GLIBC-1 · `GLIBC_TUNABLES` set unconditionally**
- `src/orchestrator.rs:157-158` — Sets `GLIBC_TUNABLES=glibc.malloc.arena_max=1`
  and `MALLOC_ARENA_MAX=1` as env vars passed to spawned simulation processes.
  Harmless on musl (the variables are ignored), but a cleaner story would
  guard with `#[cfg(target_env = "gnu")]` or detect at runtime.
  - Effort: **trivial**.

**F-GLIBC-2 · Cargo.toml is pure-Rust**
- `Cargo.toml` — No `*-sys` crates, no `openssl-sys`, no `bindgen`,
  no `pkg-config`-driven sys deps, no native-binary-bundling crates. The
  only borderline case is `zstd 0.13` which vendors zstd source. ✅

**F-GLIBC-3 · Sibling repos compile against glibc by default**
- Shadow and Monero (cloned by `setup.sh`) — neither is musl-tested. Building
  on Alpine would require validating each upstream supports musl.
  - Breaks on: Alpine. Effort: **large** (out-of-scope unless prioritized).

### 3.4 Shell & utilities portability

**F-SH-1 · Top-level scripts are `#!/bin/bash`**
- `setup.sh:1`, `start_here.sh:1`, `run_sim.sh:1`, `update.sh:1`,
  `smart_config_tool.sh:1`, `scripts/check_sim.sh:1` (and the rest) all use
  `#!/bin/bash`. The bashisms inside (`[[ ]]`, arrays, `(( ))`, `local`) are
  legal under that shebang. **This is correct portability practice.** The
  only break is on Alpine where bash isn't installed by default — fix is
  `apk add bash`, which the Alpine setup branch (when added in Wave 1)
  should do.
  - Breaks on: Alpine without bash. Effort: **trivial** (document; Wave 2
    bootstrapper installs bash).

**F-SH-2 · `grep -oP` (Perl regex) — GNU-only**
- `scripts/check_sim.sh:253, 798` — `grep -oP '(?<=…)\d+'` uses lookbehind.
  PCRE is GNU grep–only; works on RHEL/Fedora/Arch/SUSE, fails on Alpine
  BusyBox grep.
  - Breaks on: Alpine. Effort: **small** — replace with `grep -oE` + `awk`/`sed`.

**F-SH-3 · `pgrep -xf` not in BusyBox by default**
- `scripts/check_sim.sh:66` — Alpine needs `apk add procps` for `pgrep`.
  - Breaks on: Alpine minimal. Effort: **trivial** (document or add apk dep).

**F-SH-4 · `readlink -f` — BusyBox lacked it historically**
- `scripts/check_sim.sh:68, 86, 115` — BusyBox readlink added `-f` around
  v1.27 (2017); modern Alpine has it but ancient Alpine images don't.
  - Breaks on: very old Alpine / minimal busybox builds. Effort: **trivial**.

**F-SH-5 · `bc` not installed by default on Alpine/RHEL minimal**
- `scripts/check_sim.sh:873`, `scripts/scaling_test.sh:316` — Float arithmetic
  via `bc -l`. RHEL minimal and Alpine both omit it.
  - Breaks on: Alpine, RHEL minimal. Effort: **trivial** — replace with
    `awk 'BEGIN{print …}'` or `python3 -c`.

**F-SH-6 · `sort -V` (GNU coreutils version sort)**
- `setup.sh:199` (and similar) — Used to compare semantic version strings
  for Rust. Available on glibc distros' GNU coreutils (Debian, RHEL, Arch,
  SUSE) but not on BusyBox sort.
  - Breaks on: Alpine. Effort: **small** — implement portable version compare.

**F-SH-7 · `lsof` for ramdisk cleanup**
- `run_sim.sh:278-280` — `lsof +D` to find processes still using a ramdisk.
  Already wrapped in `2>/dev/null` with safe fallback, but `lsof` is a
  separate package on RHEL minimal and Alpine.
  - Breaks on: minimal installs without lsof. Effort: **trivial** (already
    defensive; document or use `fuser`).

**F-SH-8 · `mount -t tmpfs` syntax & permissions**
- `run_sim.sh:353` — `sudo mount -t tmpfs -o "size=…M,uid=…,gid=…,mode=0755"
  tmpfs "$RAMDISK_PATH"`. Syntax is portable across glibc distros. On Alpine
  the `mount` binary is BusyBox by default — most options work, but verify.
  - Effort: **trivial** (verification only).

**F-SH-9 · Bashisms in scripts that are correctly bash-shebanged**
- Multiple `[[ ]]`, `(( ))`, arrays, regex `=~` — all correct under `#!/bin/bash`.
  These are not portability bugs. Listed for completeness so they don't get
  flagged as findings in future audits. ✅

### 3.5 Filesystem layout

**F-FS-1 · Hardcoded `/bin/bash` for generated scripts**
- `src/utils/script.rs:44` — Default interpreter for generated agent
  wrappers is `/bin/bash`. Universal across all glibc distros (bash is at
  `/bin/bash`); Alpine without bash installed would fail.
  - Effort: **trivial** — the wrapper bodies are POSIX (only `cd`, `export`,
    `exec`); change to `#!/bin/sh` or detect.

**F-FS-2 · Hardcoded PATH `/usr/local/bin:/usr/bin:/bin`**
- `src/process/agent_scripts.rs:122`, `src/agent/pure_scripts.rs:84`,
  `src/agent/miner_distributor.rs:102`, `src/agent/simulation_monitor.rs:133`,
  `src/orchestrator.rs:282` — Generated wrapper scripts set
  `export PATH=/usr/local/bin:/usr/bin:/bin:{}/.monerosim/bin`. The order
  `/usr/local/bin` first is Debian convention; on RHEL/Arch/SUSE the system
  PATH ordering may differ but no breakage occurs because `/usr/local/bin`
  exists everywhere (often empty). Slightly cleaner: append rather than
  redefine.
  - Effort: **small** — change to `export PATH="$PATH:{}/.monerosim/bin"`.

**F-FS-3 · `/tmp/monerosim_shared`**
- `src/lib.rs:19, 22`, `src/config/defaults.rs:20`, `src/bin/tx_analyzer.rs:37`,
  `agents/base_agent.py:24`, `agents/agent_discovery.py:2,28`,
  `agents/public_node_discovery.py:22`, `scripts/...` — Hardcoded `/tmp/...`
  paths for the simulation shared-state directory. Works on every distro
  out of the box. Concerns:
  - `/tmp` is sometimes mounted with `noexec` on hardened RHEL/SUSE images.
    The shared dir doesn't host executables, so `noexec` is fine.
  - `/tmp` is sometimes systemd-tmpfiles–cleaned during long runs.
    Monerosim's runs are typically short; not seen in practice.
  - SELinux contexts on RHEL/Fedora may restrict `/tmp` access between
    confined processes — flag for testing.
  - Effort: **small** — make configurable via `MONEROSIM_SHARED_DIR` env var
    with `/tmp/monerosim_shared` as default; document.

**F-FS-4 · `~/.monerosim/bin/` install location**
- `setup.sh`, `run_sim.sh`, README, QUICKSTART — All install binaries under
  `$HOME/.monerosim/bin`. Distro-agnostic (uses `$HOME`); ✅.

**F-FS-5 · No `/lib/x86_64-linux-gnu/` references**
- Repo-wide grep — clean. ✅
- No `/lib64/` either. ✅
- No `/var/run` (deprecated) — the only `/run` references are in /proc/<pid>/
  paths via `os.readlink` and `os.path.exists`, which are fine. ✅

### 3.6 Users, groups, permissions

**F-USR-1 · `sudo adduser monerosim` in user docs**
- `README.md:5`, `QUICKSTART.md:11` — `adduser` is the Debian interactive
  helper around `useradd`. On RHEL/Fedora/Rocky/Alma/openSUSE, `adduser` is
  a symlink to `useradd` and supports a different (non-interactive) flag
  set; on Arch, `adduser` doesn't exist by default at all.
  - Breaks on: Arch (no `adduser`). On RHEL/SUSE the command runs but
    behaves differently and may not create a home directory without `-m`.
  - Effort: **trivial** — replace with `sudo useradd -m monerosim` (or show
    both with a one-line explanation).

**F-USR-2 · No hardcoded `sudo`/`wheel` group**
- Repo-wide grep — no hardcoded `wheel` vs `sudo` group references in code
  or scripts. ✅

**F-USR-3 · No hardcoded UIDs/GIDs**
- Code uses `id -u`/`id -g` (POSIX) at runtime. ✅

**F-USR-4 · `sudo` is universally assumed**
- `setup.sh`, `start_here.sh`, `run_sim.sh` — All assume `sudo` is present
  for system package installs and tmpfs mounts. `doas` (used on some hardened
  systems and minimal installs) is not handled. Documented as a prerequisite,
  so this is an accepted limitation.
  - Effort: **medium** if doas support is wanted (detect `sudo`/`doas` and
    abstract). Currently out-of-scope.

### 3.7 Security frameworks (AppArmor / SELinux)

**No findings.** Repo-wide grep for `aa-`, `apparmor`, `chcon`, `restorecon`,
`semanage`, `setsebool`, `runcon` — clean. No security-module assumptions in
code or config.

**Caveat (testing-only finding):** SELinux in enforcing mode on RHEL/Fedora may
restrict child processes from sharing files in `/tmp/monerosim_shared` or
spawning RPC ports — needs validation under enforcing mode. If issues arise,
the fix is either an SELinux policy module or rebasing the shared dir under
`$HOME` (per F-FS-3). Effort: **medium** if it surfaces.

### 3.8 Networking & DNS

**F-NET-1 · `ufw`, `firewall-cmd`, `iptables`, `nftables` — none used**
- Repo-wide grep — clean. The simulation runs all networking inside Shadow,
  so host-firewall manipulation isn't needed. ✅

**F-NET-2 · `/etc/resolv.conf`, systemd-resolved (`127.0.0.53`) — not touched**
- Repo-wide grep — clean. The in-sim DNS (`agents/dns_server.py`) operates
  inside Shadow's virtual network and doesn't interact with the host
  resolver. ✅

**F-NET-3 · `NetworkManager`/`systemd-networkd` — not used**
- ✅

**F-NET-4 · `lsof`/`mountpoint` for ramdisk** — see F-SH-7.

### 3.9 Runtime / interpreter assumptions

**F-RT-1 · Python interpreter discovery via `env`** ✅
- Every Python entry point (`agents/*.py`, `scripts/*.py`) uses
  `#!/usr/bin/env python3`. Robust across distros.

**F-RT-2 · Python ≥3.10 hard requirement**
- `pyproject.toml:10`, `setup.sh:308-312` — Reasonable. RHEL 8 ships 3.6 by
  default but has `python3.11` in AppStream. Document per-distro how to
  install Python 3.10+ (already partially in `setup.sh` but only for apt).
  - Effort: **small** (docs).

**F-RT-3 · `pip` and `venv`/`ensurepip` availability**
- Modern Debian/Ubuntu: `python3-venv` is a separate package (`setup.sh`
  handles correctly).
- Modern RHEL/Fedora/Arch/SUSE: `venv` and `ensurepip` ship inside the main
  `python3` package — the yum/pacman branches in `setup.sh:325-328` install
  the wrong thing (see F-PKG-4).
  - Effort: **small**.

**F-RT-4 · `subprocess.Popen(..., shell=True)` with bashisms**
- `agents/base_agent.py:349` — Wallet command is launched with `shell=True`.
  The string going in is constructed in code, so we control it; but it
  forwards through `/bin/sh`, which is `dash` on Debian/Ubuntu and `ash`
  (BusyBox) on Alpine. If the constructed string ever uses bashisms, it
  breaks. Currently looks like it uses only POSIX-compatible quoting.
  - Effort: **medium** (refactor to list args, drop `shell=True`, would also
    eliminate command-injection risk surface).

**F-RT-5 · `pgrep` with `/proc` fallback**
- `agents/base_agent.py:411-432` — Tries `pgrep -f` first, falls back to
  `/proc/<pid>/cmdline` parsing. Good defensive design. The `pgrep` failure
  is logged at WARN level — could be DEBUG since the fallback works.
  - Effort: **trivial** (cosmetic).

**F-RT-6 · `/proc/meminfo` parsing**
- `setup.sh:84-86` (`free -g | awk`); `scripts/calibrate.py:366-370`
  (parse `MemTotal:` from `/proc/meminfo`). Linux-portable; field names
  stable. ✅
- `agents/base_agent.py:432` reads `/proc/<pid>/cmdline` — Linux-portable. ✅

### 3.10 Distro detection (current state)

**F-DD-1 · Detection is via tool presence, not `/etc/os-release`**
- `setup.sh:245-256` uses `command -v apt-get/yum/pacman` — this is the
  **right approach** for "what package manager do I have," better than
  reading `/etc/os-release` for that purpose.
- No code reads `/etc/os-release`, `lsb_release`, or `/etc/debian_version`.
  ✅ (this is the intended pattern; just needs more branches — F-PKG-1).

### 3.11 Build / install scripts

**F-BLD-1 · No CI matrix**
- No `.github/`, no `.gitlab-ci.yml`, no `Jenkinsfile` or similar.
  Cross-distro testing is currently manual. Adding a CI matrix
  (Ubuntu 22.04, Fedora latest, Arch latest at minimum) would catch the
  bugs in F-PKG-2 / F-PKG-3 / F-PKG-4 / F-PKG-5 immediately.
  - Effort: **medium**.

**F-BLD-2 · `update.sh` mirrors `setup.sh` patterns**
- `update.sh` re-pulls and rebuilds; same package-manager assumptions
  cascade. Fixes in `setup.sh` should be reflected/shared.

### 3.12 Documentation

**F-DOC-1 · README install section is apt-only**
- `README.md:237-249` — The install block is `sudo apt-get install …` with
  no per-distro alternative. This contradicts the actual `setup.sh` (which
  branches across apt/yum/pacman) and contradicts QUICKSTART.md (which
  says "Debian and Arch also supported").
  - Effort: **small** — add a per-distro snippet or "see setup.sh which
    auto-detects your package manager" note, plus include the manual
    bootstrap deps the user needs **before** running `setup.sh` (currently
    `git build-essential cmake libglib2.0-dev libclang-dev clang`) translated
    for each supported distro.

**F-DOC-2 · QUICKSTART claims "Debian and Arch also supported"**
- `QUICKSTART.md:5` — Honest about scope; matches the apt/pacman branches
  in code. RHEL/Fedora and openSUSE are notably absent. Recommend updating
  once Wave 1 is done so this list reflects reality.
  - Effort: **trivial** (docs).

**F-DOC-3 · `sudo adduser monerosim`** — see F-USR-1.

---

## 4. Remediation plan

### Wave 1 — mechanical fixes (1 person-day)

These are local, low-risk, no-API-change edits. They make Monerosim
*correctly* support the distros it already claims to support, plus
openSUSE.

1. **Fix wrong package names in `setup.sh`** (F-PKG-2, F-PKG-3):
   - yum branch (lines 281, 644): `sodium-devel` → `libsodium-devel`;
     `pgm-devel` → `openpgm-devel` (note: in EPEL, document); audit
     `qt5-linguist` vs `qt5-qttools-devel` and `libusbx-devel` vs
     `libusb1-devel` per RHEL version.
   - pacman branch (lines 283, 650): `sodium` → `libsodium`.

2. **Add `dnf`, `zypper`, `apk` branches** (F-PKG-1):
   - At every `command -v apt-get/yum/pacman` block (`setup.sh:245-256`,
     `:320-329`, `:412-422`, `:633-656`), add `elif` for dnf, zypper, apk.
     `dnf` package names are identical to yum in 99% of cases (RHEL/Fedora
     packaging metadata is consistent).
   - Centralize the branching in a single helper: see Wave 2.

3. **Fix Python venv branch on yum/pacman** (F-PKG-4):
   - On yum/pacman, `python3` already includes `venv` and `ensurepip`. The
     branch should print a clearer error, not install `python3-virtualenv`.
   - On Alpine, install `python3` (which includes venv since 3.4).

4. **Restructure `setup.sh:269-287` so the bulk dep list installs whenever
   needed, not only when gcc is missing** (F-PKG-5):
   - Either (a) detect each library dep individually and install on demand,
     or (b) always install the full bulk list when in bulk-install mode.
     Option (b) is simpler and matches the actual intent.

5. **Fix `adduser` in user docs** (F-USR-1):
   - `README.md:5, 243`, `QUICKSTART.md:11` — replace with
     `sudo useradd -m monerosim` (and a note that some distros set up the
     home dir differently). `useradd` is universal; `adduser` is not.

6. **Add per-distro install instructions to `README.md`** (F-DOC-1):
   - Replace the apt-only block at `README.md:237-249` with a small table
     or per-distro tabs (Debian/Ubuntu, RHEL/Fedora, Arch, openSUSE), or
     a one-liner "run `./setup.sh` — it detects your package manager."

7. **Rust orchestrator quick wins** (F-FS-2):
   - Change generated wrapper PATH to append rather than override:
     `export PATH="$PATH:{}/.monerosim/bin"` instead of
     `export PATH=/usr/local/bin:/usr/bin:/bin:{}/.monerosim/bin`.
   - 5 sites: `src/process/agent_scripts.rs:122`,
     `src/agent/pure_scripts.rs:84`, `src/agent/miner_distributor.rs:102`,
     `src/agent/simulation_monitor.rs:133`, `src/orchestrator.rs:282`.

8. **Replace `grep -oP`, `bc`, with portable equivalents** in non-critical
   scripts (F-SH-2, F-SH-5):
   - `scripts/check_sim.sh:253, 798` — `grep -oE` + `awk`/`sed`.
   - `scripts/check_sim.sh:873`, `scripts/scaling_test.sh:316` — `awk
     'BEGIN{print …}'` or `python3 -c "print(…)"`.

9. **Fix the small typo in `setup.sh:281` `sudo yum update`** without `-y`
   ("update" prompts on yum without `-y` and may hang in CI). Cosmetic.

### Wave 2 — packaging portability and abstraction (2–3 person-days)

Now that the mechanical bugs are fixed, centralize the patterns so they
don't drift.

1. **`scripts/distro_pkg.sh` helper** (F-PKG-1, F-BLD-2):
   ```bash
   # Detects package manager, exposes:
   #   detect_pkg_manager   → echo apt|dnf|yum|pacman|zypper|apk
   #   pkg_install <canonical> [<canonical> …]
   #   pkg_check_installed <canonical>
   # Maintains a translation table: canonical → distro-specific name.
   ```
   Sourced by `setup.sh`, `update.sh`, and the README install snippet
   ("`./scripts/distro_pkg.sh install build-base ssl zmq …`").

2. **`scripts/sh_compat.sh` helper** for portability shims:
   - `pkg_pgrep` (pgrep with /proc fallback)
   - `pkg_readlink_f` (readlink -f with realpath/cd-pwd fallback)
   - `pkg_version_compare` (replacing `sort -V` reliance)
   - `pkg_calc` (shell math via awk)

3. **CI matrix** (F-BLD-1):
   - `.github/workflows/portability.yml` running `setup.sh --dry-run` (or a
     reduced "install deps + cargo build" subset) on:
     `ubuntu-22.04`, `ubuntu-24.04`, `fedora-latest`, `archlinux:latest`,
     `opensuse/leap:latest`. Alpine matrix entry can be wired in but
     allowed to fail (informational) until Wave 3 decides on it.

4. **Refactor `agents/base_agent.py:349`** (F-RT-4):
   - Drop `shell=True`; pass list args. Eliminates a portability *and*
     security concern (command-injection surface).

5. **Make `/tmp/monerosim_shared` configurable** (F-FS-3):
   - Read `MONEROSIM_SHARED_DIR` env var; fall back to `/tmp/monerosim_shared`.
   - Document for users on noexec-`/tmp` or hardened SELinux systems.

6. **Refresh `QUICKSTART.md`** to reflect the expanded distro list once
   F-PKG-1 + Wave 2.1 land (F-DOC-2).

### Wave 3 — structural changes (1–2 person-weeks if pursued)

These are higher-effort and require an explicit "yes, we want to support X"
decision.

1. **Alpine/musl support — feasibility study first** (F-GLIBC-3):
   - Validate Shadow builds on musl (likely needs upstream patches; check
     shadowformonero for any glibc-only assumptions).
   - Validate Monero builds on musl (Monero has had musl PRs historically;
     status today unknown — may be straightforward).
   - Once confirmed: swap `#!/bin/bash` → `#!/bin/sh` in generated agent
     wrappers (F-FS-1) where possible, ensure all bash scripts have a
     fallback or just declare `apk add bash` as a prerequisite.
   - Conditionalize `GLIBC_TUNABLES` env (F-GLIBC-1).

2. **Generic init-system abstraction**: not needed — Monerosim doesn't
   register as a system service. ✅ No work.

3. **Doas support**: low priority; deferred until requested. Helper
   abstraction in `scripts/sh_compat.sh` could expose `pkg_sudo` to detect
   sudo vs doas vs su.

4. **SELinux/AppArmor validation runs**: run smoke tests on RHEL with
   SELinux enforcing and on Ubuntu with AppArmor enforcing; address any
   policy-driven failures.

---

## 5. Out-of-scope / accepted limitations

- **RHEL / Rocky / Alma 9 (EL9 family).** Tested empirically on Rocky 9 in
  May 2026. After Wave 1+2 fixes, `setup.sh` runs to completion (Python 3.11
  auto-installed from AppStream, EPEL+CRB enabled, all build deps resolve)
  and the Monero + Shadow builds succeed. But the test simulation aborts at
  ~87% sim time with `simulation_monitor` failing to write `final_report.json`
  and Shadow exiting code 1. Suspected root cause: a Python 3.11 ABI quirk
  or SELinux denial that hits the simulation_monitor agent specifically.
  Out-of-scope unless someone wants to chase that thread; **EL10** (Rocky 10
  / RHEL 10 / Alma 10) does not exhibit the issue and is the recommended
  RHEL-family target. The setup.sh changes that auto-handle EL9
  prerequisites (Python 3.11 install, EPEL+CRB enable) remain in place
  and benefit anyone who tries to push EL9 support further.
- **Alpine/musl as a primary target.** Listed in Wave 3 but pursued only
  on demand. Cost: validating two large external codebases (Shadow +
  Monero) build on musl. Worth doing only if there's a concrete user need.
- **Non-Linux Unix (BSD, macOS).** Shadow itself is Linux-only; the project
  inherits that constraint. Out of scope.
- **Windows.** Same. The Rust crate would mostly compile, but the agent
  framework, `/proc` reads, fcntl locking, and Shadow itself preclude it.
- **Doas / non-`sudo` privilege escalation.** Not addressed in Wave 1/2;
  add to Wave 3 if requested.
- **Containerization (Docker/Podman).** Explicitly off the table per the
  audit charter; native portability is the goal.
- **GUI / `qt5-linguist` strict requirement.** Used in Monero's wallet
  GUI build but not in the headless `monerod` + `wallet-rpc` path that
  Monerosim actually uses. Could be removed from `setup.sh:281` entirely
  (not just renamed) — verify with the Monero build.

---

## 6. Open questions

1. **Are RHEL/Fedora/Rocky/Alma official targets?** The yum branch in
   `setup.sh` exists but contains broken package names that suggest it's
   never been smoke-tested. If yes → Wave 1 is mandatory. If no →
   either remove the yum branch entirely (simpler) or fix it.
2. **Are openSUSE and Alpine targets we want to claim?** Currently neither
   is detected; both are easy to add detection for, but Alpine (musl)
   has structural cost (Wave 3).
3. **Do the sibling repos (`shadowformonero`, `monero`) compile cleanly on
   Fedora/Arch as-is?** The `setup.sh` branches install the right (mostly)
   deps, but neither sibling has been tested on those distros to our
   knowledge. Validate as part of the CI matrix in Wave 2.3.
4. **Is `qt5-linguist` actually needed for the binaries Monerosim uses?**
   We build only `daemon` and `wallet_rpc_server` by default — neither
   requires the GUI translation tools. Likely removable from the apt/yum/
   pacman lists, simplifying portability.
5. **Should we adopt a single source of truth for system deps?** A
   `deps/system-deps.yaml` mapping canonical names → per-distro names,
   driving both `setup.sh` and the README install instructions, would make
   future drift impossible.

### Audit / planning files encountered and skipped

Per the audit charter, these were flagged but not ingested:

- `AUDIT.md` (root) — prior audit, skipped.
- `CHANGELOG.md` (root) — change history, skipped.
- `TODO/` (directory) — task notes, skipped.
- `docs/20260503_refactor_plan.md` — referenced in `git status` as deleted.
- `.claude/` (project Claude config) — skipped per charter.
- `attic/` (per `attic/README.md` an "ad-hoc / unmaintained" folder) —
  skipped; if this directory is to be audited later, expect mostly
  orphaned scripts that don't affect production portability.
- `archived_runs/`, `shadow_output/`, `target/`, `venv/`, `__pycache__/`,
  `.pytest_cache/`, `sibling_repos/` (Shadow + Monero source trees) —
  excluded as build/runtime output or external code outside this audit's
  scope.

`README.md`, `QUICKSTART.md`, and `CLAUDE.md` were read for project context
only; doc/code discrepancies they revealed are themselves findings (F-DOC-1,
F-DOC-2, F-USR-1).
