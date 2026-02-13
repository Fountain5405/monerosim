//! Upgrade impact analysis.
//!
//! Analyzes changes in network behavior before and after a daemon upgrade
//! by comparing metrics across time windows.

use std::collections::{HashMap, HashSet};
use std::path::Path;

use chrono::Utc;
use color_eyre::eyre::Result;
use rayon::prelude::*;

use super::time_window::*;
use super::types::*;

/// Pre-partitioned data for efficient windowed analysis.
///
/// Flattens all per-node observations into globally sorted vectors, then
/// pre-computes window boundary indices via binary search. This turns
/// O(W * N * O) per-window filtering into O(N*O*log(N*O)) one-time setup
/// + O(slice_size) per window.
struct PrepartitionedData<'a> {
    /// All TX observations sorted by timestamp
    tx_obs_sorted: Vec<&'a TxObservation>,
    /// Per-window (start, end) index ranges into tx_obs_sorted
    tx_obs_window_ranges: Vec<(usize, usize)>,

    /// All bandwidth events sorted by timestamp, with is_sent flag and bytes
    bw_sorted: Vec<BwRef<'a>>,
    /// Per-window (start, end) index ranges into bw_sorted
    bw_window_ranges: Vec<(usize, usize)>,

    /// Pre-computed average peer count at each window's end time
    conn_avg_peer_counts: Vec<Option<f64>>,
}

struct BwRef<'a> {
    event: &'a BandwidthEvent,
}

/// Build pre-partitioned data structures for all windows (runs once).
fn prepartition_data<'a>(
    log_data: &'a HashMap<String, NodeLogData>,
    windows: &[TimeWindow],
) -> PrepartitionedData<'a> {
    // 1. Flatten and sort TX observations by timestamp
    let mut tx_obs_sorted: Vec<&TxObservation> = log_data
        .values()
        .flat_map(|nd| nd.tx_observations.iter())
        .collect();
    tx_obs_sorted.sort_by(|a, b| a.timestamp.partial_cmp(&b.timestamp).unwrap());

    let tx_obs_window_ranges: Vec<(usize, usize)> = windows
        .iter()
        .map(|w| {
            let start = tx_obs_sorted.partition_point(|o| o.timestamp < w.start);
            let end = tx_obs_sorted.partition_point(|o| o.timestamp < w.end);
            (start, end)
        })
        .collect();

    // 2. Flatten and sort bandwidth events by timestamp
    let mut bw_pairs: Vec<(&BandwidthEvent, SimTime)> = log_data
        .values()
        .flat_map(|nd| nd.bandwidth_events.iter().map(|e| (e, e.timestamp)))
        .collect();
    bw_pairs.sort_by(|a, b| a.1.partial_cmp(&b.1).unwrap());

    let bw_sorted: Vec<BwRef> = bw_pairs
        .iter()
        .map(|(e, _)| BwRef { event: e })
        .collect();

    let bw_window_ranges: Vec<(usize, usize)> = windows
        .iter()
        .map(|w| {
            let start = bw_pairs.partition_point(|(_, ts)| *ts < w.start);
            let end = bw_pairs.partition_point(|(_, ts)| *ts < w.end);
            (start, end)
        })
        .collect();

    // 3. Incrementally compute connection state at each window boundary
    // Sort all connection events globally by timestamp
    let mut all_conn_events: Vec<(&ConnectionEvent, &str)> = log_data
        .iter()
        .flat_map(|(nid, nd)| {
            nd.connection_events.iter().map(move |e| (e, nid.as_str()))
        })
        .collect();
    all_conn_events.sort_by(|a, b| a.0.timestamp.partial_cmp(&b.0.timestamp).unwrap());

    // Walk through events once, snapshotting peer counts at each window end
    let mut conn_avg_peer_counts = Vec::with_capacity(windows.len());
    let mut current_peers: HashMap<&str, HashMap<String, bool>> = HashMap::new();
    let mut event_idx = 0;

    for window in windows {
        // Advance events up to window.end (inclusive, matching original <= behavior)
        while event_idx < all_conn_events.len()
            && all_conn_events[event_idx].0.timestamp <= window.end
        {
            let (event, node_id) = all_conn_events[event_idx];
            let node_peers = current_peers.entry(node_id).or_default();
            let peer_key = format!("{}:{}", event.peer_ip, event.connection_id);
            if event.is_open {
                node_peers.insert(peer_key, true);
            } else {
                node_peers.remove(&peer_key);
            }
            event_idx += 1;
        }

        // Snapshot average peer count
        if current_peers.is_empty() {
            conn_avg_peer_counts.push(None);
        } else {
            let peer_counts: Vec<f64> = current_peers
                .values()
                .map(|peers| peers.len() as f64)
                .collect();
            let avg = peer_counts.iter().sum::<f64>() / peer_counts.len() as f64;
            conn_avg_peer_counts.push(Some(avg));
        }
    }

    PrepartitionedData {
        tx_obs_sorted,
        tx_obs_window_ranges,
        bw_sorted,
        bw_window_ranges,
        conn_avg_peer_counts,
    }
}

/// Configuration for upgrade analysis
#[derive(Debug, Clone)]
pub struct UpgradeAnalysisConfig {
    /// Size of each time window in seconds
    pub window_size_sec: f64,
    /// Optional path to upgrade manifest
    pub manifest_path: Option<String>,
    /// Manual override: end of pre-upgrade period
    pub pre_upgrade_end: Option<SimTime>,
    /// Manual override: start of post-upgrade period
    pub post_upgrade_start: Option<SimTime>,
}

