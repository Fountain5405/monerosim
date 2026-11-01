#!/bin/bash
# Stop campaign 3: the driver, the matrix runners, every run_sim.sh and Shadow it started.
pkill -TERM -f 'run_campaign3.sh|run_stage2.sh' ; pkill -TERM -f 'selfish_matrix.py test_configs/matrix/(pop_exact2_h10|pop_exact_h10|sop2_h10_ctl|pop_exact_mid)'
sleep 2; pkill -TERM -f 'run_sim.sh --config .*(pop_exact2_h10|pop_exact_h10|sop2_h10_ctl|pop_exact_mid)'; sleep 2; pkill -TERM -f '[/]shadow -d'
sleep 5; pgrep -fa 'selfish_matrix|run_sim.sh|shadow -d' || echo "nothing left"
# added 2026-09-27: det-tie mid control and the relay matrices
pkill -TERM -f 'run_stage[23].sh|run_relay_matri[x].sh'; pkill -TERM -f 'selfish_matrix.py test_configs/matrix/(pop_dettie_mi[d]|pop_exact_rela[y])'
sleep 2; pkill -TERM -f 'run_sim.sh --config .*(pop_dettie_mi[d]|pop_exact_rela[y])'; sleep 2; pkill -TERM -f '[/]shadow -d'
# added 2026-09-27 13:xxZ: stranding re-run
pkill -TERM -f 'run_fbridg[e].sh'; pkill -TERM -f 'selfish_matrix.py test_configs/matrix/.*_fbridg[e]'
sleep 2; pkill -TERM -f 'run_sim.sh --config .*_fbridg[e]'; sleep 2; pkill -TERM -f '[/]shadow -d'
