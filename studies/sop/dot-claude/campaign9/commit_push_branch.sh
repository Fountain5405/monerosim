#!/bin/bash
# commit_push_branch.sh: commit the owner's three untracked files on sop-research
# and push via tr's checkout (gh credential helper), then verify sync.
set -eu
cd /home/selfishmining/monerosim
BR=sop-research
TRREPO=/scratch/monerosim_dev/monerosim
[ "$(git rev-parse --abbrev-ref HEAD)" = "$BR" ] || { echo "not on $BR"; exit 1; }
git add review_report.md docs/20261021_research_direction_idea_SoP.txt data/campaign8/analysis_out/modelb_sweep_rev20261020_noown.md
git commit -q -m "$(cat <<'EOF'
SoP: independent review of campaign 7, MDP research-direction note, model-B noown sweep

review_report.md: the independent review of the dev-branch SoP (MRL #146)
campaign 7 at 7d4e56da, code and logs only, no simulation run.
docs/20261021_research_direction_idea_SoP.txt: the suggestion to put SoP
into an MDP, count the states, and fall back to RL if too many.
data/campaign8/analysis_out/modelb_sweep_rev20261020_noown.md: race-model
sweep output for rule version 20261020_noown (2000 d, seed 1).

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
EOF
)"
NEW=$(git rev-parse --short HEAD); echo "committed $NEW"
git push -q "tr:$TRREPO" "$BR:$BR"
ssh -o BatchMode=yes tr "cd $TRREPO && git -c credential.helper='!gh auth git-credential' push -q origin $BR && echo tr pushed origin/$BR=\$(git rev-parse --short origin/$BR)"
git fetch -q origin
echo "--- sync ---"; git status -sb | head -1; git status --porcelain | sed 's/^/  /'; [ -z "$(git status --porcelain)" ] && echo "  working tree clean"
echo "local $BR=$(git rev-parse --short $BR) origin/$BR=$(git rev-parse --short origin/$BR)"