impl Default for UpgradeAnalysisConfig {
    fn default() -> Self {
        Self {
            window_size_sec: 60.0,
            manifest_path: None,
            pre_upgrade_end: None,
            post_upgrade_start: None,
        }
    }
}

/// Pre-computed random node subsets for synthetic spy analysis.
/// Built once, shared read-only across parallel window processing.
struct SpyTrialSets {
    /// Visibility levels (e.g., [0.05, 0.10, 0.20, 0.30, 0.50])
    visibility_levels: Vec<f64>,
    /// For each visibility level, for each trial: set of monitored node_ids
    /// Indexed as: trial_sets[level_idx][trial_idx] = HashSet<node_id>
    trial_sets: Vec<Vec<HashSet<String>>>,
}

fn build_spy_trial_sets(
    node_ids: &[&str],
    visibility_levels: &[f64],
    trials_per_level: usize,
    base_seed: u64,
) -> SpyTrialSets {
    use rand::seq::SliceRandom;
    use rand::SeedableRng;
    use rand::rngs::StdRng;

    let mut trial_sets = Vec::with_capacity(visibility_levels.len());
    for (level_idx, &visibility) in visibility_levels.iter().enumerate() {
        let n_monitored = ((node_ids.len() as f64 * visibility).round() as usize).max(1);
        let mut level_trials = Vec::with_capacity(trials_per_level);
        for trial in 0..trials_per_level {
            let seed = base_seed + (level_idx as u64 * 100) + trial as u64;
            let mut rng = StdRng::seed_from_u64(seed);
            let mut shuffled = node_ids.to_vec();
            shuffled.shuffle(&mut rng);
            let monitored: HashSet<String> = shuffled[..n_monitored].iter().map(|s| s.to_string()).collect();
            level_trials.push(monitored);
        }
        trial_sets.push(level_trials);
    }
    SpyTrialSets { visibility_levels: visibility_levels.to_vec(), trial_sets }
}

/// Main entry point for upgrade impact analysis.
pub fn analyze_upgrade_impact(
    transactions: &[Transaction],
    log_data: &HashMap<String, NodeLogData>,
    agents: &[AgentInfo],
    _blocks: &[BlockInfo],
    config: &UpgradeAnalysisConfig,
    data_dir: &str,
) -> Result<UpgradeAnalysisReport> {
    // Find simulation time range
    let (sim_start, sim_end) = find_simulation_time_range(log_data);
    log::info!(
        "Simulation time range: {:.1}s - {:.1}s ({:.1}s duration)",
        sim_start,
        sim_end,
        sim_end - sim_start
    );

    // Load upgrade manifest if provided
    let manifest = if let Some(ref path) = config.manifest_path {
        Some(load_upgrade_manifest(Path::new(path))?)
    } else {
        None
    };

    // Create time windows
    let mut windows = create_time_windows(sim_start, sim_end, config.window_size_sec);
    log::info!("Created {} time windows of {}s each", windows.len(), config.window_size_sec);

    // Label windows based on upgrade timing
    if let Some(ref m) = manifest {
        label_windows_by_upgrade(&mut windows, m);
    } else if let (Some(pre_end), Some(post_start)) = (config.pre_upgrade_end, config.post_upgrade_start) {
        // Use manual overrides
        let manual_manifest = UpgradeManifest {
            pre_upgrade_version: None,
            post_upgrade_version: None,
            node_upgrades: Vec::new(),
            upgrade_start: Some(pre_end),
            upgrade_end: Some(post_start),
        };
        label_windows_by_upgrade(&mut windows, &manual_manifest);
    }

    // Pre-sort transactions by timestamp for binary-search window filtering
    let mut sorted_txs: Vec<&Transaction> = transactions.iter().collect();
    sorted_txs.sort_by(|a, b| a.timestamp.partial_cmp(&b.timestamp).unwrap());

    // Pre-partition all observation data (one-time O(N*O*log) cost)
    log::info!("Pre-partitioning observation data for {} windows...", windows.len());
    let prepartitioned = prepartition_data(log_data, &windows);
    log::info!(
        "Pre-partitioned: {} TX observations, {} bandwidth events",
        prepartitioned.tx_obs_sorted.len(),
        prepartitioned.bw_sorted.len(),
    );

    // Build IP-to-agent mapping (shared across all windows)
    let ip_to_agent: HashMap<&str, &AgentInfo> = agents
        .iter()
        .map(|a| (a.ip_addr.as_str(), a))
        .collect();

    // Pre-compute synthetic spy trial sets (shared read-only across parallel windows)
    const SPY_VISIBILITY_LEVELS: &[f64] = &[0.05, 0.10, 0.20, 0.30, 0.50];
    const SPY_TRIALS_PER_LEVEL: usize = 3;

    let node_ids: Vec<&str> = log_data.keys().map(|s| s.as_str()).collect();
    let spy_trials = build_spy_trial_sets(&node_ids, SPY_VISIBILITY_LEVELS, SPY_TRIALS_PER_LEVEL, 42);

    // Process all windows in parallel using rayon
    let windowed_metrics: Vec<WindowedMetrics> = windows
        .par_iter()
        .enumerate()
        .map(|(i, window)| {
            // Binary search for transactions in this window
            let tx_start = sorted_txs.partition_point(|tx| tx.timestamp < window.start);
            let tx_end = sorted_txs.partition_point(|tx| tx.timestamp < window.end);
            let window_txs = &sorted_txs[tx_start..tx_end];

            // Get pre-computed slices
            let (obs_start, obs_end) = prepartitioned.tx_obs_window_ranges[i];
            let tx_obs_slice = &prepartitioned.tx_obs_sorted[obs_start..obs_end];

            let (bw_start, bw_end) = prepartitioned.bw_window_ranges[i];
            let bw_slice = &prepartitioned.bw_sorted[bw_start..bw_end];

            let avg_peer_count = prepartitioned.conn_avg_peer_counts[i];

            calculate_window_metrics_fast(
                window,
                window_txs,
                tx_obs_slice,
                bw_slice,
                avg_peer_count,
                &ip_to_agent,
                &spy_trials,
            )
        })
        .collect();

    // Aggregate by period label
    let by_label = aggregate_windows_by_label(&windowed_metrics);

    // Create period summaries
    let pre_upgrade_summary = create_period_summary("pre-upgrade", &by_label);
    let transition_summary = create_period_summary("transition", &by_label);
    let post_upgrade_summary = create_period_summary("post-upgrade", &by_label);

    // Compare pre vs post
    let changes = if pre_upgrade_summary.is_some() && post_upgrade_summary.is_some() {
        compare_periods(
            pre_upgrade_summary.as_ref().unwrap(),
            post_upgrade_summary.as_ref().unwrap(),
        )
    } else {
        Vec::new()
    };

    // Generate assessment
    let assessment = generate_assessment(&changes, &pre_upgrade_summary, &post_upgrade_summary);

    // Build metadata
    let metadata = UpgradeAnalysisMetadata {
        analysis_timestamp: Utc::now().to_rfc3339(),
        simulation_data_dir: data_dir.to_string(),
        simulation_start: sim_start,
        simulation_end: sim_end,
        window_size_sec: config.window_size_sec,
        total_windows: windowed_metrics.len(),
        total_nodes: agents.len(),
        total_transactions: transactions.len(),
        spy_visibility_levels: SPY_VISIBILITY_LEVELS.to_vec(),
        spy_trials_per_level: SPY_TRIALS_PER_LEVEL,
        fluff_gap_thresholds_ms: FLUFF_GAP_THRESHOLDS_MS.to_vec(),
    };

    Ok(UpgradeAnalysisReport {
        metadata,
        upgrade_info: manifest,
        time_series: windowed_metrics,
        pre_upgrade_summary,
        transition_summary,
        post_upgrade_summary,
        changes,
        assessment,
    })
}

