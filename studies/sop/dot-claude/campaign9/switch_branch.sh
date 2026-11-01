#!/bin/bash
# switch_branch.sh <box>...: on an IDLE lane box (no sim running), clear HALT,
# drop the two untracked spec copies (identical to the committed ones), fetch
# and check out sop-research.
for h in "$@"; do
  echo "######## $h ########"
  ssh -o BatchMode=yes $h 'cd ~/monerosim || exit 1
    if pgrep -f "[s]hadow --parallelism|[s]elfish_matrix" >/dev/null; then echo "sim running; not switching"; exit 1; fi
    rm -f .claude/campaign9/HALT
    rm -f test_configs/matrix/sop_v4_o5_alpha_72h.yaml test_configs/matrix/sop_v4_o5_noown_72h.yaml
    git fetch -q origin && git checkout -q sop-research && git status -sb | head -1 && git log --oneline -1
    ls test_configs/matrix/sop_v4_o5_alpha_72h.yaml test_configs/matrix/sop_v4_o5_noown_72h.yaml docs/20261021_research_direction_idea_SoP.txt >/dev/null && echo "specs + note present from branch"'
done
