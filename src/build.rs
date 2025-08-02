use crate::config_v2::Config;
use color_eyre::Result;
use log::info;
use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;
use num_cpus;

/// Directory where all builds will be placed
pub const BUILDS_DIR: &str = "builds";

/// Represents the build plan for a node type
#[derive(Debug)]
pub struct BuildPlan {
    pub name: String,
    pub build_dir: PathBuf,
}

/// Prepare build directories and log the build plan
pub fn prepare_builds(config: &Config) -> Result<HashMap<String, BuildPlan>> {
    let mut plans = HashMap::new();
    fs::create_dir_all(BUILDS_DIR)?;
    
    // Since all nodes use the same binary, we only need one build (A)
    let build_dir = Path::new(BUILDS_DIR).join("A");
    fs::create_dir_all(&build_dir)?;
    let plan = BuildPlan {
        name: "A".to_string(),
        build_dir: build_dir.clone(),
    };
    info!("Planned build for nodes: {:?}", plan);
    plans.insert("A".to_string(), plan);
    
    Ok(plans)
}

/// Build the monero binary from the monero-shadow fork
pub fn build_monero_binaries(build_plans: &HashMap<String, BuildPlan>) -> Result<()> {
    for (name, plan) in build_plans {
        let build_dir = &plan.build_dir;
        let monero_dir = build_dir.join("monero");
        
        if !monero_dir.exists() {
            info!("Cloning Shadow-compatible monero source to {:?}...", monero_dir);
            let shadow_fork_path = Path::new("../monero-shadow").canonicalize()
                .map_err(|e| color_eyre::eyre::eyre!("Failed to resolve monero-shadow path: {}", e))?;
            let status = Command::new("git")
                .args(["clone", shadow_fork_path.to_str().unwrap(), monero_dir.to_str().unwrap()])
                .status()?;
            if !status.success() {
                return Err(color_eyre::eyre::eyre!("Failed to clone Shadow-compatible monero source"));
            }
            
            // Switch to shadow-complete branch (contains all Shadow modifications)
            info!("Switching to shadow-complete branch...");
            let branch_status = Command::new("git")
                .arg("-C").arg(&monero_dir)
                .args(["checkout", "shadow-complete"])
                .status()?;
            if !branch_status.success() {
                return Err(color_eyre::eyre::eyre!("Failed to checkout shadow-complete branch"));
            }
        } else {
            info!("Monero source already present at {:?}", monero_dir);
        }

        // Ensure all submodules are initialized and up-to-date
        let submodule_status = Command::new("git")
            .args(["submodule", "update", "--init", "--force"])
            .current_dir(&monero_dir)
            .status()?;
        if !submodule_status.success() {
            return Err(color_eyre::eyre::eyre!("Failed to update submodules"));
        }

        // Apply any available patches
        info!("Applying patches...");
        let patches_dir = Path::new("patches");
        if patches_dir.exists() {
            for entry in fs::read_dir(patches_dir)? {
                let entry = entry?;
                let path = entry.path();
                if path.is_file() && path.extension().and_then(|s| s.to_str()) == Some("patch") {
                    info!("Applying patch: {:?}", path);
                    let patch_path = path.canonicalize()?;
                    let apply_status = Command::new("git")
                        .args(["apply", "--check", patch_path.to_str().unwrap()])
                        .current_dir(&monero_dir)
                        .status()?;
                    
                    if !apply_status.success() {
                        return Err(color_eyre::eyre::eyre!("Failed to apply patch {:?} -- maybe it is already applied?", path));
                    }

                    let apply_status = Command::new("git")
                        .args(["apply", patch_path.to_str().unwrap()])
                        .current_dir(&monero_dir)
                        .status()?;

                    if !apply_status.success() {
                        return Err(color_eyre::eyre::eyre!("Failed to apply patch {:?}", path));
                    }
                }
            }
        }


        // Build the monerod binary with Shadow compatibility
        info!("Building Shadow-compatible monerod...");
        let jobs = num_cpus::get().to_string();
        
        // First, configure with Shadow compatibility flag
        let cmake_status = Command::new("cmake")
            .args(["-DSHADOW_BUILD=ON", "-DCMAKE_BUILD_TYPE=Release", "."])
            .current_dir(&monero_dir)
            .status()?;
        if !cmake_status.success() {
            return Err(color_eyre::eyre::eyre!("Failed to configure CMake with Shadow compatibility"));
        }
        
        // Then build with make
        let make_status = Command::new("make")
            .args([&format!("-j{}", jobs)])
            .current_dir(&monero_dir)
            .status()?;
        if !make_status.success() {
            return Err(color_eyre::eyre::eyre!("Failed to build Shadow-compatible monerod"));
        }
    }
    Ok(())
} 