/// Calculate all metrics for a single time window using pre-partitioned data.
///
/// Receives pre-windowed slices instead of re-scanning all observations.
fn calculate_window_metrics_fast(
    window: &TimeWindow,
    window_txs: &[&Transaction],
    tx_obs_slice: &[&TxObservation],
    bw_slice: &[BwRef],
    avg_peer_count: Option<f64>,
    ip_to_agent: &HashMap<&str, &AgentInfo>,
    spy_trials: &SpyTrialSets,
) -> WindowedMetrics {
    let mut metrics = WindowedMetrics {
        window: window.clone(),
        ..Default::default()
    };

    metrics.tx_count = window_txs.len();
    metrics.observation_count = tx_obs_slice.len();

    if window_txs.is_empty() || tx_obs_slice.is_empty() {
        // Still compute bandwidth even if no TXs
        let (bytes_sent, bytes_received, msg_count) = calculate_bandwidth_from_slice(bw_slice);
        if bytes_sent > 0 || bytes_received > 0 {
            metrics.bytes_sent = Some(bytes_sent);
            metrics.bytes_received = Some(bytes_received);
            metrics.total_bandwidth = Some(bytes_sent + bytes_received);
            metrics.bandwidth_message_count = Some(msg_count);
        }
        metrics.avg_peer_count = avg_peer_count;
        return metrics;
    }

    // Build TX hash -> observations mapping from the pre-windowed slice
    let window_tx_hashes: HashSet<&str> =
        window_txs.iter().map(|tx| tx.tx_hash.as_str()).collect();

    let mut tx_observations: HashMap<String, Vec<&TxObservation>> = HashMap::new();
    for &obs in tx_obs_slice {
        if window_tx_hashes.contains(obs.tx_hash.as_str()) {
            tx_observations
                .entry(obs.tx_hash.clone())
                .or_default()
                .push(obs);
        }
    }

    // Synthetic spy node analysis
    let (spy_accuracy_by_vis, spy_analyzable) =
        calculate_synthetic_spy_accuracy(window_txs, &tx_observations, ip_to_agent, spy_trials);
    metrics.spy_accuracy_by_visibility = spy_accuracy_by_vis;
    metrics.spy_analyzable_txs = spy_analyzable;

    // Propagation analysis
    let (avg_prop, median_prop, p95_prop) =
        calculate_propagation_for_window(&tx_observations);
    metrics.avg_propagation_ms = avg_prop;
    metrics.median_propagation_ms = median_prop;
    metrics.p95_propagation_ms = p95_prop;

    // Pre-computed connection state
    metrics.avg_peer_count = avg_peer_count;

    // Gini coefficient for first-seen distribution in this window
    metrics.gini_coefficient = calculate_gini_for_window(&tx_observations);

    // Dandelion analysis (gap-based fluff detection, multiple thresholds)
    let (avg_stem, paths_count, stem_by_threshold) =
        calculate_dandelion_for_window(window_txs, &tx_observations, ip_to_agent, FLUFF_GAP_THRESHOLDS_MS);
    metrics.avg_stem_length = avg_stem;
    metrics.stem_length_by_gap_threshold = stem_by_threshold;
    metrics.paths_reconstructed = paths_count;

    // Bandwidth analysis from pre-windowed slice
    let (bytes_sent, bytes_received, msg_count) = calculate_bandwidth_from_slice(bw_slice);
    if bytes_sent > 0 || bytes_received > 0 {
        metrics.bytes_sent = Some(bytes_sent);
        metrics.bytes_received = Some(bytes_received);
        metrics.total_bandwidth = Some(bytes_sent + bytes_received);
        metrics.bandwidth_message_count = Some(msg_count);
    }

    metrics
}

