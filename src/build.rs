use crate::config::{Config, NodeType};
use color_eyre::Result;
use color_eyre::eyre::WrapErr;
use log::{info, warn};
use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;
use num_cpus;

/// Directory where all builds will be placed
pub const BUILDS_DIR: &str = "builds";

/// Path to the local monero source (relative to workspace root)
pub const MONERO_SRC: &str = "../monero";

/// Represents the build plan for a node type
#[derive(Debug)]
pub struct BuildPlan {
    pub name: String,
    pub build_dir: PathBuf,
    pub base_commit: Option<String>,
    pub patches: Option<Vec<String>>,
    pub base: Option<String>,
    pub prs: Option<Vec<u32>>,
}

/// Prepare build directories and log the build plan for each node type
pub fn prepare_builds(config: &Config) -> Result<HashMap<String, BuildPlan>> {
    let mut plans = HashMap::new();
    fs::create_dir_all(BUILDS_DIR)?;
    for node in &config.monero.nodes {
        let build_dir = Path::new(BUILDS_DIR).join(&node.name);
        fs::create_dir_all(&build_dir)?;
        let plan = BuildPlan {
            name: node.name.clone(),
            build_dir: build_dir.clone(),
            base_commit: node.base_commit.clone(),
            patches: node.patches.clone(),
            base: node.base.clone(),
            prs: node.prs.clone(),
        };
        info!("Planned build for node type '{}': {:?}", node.name, plan);
        plans.insert(node.name.clone(), plan);
    }
    Ok(plans)
}

