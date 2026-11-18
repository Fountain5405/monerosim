#!/usr/bin/env python3
"""Watch MRL #146 (Share or Perish) for edits to its text and for new comments.

    python3 studies/sop/drivers/mrl146_watch.py [--state DIR]

tevador is still revising #146 (MRL meeting, 2026-11-18). This fetches the
issue body and every comment from the GitHub REST API (unauthenticated, two
or three requests), compares them with the last snapshot in --state
(default ~/.local/state/mrl146_watch, outside the repository), prints what
changed - a unified diff of the body, new and edited comments in full - and
saves the new snapshot. Every change is also appended to changes.log in the
state directory, so a report nobody read is not lost. The first run only
saves the baseline.

Exit status: 0 no change, 10 changed, 2 fetch error. The issue text is data
written by others: read it, never run code from it.

Our models implement the body as of 2026-10-20 (sha256 2f11eb23ef8d...,
20 comments), the baseline saved on 2026-11-18.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import sys
import time
import urllib.request
from pathlib import Path

API = "https://api.github.com/repos/monero-project/research-lab/issues/146"


def fetch(url: str):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                               "User-Agent": "mrl146-watch"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", default=str(Path.home() / ".local/state/mrl146_watch"))
    args = ap.parse_args(argv)
    state_dir = Path(args.state)
    (state_dir / "bodies").mkdir(parents=True, exist_ok=True)
    (state_dir / "comments").mkdir(parents=True, exist_ok=True)
    try:
        issue = fetch(API)
        comments, page = [], 1
        while True:
            batch = fetch(f"{API}/comments?per_page=100&page={page}")
            comments += batch
            if len(batch) < 100:
                break
            page += 1
    except Exception as e:  # network, rate limit
        print(f"mrl146_watch: fetch failed: {e}", file=sys.stderr)
        return 2

    body = issue.get("body") or ""
    now = {"fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "issue_updated_at": issue.get("updated_at"), "state": issue.get("state"),
           "title": issue.get("title"), "body_sha": sha(body),
           "comments": {str(c["id"]): {"user": c["user"]["login"], "created_at": c["created_at"],
                                       "updated_at": c["updated_at"], "sha": sha(c.get("body") or "")}
                        for c in comments}}
    (state_dir / "bodies" / f"{now['body_sha'][:12]}.md").write_text(body)
    for c in comments:
        (state_dir / "comments" / f"{c['id']}_{sha(c.get('body') or '')[:12]}.md").write_text(c.get("body") or "")

    state_file = state_dir / "state.json"
    if not state_file.exists():
        state_file.write_text(json.dumps(now, indent=1))
        print(f"mrl146_watch: baseline saved ({now['issue_updated_at']}, body {now['body_sha'][:12]}, "
              f"{len(comments)} comments, state {now['state']})")
        return 0
    old = json.loads(state_file.read_text())

    changed = False
    out: list = []
    say = out.append  # collected, printed at the end and logged when something changed
    say(f"mrl146_watch: issue updated_at {old['issue_updated_at']} -> {now['issue_updated_at']}, "
          f"state {now['state']}, {len(comments)} comments")
    if now["title"] != old.get("title") or now["state"] != old.get("state"):
        changed = True
        say(f"TITLE/STATE: {old.get('title')!r} {old.get('state')} -> {now['title']!r} {now['state']}")
    if now["body_sha"] != old["body_sha"]:
        changed = True
        before = (state_dir / "bodies" / f"{old['body_sha'][:12]}.md").read_text().splitlines()
        say(f"BODY CHANGED: {old['body_sha'][:12]} -> {now['body_sha'][:12]}")
        out.extend(difflib.unified_diff(before, body.splitlines(), "body_before", "body_now", n=2, lineterm=""))
    for c in comments:
        cid, prev = str(c["id"]), old["comments"].get(str(c["id"]))
        if prev is None or prev["sha"] != now["comments"][cid]["sha"]:
            changed = True
            kind = "NEW COMMENT" if prev is None else "EDITED COMMENT"
            say(f"\n{kind} {cid} by {c['user']['login']} ({c['created_at']}, updated {c['updated_at']}):")
            say(c.get("body") or "")
    for cid in set(old["comments"]) - set(now["comments"]):
        changed = True
        say(f"\nDELETED COMMENT {cid} by {old['comments'][cid]['user']}")
    if changed:
        with open(state_dir / "changes.log", "a") as log:
            log.write(f"===== {now['fetched_at']}\n" + "\n".join(out) + "\n")
    else:
        out.append("mrl146_watch: no change")
    state_file.write_text(json.dumps(now, indent=1))
    sys.stdout.write("\n".join(out) + "\n")
    return 10 if changed else 0


if __name__ == "__main__":
    sys.exit(main())