/// Calculate bandwidth metrics from a pre-windowed slice of bandwidth events.
fn calculate_bandwidth_from_slice(bw_slice: &[BwRef]) -> (u64, u64, u64) {
    let mut bytes_sent: u64 = 0;
    let mut bytes_received: u64 = 0;
    let mut message_count: u64 = 0;

    for bw in bw_slice {
        if bw.event.is_sent {
            bytes_sent += bw.event.bytes;
        } else {
            bytes_received += bw.event.bytes;
        }
        message_count += 1;
    }

    (bytes_sent, bytes_received, message_count)
}

/// Calculate synthetic spy accuracy at multiple visibility levels.
///
/// For each visibility level, for each trial:
///   For each TX, find earliest observation from a monitored node,
///   infer originator = source_ip of that observation.
///   Compare to true sender IP.
/// Average accuracy across trials for each level.
fn calculate_synthetic_spy_accuracy(
    transactions: &[&Transaction],
    tx_observations: &HashMap<String, Vec<&TxObservation>>,
    ip_to_agent: &HashMap<&str, &AgentInfo>,
    spy_trials: &SpyTrialSets,
) -> (Option<Vec<f64>>, usize) {
    // Count analyzable TXs (have observations and a known sender IP)
    let mut analyzable = 0usize;
    for tx in transactions {
        if let Some(observations) = tx_observations.get(&tx.tx_hash) {
            if observations.is_empty() {
                continue;
            }
            let true_sender_ip = ip_to_agent
                .iter()
                .find(|(_, agent)| agent.id == tx.sender_id)
                .map(|(ip, _)| *ip);
            if true_sender_ip.is_some() {
                analyzable += 1;
            }
        }
    }

    if analyzable == 0 {
        return (None, 0);
    }

    let mut level_accuracies = Vec::with_capacity(spy_trials.visibility_levels.len());
    for level_trials in &spy_trials.trial_sets {
        let mut trial_accuracies = Vec::new();
        for monitored_set in level_trials {
            let mut correct = 0;
            let mut total = 0;
            for tx in transactions {
                if let Some(observations) = tx_observations.get(&tx.tx_hash) {
                    let true_sender_ip = ip_to_agent
                        .iter()
                        .find(|(_, agent)| agent.id == tx.sender_id)
                        .map(|(ip, _)| *ip);
                    if true_sender_ip.is_none() {
                        continue;
                    }
                    let true_ip = true_sender_ip.unwrap();

                    // Find earliest observation from a monitored node
                    let earliest = observations
                        .iter()
                        .filter(|obs| monitored_set.contains(&obs.node_id))
                        .min_by(|a, b| {
                            a.timestamp
                                .partial_cmp(&b.timestamp)
                                .unwrap_or(std::cmp::Ordering::Equal)
                        });

                    if let Some(obs) = earliest {
                        total += 1;
                        if obs.source_ip == true_ip {
                            correct += 1;
                        }
                    }
                }
            }
            if total > 0 {
                trial_accuracies.push(correct as f64 / total as f64);
            }
        }
        if !trial_accuracies.is_empty() {
            let avg = trial_accuracies.iter().sum::<f64>() / trial_accuracies.len() as f64;
            level_accuracies.push(avg);
        } else {
            level_accuracies.push(0.0);
        }
    }

    (Some(level_accuracies), analyzable)
}

/// Calculate propagation metrics for a window.
fn calculate_propagation_for_window(
    tx_observations: &HashMap<String, Vec<&TxObservation>>,
) -> (Option<f64>, Option<f64>, Option<f64>) {
    let mut all_propagation_times: Vec<f64> = Vec::new();

    for observations in tx_observations.values() {
        if observations.is_empty() {
            continue;
        }

        let mut sorted_obs: Vec<&&TxObservation> = observations.iter().collect();
        sorted_obs.sort_by(|a, b| {
            a.timestamp
                .partial_cmp(&b.timestamp)
                .unwrap_or(std::cmp::Ordering::Equal)
        });

        let first_time = sorted_obs.first().map(|o| o.timestamp).unwrap_or(0.0);
        let last_time = sorted_obs.last().map(|o| o.timestamp).unwrap_or(0.0);

        let propagation_ms = (last_time - first_time) * 1000.0;
        all_propagation_times.push(propagation_ms);
    }

    if all_propagation_times.is_empty() {
        return (None, None, None);
    }

    all_propagation_times.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));

    let avg = all_propagation_times.iter().sum::<f64>() / all_propagation_times.len() as f64;
    let median = all_propagation_times[all_propagation_times.len() / 2];
    let p95_idx = (all_propagation_times.len() as f64 * 0.95) as usize;
    let p95 = all_propagation_times.get(p95_idx).copied().unwrap_or(median);

    (Some(avg), Some(median), Some(p95))
}

