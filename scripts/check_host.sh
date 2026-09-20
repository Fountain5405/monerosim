#!/usr/bin/env bash
# monerosim host preflight - READ ONLY. Installs nothing, changes nothing, no sudo.
GO=0; FIX=0
p(){ printf '  \033[0;32mPASS\033[0m  %s\n' "$1"; }
f(){ printf '  \033[0;31mFAIL\033[0m  %s\n' "$1"; GO=1; }
w(){ printf '  \033[1;33mFIX \033[0m  %s\n' "$1"; FIX=1; }
i(){ printf '  ----  %s\n' "$1"; }
ge(){ [ "$(printf '%s\n%s\n' "$2" "$1" | sort -V | head -n1)" = "$2" ]; }

echo; echo "=== monerosim host check: $(hostname) ==="
. /etc/os-release 2>/dev/null
i "OS: ${PRETTY_NAME:-unknown}"
i "kernel: $(uname -r)"
case "${ID:-}:${VERSION_ID:-}" in
  rhel:9*|centos:9*|rocky:9*|almalinux:9*) f "RHEL/Rocky/Alma 9 is explicitly unsupported (PORTABILITY.md)";;
esac

echo; echo "-- hard blockers (cannot be fixed without a reboot / new host) --"
K=$(uname -r | cut -d- -f1 | cut -d. -f1,2)
if ge "$K" 5.10; then p "kernel $(uname -r) >= 5.10"
else f "kernel $(uname -r) < 5.10 - Shadow needs PIDFD_NONBLOCK (Linux 5.10+)"; fi

if command -v python3 >/dev/null 2>&1; then
  if python3 - <<'PY' >/dev/null 2>&1
import ctypes, os, sys
l = ctypes.CDLL("libc.so.6", use_errno=True); ctypes.set_errno(0)
fd = l.syscall(434, ctypes.c_int(os.getpid()), ctypes.c_uint(0o4000))
sys.exit(0) if fd >= 0 else sys.exit(1)
PY
  then p "pidfd_open(PIDFD_NONBLOCK) works - the exact call Shadow makes"
  else f "pidfd_open(PIDFD_NONBLOCK) rejected - every simulation will SIGABRT (exit 134)"; fi
else i "pidfd runtime test skipped (no python3 yet)"; fi

echo; echo "-- fixable before setup (no reboot) --"
PY310=""
for c in python3 python3.13 python3.12 python3.11 python3.10; do
  if command -v $c >/dev/null 2>&1 && $c -c 'import sys;sys.exit(0 if sys.version_info>=(3,10) else 1)' 2>/dev/null; then PY310=$c; break; fi
done
if [ -n "$PY310" ]; then p "python $($PY310 -V 2>&1 | awk '{print $2}') ($PY310) >= 3.10"
else w "no python >= 3.10  ->  install python3.11, or: uv python install 3.11"; fi

if command -v cmake >/dev/null 2>&1; then
  CV=$(cmake --version | head -1 | awk '{print $3}')
  if ge "$CV" 3.18.4; then
    p "cmake $CV >= 3.18.4"
    if ge "$CV" 4.0.0; then i "cmake is 4.x - Monero declares a 3.5 minimum; a 3.x cmake is safer"; fi
  else w "cmake $CV < 3.18.4  ->  uv tool install 'cmake<4'  (or the Kitware APT repo)"; fi
else w "cmake missing  ->  package manager, or: uv tool install 'cmake<4'"; fi

CARGO=""
if command -v cargo >/dev/null 2>&1; then CARGO=cargo
elif [ -x "$HOME/.cargo/bin/cargo" ]; then CARGO="$HOME/.cargo/bin/cargo"; i "cargo found at ~/.cargo/bin but NOT on PATH - export PATH=\"\$HOME/.cargo/bin:\$PATH\""; fi
if [ -n "$CARGO" ]; then
  RV=$("$CARGO" --version | awk '{print $2}')
  if ge "$RV" 1.82.0; then p "cargo $RV >= 1.82"
  else i "cargo $RV < 1.82 - setup.sh rustup-updates it (no sudo)"; fi
else i "cargo absent - setup.sh installs Rust itself (no sudo)"; fi

MISS=""
for t in git gcc g++ make pkg-config curl clang; do command -v $t >/dev/null 2>&1 || MISS="$MISS $t"; done
pkg-config --exists glib-2.0 2>/dev/null || MISS="$MISS libglib2.0-dev"
if [ -z "$MISS" ]; then p "build prerequisites present"
else i "setup.sh will install (needs sudo):$MISS"; fi

echo; echo "-- capacity --"
C=$(nproc 2>/dev/null || echo 0)
R=$(free -g 2>/dev/null | awk '/^Mem:/{print $2}'); R=${R:-0}
D=$(df -BG --output=avail "$HOME" 2>/dev/null | tail -1 | tr -dc '0-9'); D=${D:-0}
if   [ "$C" -ge 8 ]; then p "$C cores"
elif [ "$C" -ge 4 ]; then i "$C cores (min 4, 8+ recommended)"
else f "$C cores (below the 4-core minimum)"; fi
if   [ "$R" -ge 16 ]; then p "$R GB RAM"
elif [ "$R" -ge 8 ];  then i "$R GB RAM (quickstart only; 16+ for real work, 32+ for 1000＋ agents)"
else f "$R GB RAM (below the 8 GB minimum)"; fi
if   [ "$D" -ge 50 ]; then p "$D GB free in \$HOME"
elif [ "$D" -ge 30 ]; then i "$D GB free (min 30, 50+ recommended)"
else f "$D GB free (below the 30 GB minimum)"; fi

echo; echo "=================================================="
if   [ $GO  -ne 0 ]; then printf ' \033[0;31mNO-GO\033[0m  a hard blocker above must be fixed first.\n'
elif [ $FIX -ne 0 ]; then printf ' \033[1;33mGO, after the FIX items\033[0m  (no reboot needed).\n'
else                      printf ' \033[0;32mGO\033[0m  this host should install and run monerosim.\n'; fi
echo "=================================================="; echo
