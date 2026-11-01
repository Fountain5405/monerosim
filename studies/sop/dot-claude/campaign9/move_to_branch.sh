#!/bin/bash
# move_to_branch.sh (2026-10-24, owner: "move to a branch", "call the branch
# sop-research"): the five SoP commits since 5f04b397 (b5bc1a02 23162f3a
# 185cd4c0 4a68cd7a ca97daf9) go to sop-research; origin/main goes back to
# 5f04b397. This box has no GitHub login, so the pushes run from tr's checkout
# (gh logged in as the owner) with gh as the credential helper. Order: push
# the branch FIRST (nothing can be lost), then force-with-lease main.
# Undo: on tr, git -c credential.helper='!gh auth git-credential' push origin sop-research:main
set -eu
cd /home/selfishmining/monerosim
BR=sop-research
BASE=5f04b397
TIP=ca97daf9
OLD_ORIGIN=4a68cd7a
TRREPO=/scratch/monerosim_dev/monerosim
GH="git -c credential.helper=!gh\ auth\ git-credential"
if git show-ref -q --verify refs/heads/feat/sop-o5-attacker; then git branch -m feat/sop-o5-attacker "$BR"; fi
git show-ref -q --verify "refs/heads/$BR" || git branch "$BR" "$TIP"
[ "$(git rev-parse $BR)" = "$(git rev-parse $TIP)" ] || { echo "$BR is not at $TIP; abort"; exit 1; }
[ -z "$(git status --porcelain | grep -v '^??')" ] || { echo "tracked changes present; abort"; exit 1; }
git fetch -q origin
[ "$(git rev-parse origin/main)" = "$(git rev-parse $OLD_ORIGIN)" ] || { echo "origin/main is not $OLD_ORIGIN; abort"; exit 1; }
echo "--- commits moving to $BR ---"; git log --oneline $BASE..$TIP
echo "--- 1. branch to tr's checkout ---"
git push -q "tr:$TRREPO" "$BR:$BR"
echo "--- 2. tr pushes the branch to origin ---"
ssh -o BatchMode=yes tr "cd $TRREPO && git -c credential.helper='!gh auth git-credential' push -q -u origin $BR && echo pushed: \$(git rev-parse --short origin/$BR)"
echo "--- 3. tr resets origin/main to $BASE (lease on $OLD_ORIGIN) ---"
ssh -o BatchMode=yes tr "cd $TRREPO && git -c credential.helper='!gh auth git-credential' push --force-with-lease=main:$OLD_ORIGIN origin $BASE:main && git fetch -q origin && echo origin/main now: \$(git rev-parse --short origin/main); echo tr local main still: \$(git rev-parse --short main) '(owner: git branch -f main origin/main when off main)'"
echo "--- 4. this box ---"
git fetch -q origin
git checkout -q "$BR"
git branch -q -u "origin/$BR" "$BR"
git branch -f main origin/main
git branch -vv | sed 's/^/  /'
echo "origin/main = $(git rev-parse --short origin/main)   origin/$BR = $(git rev-parse --short origin/$BR)"