/// Calculate Gini coefficient for first-seen distribution.
fn calculate_gini_for_window(
    tx_observations: &HashMap<String, Vec<&TxObservation>>,
) -> Option<f64> {
    // Count first-seens per node
    let mut first_seen_counts: HashMap<&str, usize> = HashMap::new();

    for observations in tx_observations.values() {
        if observations.is_empty() {
            continue;
        }

        // Find the node that saw this TX first
        let first_obs = observations
            .iter()
            .min_by(|a, b| {
                a.timestamp
                    .partial_cmp(&b.timestamp)
                    .unwrap_or(std::cmp::Ordering::Equal)
            });

        if let Some(obs) = first_obs {
            *first_seen_counts.entry(&obs.node_id).or_insert(0) += 1;
        }
    }

    if first_seen_counts.is_empty() {
        return None;
    }

    // Calculate Gini coefficient
    let mut values: Vec<f64> = first_seen_counts.values().map(|&v| v as f64).collect();
    values.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));

    let n = values.len() as f64;
    let sum: f64 = values.iter().sum();

    if sum == 0.0 {
        return Some(0.0);
    }

    let mut gini_sum = 0.0;
    for (i, v) in values.iter().enumerate() {
        gini_sum += (2.0 * (i + 1) as f64 - n - 1.0) * v;
    }

    Some(gini_sum / (n * sum))
}

/// Gap thresholds (ms) for multi-threshold stem length analysis.
const FLUFF_GAP_THRESHOLDS_MS: &[f64] = &[500.0, 1000.0, 2000.0, 3000.0, 5000.0];

/// Index of the representative threshold (2000ms) used for backward-compatible avg_stem_length.
const REPRESENTATIVE_THRESHOLD_IDX: usize = 2;

/// Trace stem length for a single TX with a given fluff gap threshold.
///
/// Walks the chain of relays starting from the originator. At each step, if 3+
/// recipients are found from the current sender, checks whether the time gap
/// between the 1st and 3rd observation is within `threshold_ms`. If so, it's
/// a genuine fluff broadcast and the chain stops. Otherwise, the first
/// observation is a stem relay (the rest are later gossip re-relays).
fn trace_stem_with_threshold(
    sorted_obs: &[&TxObservation],
    originator_ip: &str,
    node_to_ip: &HashMap<&str, &str>,
    threshold_ms: f64,
) -> usize {
    let mut stem_length = 0usize;
    let mut used: HashSet<usize> = HashSet::new();

    // Find first observation from originator
    let first_hop_idx = sorted_obs
        .iter()
        .enumerate()
        .find(|(_, obs)| obs.source_ip == originator_ip)
        .map(|(i, _)| i);

    if let Some(idx) = first_hop_idx {
        used.insert(idx);
        stem_length = 1;

        let mut current_sender_ip = node_to_ip
            .get(sorted_obs[idx].node_id.as_str())
            .copied();

        for _ in 0..50 {
            if current_sender_ip.is_none() {
                break;
            }

            let sender_ip = current_sender_ip.unwrap();

            let from_current: Vec<(usize, &TxObservation)> = sorted_obs
                .iter()
                .enumerate()
                .filter(|(i, obs)| !used.contains(i) && obs.source_ip == sender_ip)
                .map(|(i, obs)| (i, *obs))
                .collect();

            if from_current.is_empty() {
                break;
            }

            // Check for fluff (3+ recipients with clustered timing)
            if from_current.len() >= 3 {
                let first_time = from_current[0].1.timestamp;
                let third_time = from_current[2].1.timestamp;
                let gap_ms = (third_time - first_time) * 1000.0;

                if gap_ms <= threshold_ms {
                    // Genuine fluff broadcast -> stop
                    break;
                }
                // Large gap -> stem relay + later gossip, fall through
            }

            // Take first recipient as next stem hop
            let (next_idx, next_obs) = from_current[0];
            used.insert(next_idx);
            stem_length += 1;

            current_sender_ip = node_to_ip.get(next_obs.node_id.as_str()).copied();
        }
    }

    stem_length
}

