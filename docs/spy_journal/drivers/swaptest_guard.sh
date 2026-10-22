#!/bin/bash
# Logs the capped run every 20 s; stops Shadow only if the box (not the cgroup) runs low.
S=/tmp/claude-1002/-home-lever65-monerosim/df57b8d8-00c1-4e9b-8f85-c70f598c44e3/scratchpad
SP=714451
R=$(cat $S/swaptest.rundir)
CG=/sys/fs/cgroup/user.slice/user-1002.slice/user@1002.service/app.slice/x0-swaptest.scope
L=$S/swaptest_mem.csv
echo "time,epoch,sim_s,cg_mem_mb,cg_swap_mb,cg_anon_mb,cg_file_mb,pgmajfault,pswpin_pg,psi_some10,psi_full10,psi_full_total_us,avail_mb,swap_used_mb,disk_gb" > $L
while kill -0 $SP 2>/dev/null; do
  sim=$(tail -1 $R/memory_samples.csv | cut -d, -f3)
  mem=$(( $(cat $CG/memory.current) / 1048576 )); sw=$(( $(cat $CG/memory.swap.current) / 1048576 ))
  anon=$(awk '$1=="anon"{print int($2/1048576)}' $CG/memory.stat); file=$(awk '$1=="file"{print int($2/1048576)}' $CG/memory.stat)
  maj=$(awk '$1=="pgmajfault"{print $2}' $CG/memory.stat); swin=$(awk '$1=="pswpin"{print $2}' /proc/vmstat)
  s10=$(awk '/^some/{split($2,a,"=");print a[2]}' $CG/memory.pressure); f10=$(awk '/^full/{split($2,a,"=");print a[2]}' $CG/memory.pressure)
  ft=$(awk '/^full/{split($5,a,"=");print a[2]}' $CG/memory.pressure)
  a=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo)
  su=$(awk '/SwapTotal/{t=$2}/SwapFree/{f=$2}END{print int((t-f)/1024)}' /proc/meminfo)
  dk=$(df -BG --output=avail / | tail -1 | tr -dc 0-9)
  echo "$(date +%H:%M:%S),$(date +%s),$sim,$mem,$sw,$anon,$file,$maj,$swin,$s10,$f10,$ft,$a,$su,$dk" >> $L
  if [ "$a" -lt 1500 ] || [ "$dk" -lt 30 ] || [ "$su" -gt 26000 ]; then
    echo "STOPPING: avail_mb=$a disk_gb=$dk swap_used_mb=$su"; kill -TERM $SP; break
  fi
  sleep 20
done
echo "shadow exited"
