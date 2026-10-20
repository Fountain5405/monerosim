#!/usr/bin/env python3
"""Run a command with kernel same-page merging (KSM) opted in.

Sets prctl(PR_SET_MEMORY_MERGE, 1) on this process, then execs the command. The
setting survives exec and fork, so `ksm_exec.py ./run_sim.sh ...` makes Shadow and
every process it starts eligible for merging. Unprivileged. Has no effect until
root enables KSM (off by default, resets at every reboot):

    sudo sh -c 'echo 20000 > /sys/kernel/mm/ksm/pages_to_scan && echo 20 > /sys/kernel/mm/ksm/sleep_millisecs && echo 1 > /sys/kernel/mm/ksm/run'

(scripts/ksm_check.sh checks the scan rate without root.)

Measured effect and tradeoffs: docs/PERFORMANCE_AND_SCALE.md, "KSM".
"""
import ctypes
import os
import sys

PR_SET_MEMORY_MERGE = 67

libc = ctypes.CDLL(None, use_errno=True)
if libc.prctl(PR_SET_MEMORY_MERGE, 1, 0, 0, 0) != 0:
    sys.exit(f"ksm_exec: prctl(PR_SET_MEMORY_MERGE) failed: {os.strerror(ctypes.get_errno())}")
os.execvp(sys.argv[1], sys.argv[1:])