/// Calculate simplified Dandelion metrics for a window with multi-threshold gap detection.
fn calculate_dandelion_for_window(
    transactions: &[&Transaction],
    tx_observations: &HashMap<String, Vec<&TxObservation>>,
    ip_to_agent: &HashMap<&str, &AgentInfo>,
    gap_thresholds_ms: &[f64],
) -> (Option<f64>, usize, Option<Vec<f64>>) {
    // Build node_to_ip map once
    let node_to_ip: HashMap<&str, &str> = ip_to_agent
        .iter()
        .map(|(ip, agent)| (agent.id.as_str(), *ip))
        .collect();

    let mut per_threshold_lengths: Vec<Vec<f64>> = vec![Vec::new(); gap_thresholds_ms.len()];
    let mut paths_count = 0usize;

    for tx in transactions {
        if let Some(observations) = tx_observations.get(&tx.tx_hash) {
            if observations.is_empty() {
                continue;
            }

            let originator_ip = ip_to_agent
                .iter()
                .find(|(_, agent)| agent.id == tx.sender_id)
                .map(|(ip, _)| *ip);

            if originator_ip.is_none() {
                continue;
            }

            let originator_ip = originator_ip.unwrap();

            // Sort observations once
            let mut sorted_obs: Vec<&TxObservation> = observations.iter().copied().collect();
            sorted_obs.sort_by(|a, b| {
                a.timestamp
                    .partial_cmp(&b.timestamp)
                    .unwrap_or(std::cmp::Ordering::Equal)
            });

            let mut any_positive = false;
            for (t_idx, &threshold_ms) in gap_thresholds_ms.iter().enumerate() {
                let stem_len = trace_stem_with_threshold(
                    &sorted_obs,
                    originator_ip,
                    &node_to_ip,
                    threshold_ms,
                );
                if stem_len > 0 {
                    per_threshold_lengths[t_idx].push(stem_len as f64);
                    any_positive = true;
                }
            }

            if any_positive {
                paths_count += 1;
            }
        }
    }

    if paths_count == 0 {
        return (None, 0, None);
    }

    // Compute per-threshold averages
    let threshold_avgs: Vec<f64> = per_threshold_lengths
        .iter()
        .map(|lengths| {
            if lengths.is_empty() {
                0.0
            } else {
                lengths.iter().sum::<f64>() / lengths.len() as f64
            }
        })
        .collect();

    // Representative value: use the middle threshold (2000ms) for backward compat
    let representative_idx = REPRESENTATIVE_THRESHOLD_IDX.min(threshold_avgs.len().saturating_sub(1));
    let avg_stem = threshold_avgs.get(representative_idx).copied();

    (avg_stem, paths_count, Some(threshold_avgs))
}

/// Create an aggregated summary for a labeled period.
fn create_period_summary(
    label: &str,
    by_label: &HashMap<String, Vec<&WindowedMetrics>>,
) -> Option<AggregatedMetrics> {
    let windows = by_label.get(label)?;

    if windows.is_empty() {
        return None;
    }

    let start = windows.iter().map(|w| w.window.start).min_by(|a, b| a.partial_cmp(b).unwrap())?;
    let end = windows.iter().map(|w| w.window.end).max_by(|a, b| a.partial_cmp(b).unwrap())?;
    let total_txs: usize = windows.iter().map(|w| w.tx_count).sum();

    // Calculate per-visibility-level spy accuracy stats
    // Determine number of visibility levels from the first window that has data
    let num_levels = windows
        .iter()
        .filter_map(|w| w.spy_accuracy_by_visibility.as_ref())
        .map(|v| v.len())
        .next()
        .unwrap_or(0);

    let (mean_spy_by_vis, std_spy_by_vis) = if num_levels > 0 {
        let mut means = Vec::with_capacity(num_levels);
        let mut stds = Vec::with_capacity(num_levels);
        for level_idx in 0..num_levels {
            let values: Vec<Option<f64>> = windows
                .iter()
                .map(|w| {
                    w.spy_accuracy_by_visibility
                        .as_ref()
                        .and_then(|v| v.get(level_idx).copied())
                })
                .collect();
            let (m, s) = calculate_stats(&values);
            means.push(m.unwrap_or(0.0));
            stds.push(s.unwrap_or(0.0));
        }
        (Some(means), Some(stds))
    } else {
        (None, None)
    };

    let prop_values: Vec<Option<f64>> = windows.iter().map(|w| w.avg_propagation_ms).collect();
    let (mean_prop, std_prop) = calculate_stats(&prop_values);

    let peer_values: Vec<Option<f64>> = windows.iter().map(|w| w.avg_peer_count).collect();
    let (mean_peer, std_peer) = calculate_stats(&peer_values);

    let gini_values: Vec<Option<f64>> = windows.iter().map(|w| w.gini_coefficient).collect();
    let (mean_gini, std_gini) = calculate_stats(&gini_values);

    let stem_values: Vec<Option<f64>> = windows.iter().map(|w| w.avg_stem_length).collect();
    let (mean_stem, std_stem) = calculate_stats(&stem_values);

    // Per-threshold stem length aggregation (mirrors spy accuracy pattern)
    let num_thresholds = windows
        .iter()
        .filter_map(|w| w.stem_length_by_gap_threshold.as_ref())
        .map(|v| v.len())
        .next()
        .unwrap_or(0);

    let (mean_stem_by_threshold, std_stem_by_threshold) = if num_thresholds > 0 {
        let mut means = Vec::with_capacity(num_thresholds);
        let mut stds = Vec::with_capacity(num_thresholds);
        for t_idx in 0..num_thresholds {
            let values: Vec<Option<f64>> = windows
                .iter()
                .map(|w| {
                    w.stem_length_by_gap_threshold
                        .as_ref()
                        .and_then(|v| v.get(t_idx).copied())
                })
                .collect();
            let (m, s) = calculate_stats(&values);
            means.push(m.unwrap_or(0.0));
            stds.push(s.unwrap_or(0.0));
        }
        (Some(means), Some(stds))
    } else {
        (None, None)
    };

    // Bandwidth aggregation
    let total_bytes_sent: u64 = windows.iter().filter_map(|w| w.bytes_sent).sum();
    let total_bytes_received: u64 = windows.iter().filter_map(|w| w.bytes_received).sum();
    let total_bandwidth: u64 = windows.iter().filter_map(|w| w.total_bandwidth).sum();

    let bandwidth_values: Vec<Option<f64>> = windows
        .iter()
        .map(|w| w.total_bandwidth.map(|b| b as f64))
        .collect();
    let (mean_bw, std_bw) = calculate_stats(&bandwidth_values);

    Some(AggregatedMetrics {
        period_label: label.to_string(),
        start,
        end,
        window_count: windows.len(),
        total_txs,
        mean_spy_accuracy_by_visibility: mean_spy_by_vis,
        mean_propagation_ms: mean_prop,
        mean_peer_count: mean_peer,
        mean_gini: mean_gini,
        mean_stem_length: mean_stem,
        mean_stem_length_by_gap_threshold: mean_stem_by_threshold,
        std_spy_accuracy_by_visibility: std_spy_by_vis,
        std_propagation_ms: std_prop,
        std_peer_count: std_peer,
        std_gini: std_gini,
        std_stem_length: std_stem,
        std_stem_length_by_gap_threshold: std_stem_by_threshold,
        total_bytes_sent: if total_bytes_sent > 0 { Some(total_bytes_sent) } else { None },
        total_bytes_received: if total_bytes_received > 0 { Some(total_bytes_received) } else { None },
        total_bandwidth: if total_bandwidth > 0 { Some(total_bandwidth) } else { None },
        mean_bandwidth_per_window: mean_bw,
        std_bandwidth_per_window: std_bw,
        windows: windows.iter().map(|w| (*w).clone()).collect(),
    })
}

