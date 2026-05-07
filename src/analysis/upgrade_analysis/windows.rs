//! Pre-partitioning of observation data into per-window slices.
//!
//! Building these structures runs once before the per-window metrics loop and
//! turns each window's filter step from O(N) into a slice-by-index. The
//! synthetic-spy trial sets are also pre-built here so they can be shared
//! read-only across the parallel window pipeline.

use std::collections::{HashMap, HashSet};

use super::super::types::*;

/// Pre-partitioned data for efficient windowed analysis.
///
/// Flattens all per-node observations into globally sorted vectors, then
/// pre-computes window boundary indices via binary search. This turns
/// O(W * N * O) per-window filtering into O(N*O*log(N*O)) one-time setup
/// + O(slice_size) per window.
pub(super) struct PrepartitionedData<'a> {
    /// All TX observations sorted by timestamp
    pub tx_obs_sorted: Vec<&'a TxObservation>,
    /// Per-window (start, end) index ranges into tx_obs_sorted
    pub tx_obs_window_ranges: Vec<(usize, usize)>,

    /// All bandwidth events sorted by timestamp, with is_sent flag and bytes
    pub bw_sorted: Vec<BwRef<'a>>,
    /// Per-window (start, end) index ranges into bw_sorted
    pub bw_window_ranges: Vec<(usize, usize)>,

    /// Pre-computed average peer count at each window's end time
    pub conn_avg_peer_counts: Vec<Option<f64>>,
}

pub(super) struct BwRef<'a> {
    pub event: &'a BandwidthEvent,
}

/// Build pre-partitioned data structures for all windows (runs once).
pub(super) fn prepartition_data<'a>(
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

/// Pre-computed random node subsets for synthetic spy analysis.
/// Built once, shared read-only across parallel window processing.
pub(super) struct SpyTrialSets {
    /// Visibility levels (e.g., [0.05, 0.10, 0.20, 0.30, 0.50])
    pub visibility_levels: Vec<f64>,
    /// For each visibility level, for each trial: set of monitored node_ids
    /// Indexed as: trial_sets[level_idx][trial_idx] = HashSet<node_id>
    pub trial_sets: Vec<Vec<HashSet<String>>>,
}

pub(super) fn build_spy_trial_sets(
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