/// For each build plan, copy/clone the source and checkout the correct commit
pub fn build_monero_binaries(build_plans: &HashMap<String, BuildPlan>) -> Result<()> {
    for (name, plan) in build_plans {
        // Step 1: Clone the monero source to the build dir if not already present
        let src_dir = Path::new(MONERO_SRC);
        let build_dir = &plan.build_dir;
        let monero_dir = build_dir.join("monero");
        if !monero_dir.exists() {
            info!("Cloning Shadow-compatible monero source to {:?} for node type '{}'...", monero_dir, name);
            let shadow_fork_path = Path::new("../monero-shadow").canonicalize()
                .map_err(|e| color_eyre::eyre::eyre!("Failed to resolve monero-shadow path: {}", e))?;
            let status = Command::new("git")
                .args(["clone", shadow_fork_path.to_str().unwrap(), monero_dir.to_str().unwrap()])
                .status()?;
            if !status.success() {
                return Err(color_eyre::eyre::eyre!("Failed to clone Shadow-compatible monero source for node type '{}'", name));
            }
            
            // Switch to shadow-complete branch (contains all Shadow modifications)
            info!("Switching to shadow-complete branch for node type '{}'...", name);
            let branch_status = Command::new("git")
                .arg("-C").arg(&monero_dir)
                .args(["checkout", "shadow-complete"])
                .status()?;
            if !branch_status.success() {
                return Err(color_eyre::eyre::eyre!("Failed to checkout shadow-complete branch for node type '{}'", name));
            }
        } else {
            info!("Monero source already present for node type '{}' at {:?}", name, monero_dir);
        }
        // Always fetch all tags and branches before checkout
        let fetch_tags_status = Command::new("git")
            .arg("-C").arg(&monero_dir)
            .args(["fetch", "--all", "--tags"])
            .status()?;
        if !fetch_tags_status.success() {
            return Err(color_eyre::eyre::eyre!("Failed to fetch tags for node type '{}'", name));
        }

        // Step 2: Checkout the correct commit/tag if specified
        if let Some(ref commit) = plan.base_commit {
            info!("Checking out commit/tag '{}' for node type '{}'...", commit, name);
            let status = Command::new("git")
                .arg("-C").arg(&monero_dir)
                .args(["checkout", commit])
                .status()?;
            if !status.success() {
                return Err(color_eyre::eyre::eyre!("Failed to checkout commit '{}' for node type '{}'", commit, name));
            }
        }

        // Step 3: Apply patches if specified
        let mut patch_applied = false;
        if let Some(ref patches) = plan.patches {
            for patch in patches {
                let patch_path = std::fs::canonicalize(patch)
                    .map_err(|e| color_eyre::eyre::eyre!("Failed to resolve patch path '{}': {}", patch, e))?;
                // Check if patch file is empty
                let metadata = std::fs::metadata(&patch_path)?;
                if metadata.len() == 0 {
                    log::warn!("Patch '{}' is empty, skipping application for node type '{}'", patch_path.display(), name);
                    continue;
                }
                info!("Applying patch '{}' for node type '{}'...", patch_path.display(), name);
                let status = Command::new("git")
                    .arg("-C").arg(&monero_dir)
                    .args(["apply", patch_path.to_str().unwrap()])
                    .status()?;
                if !status.success() {
                    return Err(color_eyre::eyre::eyre!("Failed to apply patch '{}' for node type '{}'", patch_path.display(), name));
                }
                patch_applied = true;
            }
        }
        // Commit patch if applied
        if patch_applied {
            info!("Committing applied patches for node type '{}'...", name);
            let add_status = Command::new("git")
                .arg("-C").arg(&monero_dir)
                .args(["add", "."])
                .status()?;
            if !add_status.success() {
                return Err(color_eyre::eyre::eyre!("Failed to git add after patch for node type '{}'", name));
            }
            let commit_status = Command::new("git")
                .arg("-C").arg(&monero_dir)
                .args(["commit", "-m", "Apply patches"])
                .status()?;
            if !commit_status.success() {
                return Err(color_eyre::eyre::eyre!("Failed to git commit after patch for node type '{}'", name));
            }
        }

        // Step 4: Merge PRs if specified
        if let Some(ref prs) = plan.prs {
            for pr in prs {
                let branch_name = format!("pr-{}", pr);
                info!("Fetching PR #{} for node type '{}'...", pr, name);
                let fetch_status = Command::new("git")
                    .arg("-C").arg(&monero_dir)
                    .args(["fetch", "origin", &format!("pull/{}/head:{}", pr, branch_name)])
                    .status()?;
                if !fetch_status.success() {
                    return Err(color_eyre::eyre::eyre!("Failed to fetch PR #{} for node type '{}'", pr, name));
                }
                info!("Merging PR #{} for node type '{}'...", pr, name);
                let merge_status = Command::new("git")
                    .arg("-C").arg(&monero_dir)
                    .args(["merge", "-m", &format!("Merge PR #{}", pr), &branch_name])
                    .status()?;
                if !merge_status.success() {
                    return Err(color_eyre::eyre::eyre!("Failed to merge PR #{} for node type '{}'", pr, name));
                }
            }
        }

        // Ensure all submodules are initialized and up-to-date after patching and PRs
        let submodule_status = Command::new("git")
            .args(["submodule", "update", "--init", "--force"])
            .current_dir(&monero_dir)
            .status()?;
        if !submodule_status.success() {
            return Err(color_eyre::eyre::eyre!("Failed to update submodules for node type '{}' after patching/PRs", name));
        }

        // Step 5: Build the monerod binary with Shadow compatibility
        info!("Building Shadow-compatible monerod for node type '{}'...", name);
        let jobs = num_cpus::get().to_string();
        
        // First, configure with Shadow compatibility flag
        let cmake_status = Command::new("cmake")
            .args(["-DSHADOW_BUILD=ON", "-DCMAKE_BUILD_TYPE=Release", "."])
            .current_dir(&monero_dir)
            .status()?;
        if !cmake_status.success() {
            return Err(color_eyre::eyre::eyre!("Failed to configure CMake with Shadow compatibility for node type '{}'", name));
        }
        
        // Then build with make
        let make_status = Command::new("make")
            .args([&format!("-j{}", jobs)])
            .current_dir(&monero_dir)
            .status()?;
        if !make_status.success() {
            return Err(color_eyre::eyre::eyre!("Failed to build Shadow-compatible monerod for node type '{}'", name));
        }
    }
    Ok(())
} 