/// Compare pre and post upgrade periods.
fn compare_periods(pre: &AggregatedMetrics, post: &AggregatedMetrics) -> Vec<MetricChange> {
    let mut changes = Vec::new();

    // Helper to create a metric change with explicit sample extraction
    let build_change = |name: &str,
                        pre_v: f64,
                        post_v: f64,
                        pre_samples: Vec<f64>,
                        post_samples: Vec<f64>,
                        higher_is_better: bool|
     -> MetricChange {
        let absolute_change = post_v - pre_v;
        let percent_change = if pre_v != 0.0 {
            (absolute_change / pre_v) * 100.0
        } else {
            0.0
        };

        let p_value = welch_t_test(&pre_samples, &post_samples);
        let significant = is_significant(p_value);

        let impact = if !significant {
            ChangeImpact::Neutral
        } else if higher_is_better {
            if absolute_change > 0.0 {
                ChangeImpact::Positive
            } else {
                ChangeImpact::Negative
            }
        } else {
            if absolute_change < 0.0 {
                ChangeImpact::Positive
            } else {
                ChangeImpact::Negative
            }
        };

        let interpretation = generate_interpretation(name, percent_change, significant, impact);

        MetricChange {
            metric_name: name.to_string(),
            pre_value: pre_v,
            post_value: post_v,
            absolute_change,
            percent_change,
            p_value,
            statistically_significant: significant,
            interpretation,
            impact,
        }
    };

    // Helper for simple Option<f64> metrics
    let add_change = |name: &str,
                      pre_val: Option<f64>,
                      post_val: Option<f64>,
                      extract: &dyn Fn(&WindowedMetrics) -> Option<f64>,
                      higher_is_better: bool|
     -> Option<MetricChange> {
        let (pre_v, post_v) = (pre_val?, post_val?);
        let pre_samples: Vec<f64> = pre.windows.iter().filter_map(extract).collect();
        let post_samples: Vec<f64> = post.windows.iter().filter_map(extract).collect();
        Some(build_change(name, pre_v, post_v, pre_samples, post_samples, higher_is_better))
    };

    // Per-visibility-level spy accuracy comparisons (lower is better)
    let visibility_levels = [0.05, 0.10, 0.20, 0.30, 0.50];
    if let (Some(pre_means), Some(post_means)) = (
        &pre.mean_spy_accuracy_by_visibility,
        &post.mean_spy_accuracy_by_visibility,
    ) {
        for (level_idx, &vis) in visibility_levels.iter().enumerate() {
            if let (Some(&pre_v), Some(&post_v)) = (pre_means.get(level_idx), post_means.get(level_idx)) {
                let name = format!("Spy Acc ({}% vis)", (vis * 100.0) as u32);
                let pre_samples: Vec<f64> = pre
                    .windows
                    .iter()
                    .filter_map(|w| {
                        w.spy_accuracy_by_visibility
                            .as_ref()
                            .and_then(|v| v.get(level_idx).copied())
                    })
                    .collect();
                let post_samples: Vec<f64> = post
                    .windows
                    .iter()
                    .filter_map(|w| {
                        w.spy_accuracy_by_visibility
                            .as_ref()
                            .and_then(|v| v.get(level_idx).copied())
                    })
                    .collect();
                changes.push(build_change(&name, pre_v, post_v, pre_samples, post_samples, false));
            }
        }
    }

    // Propagation: Lower is better (faster network)
    if let Some(change) = add_change(
        "Avg Propagation (ms)",
        pre.mean_propagation_ms,
        post.mean_propagation_ms,
        &|w: &WindowedMetrics| w.avg_propagation_ms,
        false,
    ) {
        changes.push(change);
    }

    // Peer count: Higher is better (more connectivity)
    if let Some(change) = add_change(
        "Avg Peer Count",
        pre.mean_peer_count,
        post.mean_peer_count,
        &|w: &WindowedMetrics| w.avg_peer_count,
        true,
    ) {
        changes.push(change);
    }

    // Gini: Lower is better (less centralized)
    if let Some(change) = add_change(
        "Gini Coefficient",
        pre.mean_gini,
        post.mean_gini,
        &|w: &WindowedMetrics| w.gini_coefficient,
        false,
    ) {
        changes.push(change);
    }

    // Stem length: Higher is better (better privacy)
    if let Some(change) = add_change(
        "Avg Stem Length",
        pre.mean_stem_length,
        post.mean_stem_length,
        &|w: &WindowedMetrics| w.avg_stem_length,
        true,
    ) {
        changes.push(change);
    }

    // Per-threshold stem length comparisons (higher is better)
    if let (Some(pre_means), Some(post_means)) = (
        &pre.mean_stem_length_by_gap_threshold,
        &post.mean_stem_length_by_gap_threshold,
    ) {
        for (t_idx, &threshold) in FLUFF_GAP_THRESHOLDS_MS.iter().enumerate() {
            if let (Some(&pre_v), Some(&post_v)) = (pre_means.get(t_idx), post_means.get(t_idx)) {
                let name = format!("Stem Len ({}ms gap)", threshold as u64);
                let pre_samples: Vec<f64> = pre
                    .windows
                    .iter()
                    .filter_map(|w| {
                        w.stem_length_by_gap_threshold
                            .as_ref()
                            .and_then(|v| v.get(t_idx).copied())
                    })
                    .collect();
                let post_samples: Vec<f64> = post
                    .windows
                    .iter()
                    .filter_map(|w| {
                        w.stem_length_by_gap_threshold
                            .as_ref()
                            .and_then(|v| v.get(t_idx).copied())
                    })
                    .collect();
                changes.push(build_change(&name, pre_v, post_v, pre_samples, post_samples, true));
            }
        }
    }

    // Bandwidth: Lower is better (more efficient)
    if let Some(change) = add_change(
        "Bandwidth per Window",
        pre.mean_bandwidth_per_window,
        post.mean_bandwidth_per_window,
        &|w: &WindowedMetrics| w.total_bandwidth.map(|b| b as f64),
        false,
    ) {
        changes.push(change);
    }

    changes
}

