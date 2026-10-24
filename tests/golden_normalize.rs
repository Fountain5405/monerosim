//! The path normalizer shared by the golden-file tests (`tests/common/mod.rs`).
//! A golden must not depend on where the repo is checked out or on which
//! Python the venv was built with.

mod common;

use common::normalize_paths;

#[test]
fn venv_python_version_is_masked() {
    // python3.N from a venv, bare python3 when the checkout has no venv.
    let yaml = "a: /repo/venv/lib/python3.10/site-packages\n\
                b: /repo/venv/lib/python3.12/site-packages\n\
                c: /repo/venv/lib/python3/site-packages\n";
    assert_eq!(
        normalize_paths(yaml, "/repo", "/home/u"),
        "a: REPO_ROOT/venv/lib/python3.X/site-packages\n\
         b: REPO_ROOT/venv/lib/python3.X/site-packages\n\
         c: REPO_ROOT/venv/lib/python3.X/site-packages\n"
    );
}

#[test]
fn repo_checked_out_under_tmp_is_still_repo_root() {
    // A worktree in a scratch dir: the tempdir pattern must not eat its prefix.
    let yaml = "script: /tmp/scratch-1/monerosim/agents/run.py\n\
                out: /tmp/.tmpAbC123/shadow_agents.yaml\n";
    assert_eq!(
        normalize_paths(yaml, "/tmp/scratch-1/monerosim", "/home/u"),
        "script: REPO_ROOT/agents/run.py\n\
         out: TMPDIR/shadow_agents.yaml\n"
    );
}

#[test]
fn home_is_masked() {
    assert_eq!(
        normalize_paths("daemon: /home/u/.monerosim/bin/monerod\n", "/repo", "/home/u"),
        "daemon: HOME/.monerosim/bin/monerod\n"
    );
}
