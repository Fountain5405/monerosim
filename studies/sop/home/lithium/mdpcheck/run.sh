#!/bin/bash
# Runs ON lithium: the solver cross-check queues, one process each, JSON lines to ~/mdpcheck/results_<q>.jsonl.
# Single-threaded, nice 15, 8 GB address-space cap (the stressnet node keeps its headroom).
cd ~/mdpcheck/scripts
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
ulimit -v 8000000
q=$1; out=~/mdpcheck/results_$q.jsonl
run() { echo "$(date -u +%FT%TZ) start $*" >> ~/mdpcheck/run_$q.log
        nice -n 15 ../venv/bin/python -W ignore sop_mdp_crosscheck.py "$@" >> $out 2>> ~/mdpcheck/run_$q.log
        rc=$?    # before any $(...) resets it (the first version logged exit 0 for a crash)
        echo "$(date -u +%FT%TZ) exit $rc $*" >> ~/mdpcheck/run_$q.log; }
case $q in
  btc2)
    for a in 0.4 0.425 0.45 0.475; do run btc --alpha $a --gamma 0 --T 95 --bound lower --T-policy 400; done
    for a in 0.3333333333333333 0.35 0.375 0.4; do run btc --alpha $a --gamma 0.5 --T-policy 400 --policies-only; done ;;
  btc_bigT)
    # lower bounds at larger T must stay below a valid upper bound at T 95 (0.675766 at 0.45, 0.837810 at 0.475)
    for a in 0.45 0.475; do run btc --alpha $a --gamma 0 --T 200 --bound lower --T-policy 0 --no-library; done
    run btc --alpha 0.475 --gamma 0 --T 300 --bound lower --T-policy 0 --no-library ;;
esac
echo "$(date -u +%FT%TZ) queue $q done" >> ~/mdpcheck/run_$q.log