/// Generate human-readable interpretation of a metric change.
fn generate_interpretation(
    metric_name: &str,
    percent_change: f64,
    significant: bool,
    impact: ChangeImpact,
) -> String {
    if !significant {
        return format!("{} remained stable (no significant change)", metric_name);
    }

    let direction = if percent_change > 0.0 {
        "increased"
    } else {
        "decreased"
    };

    let impact_word = match impact {
        ChangeImpact::Positive => "improved",
        ChangeImpact::Negative => "degraded",
        ChangeImpact::Neutral => "changed",
    };

    match metric_name {
        name if name.starts_with("Spy Acc (") => format!(
            "Privacy {} - {} inference {} by {:.1}%",
            impact_word, name, direction, percent_change.abs()
        ),
        "Avg Propagation (ms)" => format!(
            "Network speed {} - propagation time {} by {:.1}%",
            impact_word, direction, percent_change.abs()
        ),
        "Avg Peer Count" => format!(
            "Connectivity {} - average peer count {} by {:.1}%",
            impact_word, direction, percent_change.abs()
        ),
        "Gini Coefficient" => format!(
            "Centralization {} - Gini coefficient {} by {:.1}%",
            impact_word, direction, percent_change.abs()
        ),
        name if name == "Avg Stem Length" || name.starts_with("Stem Len (") => format!(
            "Dandelion++ privacy {} - stem length {} by {:.1}%",
            impact_word, direction, percent_change.abs()
        ),
        "Bandwidth per Window" => format!(
            "Bandwidth efficiency {} - data usage {} by {:.1}%",
            impact_word, direction, percent_change.abs()
        ),
        _ => format!("{} {} by {:.1}%", metric_name, direction, percent_change.abs()),
    }
}

/// Generate overall assessment of upgrade impact.
fn generate_assessment(
    changes: &[MetricChange],
    pre: &Option<AggregatedMetrics>,
    post: &Option<AggregatedMetrics>,
) -> UpgradeAssessment {
    let mut findings = Vec::new();
    let mut concerns = Vec::new();
    let mut recommendations = Vec::new();

    let mut improved = 0;
    let mut degraded = 0;
    let mut unchanged = 0;

    for change in changes {
        match change.impact {
            ChangeImpact::Positive => {
                improved += 1;
                findings.push(change.interpretation.clone());
            }
            ChangeImpact::Negative => {
                degraded += 1;
                concerns.push(change.interpretation.clone());
            }
            ChangeImpact::Neutral => {
                unchanged += 1;
            }
        }
    }

    // Determine verdict
    let verdict = if pre.is_none() || post.is_none() {
        recommendations.push(
            "Provide upgrade manifest or manual timestamps to identify pre/post periods".to_string(),
        );
        UpgradeVerdict::Inconclusive
    } else if degraded > 0 && improved == 0 {
        recommendations.push("Consider reverting upgrade or investigating degraded metrics".to_string());
        UpgradeVerdict::Negative
    } else if improved > 0 && degraded == 0 {
        UpgradeVerdict::Positive
    } else if improved > 0 && degraded > 0 {
        recommendations.push("Investigate trade-offs between improved and degraded metrics".to_string());
        UpgradeVerdict::Mixed
    } else {
        findings.push("No significant changes detected in measured metrics".to_string());
        UpgradeVerdict::Neutral
    };

    UpgradeAssessment {
        verdict,
        metrics_improved: improved,
        metrics_degraded: degraded,
        metrics_unchanged: unchanged,
        findings,
        concerns,
        recommendations,
    }
}
