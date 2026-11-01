#!/bin/bash
# push_files.sh "<commit message>" <file>...: commit the files on sop-research
# and push via tr's checkout (gh credential helper). Verifies sync afterwards.
set -eu
cd /home/selfishmining/monerosim
msg=$1; shift
[ "$(git rev-parse --abbrev-ref HEAD)" = "sop-research" ] || { echo "not on sop-research"; exit 1; }
git add "$@"
git commit -q -m "$(printf '%s\n\nCo-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>\n' "$msg")"
echo "committed $(git rev-parse --short HEAD)"
git push -q tr:/scratch/monerosim_dev/monerosim sop-research:sop-research
ssh -o BatchMode=yes tr "cd /scratch/monerosim_dev/monerosim && git -c credential.helper='!gh auth git-credential' push -q origin sop-research && echo origin/sop-research=\$(git rev-parse --short origin/sop-research)"
git fetch -q origin; git status -sb | head -1
