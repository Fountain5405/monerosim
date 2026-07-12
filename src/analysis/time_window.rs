//! Time windowing utilities for segmented analysis.
//!
//! Provides functions to divide simulation time into windows and filter
//! observations/transactions to specific time ranges.

use std::collections::HashMap;
use std::fs;
use std::path::Path;

use color_eyre::eyre::{Context, Result};

use super::types::*;

/// Create time windows spanning the simulation duration.
///
/// # Arguments
/// * `start` - Simulation start time
/// * `end` - Simulation end time
/// * `window_size_sec` - Size of each window in seconds
///
/// # Returns
/// Vector of TimeWindow structs covering the entire simulation
pub fn create_time_windows(start: SimTime, end: SimTime, window_size_sec: f64) -> Vec<TimeWindow> {
    let mut windows = Vec::new();
    let mut current = start;
    let mut index = 0;

    while current < end {
        let window_end = (current + window_size_sec).min(end);
        windows.push(TimeWindow {
            start: current,
            end: window_end,
            label: Some(format!("window_{}", index)),
        });
        current = window_end;
        index += 1;
    }

    windows
}

/// Find the time range of all observations in the log data.
pub fn find_simulation_time_range(log_data: &HashMap<String, NodeLogData>) -> (SimTime, SimTime) {
    let mut min_time = f64::MAX;
    let mut max_time = f64::MIN;

    for node_data in log_data.values() {
        for obs in &node_data.tx_observations {
            min_time = min_time.min(obs.timestamp);
            max_time = max_time.max(obs.timestamp);
        }
        for event in &node_data.connection_events {
            min_time = min_time.min(event.timestamp);
            max_time = max_time.max(event.timestamp);
        }
        for obs in &node_data.block_observations {
            min_time = min_time.min(obs.timestamp);
            max_time = max_time.max(obs.timestamp);
        }
    }

    if min_time == f64::MAX {
        (0.0, 0.0)
    } else {
        (min_time, max_time)
    }
}

/// Load upgrade manifest from JSON file.
pub fn load_upgrade_manifest(path: &Path) -> Result<UpgradeManifest> {
    let content = fs::read_to_string(path)
        .with_context(|| format!("Failed to read upgrade manifest: {}", path.display()))?;

    // Parse the JSON structure
    let data: serde_json::Value = serde_json::from_str(&content)
        .with_context(|| "Failed to parse upgrade manifest JSON")?;

    let mut manifest = UpgradeManifest {
        pre_upgrade_version: data
            .get("pre_upgrade_version")
            .and_then(|v| v.as_str())
            .map(String::from),
        post_upgrade_version: data
            .get("post_upgrade_version")
            .and_then(|v| v.as_str())
            .map(String::from),
        node_upgrades: Vec::new(),
        upgrade_start: None,
        upgrade_end: None,
    };

    // Parse node upgrades
    if let Some(upgrades) = data.get("upgrades").and_then(|v| v.as_array()) {
        for upgrade in upgrades {
            if let (Some(node_id), Some(timestamp)) = (
                upgrade.get("node_id").and_then(|v| v.as_str()),
                upgrade.get("timestamp").and_then(|v| v.as_f64()),
            ) {
                let version = upgrade
                    .get("version")
                    .and_then(|v| v.as_str())
                    .unwrap_or("unknown")
                    .to_string();

                manifest.node_upgrades.push(NodeUpgradeEvent {
                    node_id: node_id.to_string(),
                    timestamp,
                    version,
                });
            }
        }
    }

    // Calculate upgrade start/end times
    if !manifest.node_upgrades.is_empty() {
        manifest.upgrade_start = manifest
            .node_upgrades
            .iter()
            .map(|u| u.timestamp)
            .min_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
        manifest.upgrade_end = manifest
            .node_upgrades
            .iter()
            .map(|u| u.timestamp)
            .max_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
    }

    Ok(manifest)
}

/// Label windows based on upgrade manifest.
///
/// Windows before upgrade_start get "pre-upgrade" label.
/// Windows during upgrade get "transition" label.
/// Windows after upgrade_end get "post-upgrade" label.
pub fn label_windows_by_upgrade(
    windows: &mut [TimeWindow],
    manifest: &UpgradeManifest,
) {
    let upgrade_start = manifest.upgrade_start.unwrap_or(f64::MAX);
    let upgrade_end = manifest.upgrade_end.unwrap_or(f64::MAX);

    for window in windows.iter_mut() {
        let label = if window.end <= upgrade_start {
            "pre-upgrade"
        } else if window.start >= upgrade_end {
            "post-upgrade"
        } else {
            "transition"
        };
        window.label = Some(label.to_string());
    }
}

/// Classify windows into periods and aggregate metrics.
pub fn aggregate_windows_by_label(
    windows: &[WindowedMetrics],
) -> HashMap<String, Vec<&WindowedMetrics>> {
    let mut by_label: HashMap<String, Vec<&WindowedMetrics>> = HashMap::new();

    for window in windows {
        let label = window
            .window
            .label
            .as_deref()
            .unwrap_or("unknown")
            .to_string();
        by_label.entry(label).or_default().push(window);
    }

    by_label
}

/// Calculate mean and standard deviation for a series of Option<f64> values.
pub fn calculate_stats(values: &[Option<f64>]) -> (Option<f64>, Option<f64>) {
    let valid: Vec<f64> = values.iter().filter_map(|v| *v).collect();

    if valid.is_empty() {
        return (None, None);
    }

    let n = valid.len() as f64;
    let mean = super::stats::mean(&valid);

    let std = if valid.len() > 1 {
        let variance = valid.iter().map(|v| (v - mean).powi(2)).sum::<f64>() / (n - 1.0);
        Some(variance.sqrt())
    } else {
        None
    };

    (Some(mean), std)
}

/// Perform a simple two-sample t-test (Welch's t-test).
///
/// Returns the p-value for the null hypothesis that the two samples have equal means.
pub fn welch_t_test(sample1: &[f64], sample2: &[f64]) -> Option<f64> {
    if sample1.len() < 2 || sample2.len() < 2 {
        return None;
    }

    let n1 = sample1.len() as f64;
    let n2 = sample2.len() as f64;

    let mean1 = sample1.iter().sum::<f64>() / n1;
    let mean2 = sample2.iter().sum::<f64>() / n2;

    let var1 = sample1.iter().map(|x| (x - mean1).powi(2)).sum::<f64>() / (n1 - 1.0);
    let var2 = sample2.iter().map(|x| (x - mean2).powi(2)).sum::<f64>() / (n2 - 1.0);

    let se = (var1 / n1 + var2 / n2).sqrt();
    if se == 0.0 {
        return None;
    }

    let t = (mean1 - mean2).abs() / se;

    // Welch-Satterthwaite degrees of freedom
    let df_num = (var1 / n1 + var2 / n2).powi(2);
    let df_denom = (var1 / n1).powi(2) / (n1 - 1.0) + (var2 / n2).powi(2) / (n2 - 1.0);
    let df = df_num / df_denom;

    // Two-tailed p-value from the Student's t distribution, computed exactly via
    // the regularized incomplete beta function. For large df we fall back to the
    // normal approximation as a fast path (the two distributions coincide there).
    let p = if df > 100.0 {
        2.0 * (1.0 - standard_normal_cdf(t))
    } else {
        student_t_two_tailed_p(t, df)
    };
    Some(p)
}

/// Two-tailed p-value for a Student's t statistic with `df` degrees of freedom.
///
/// Uses the identity P(|T| > t) = I_x(df/2, 1/2) with x = df / (df + t^2),
/// where I_x is the regularized incomplete beta function.
fn student_t_two_tailed_p(t: f64, df: f64) -> f64 {
    if df <= 0.0 {
        return f64::NAN;
    }
    let t = t.abs();
    let x = df / (df + t * t);
    regularized_incomplete_beta(df / 2.0, 0.5, x)
}

/// Regularized incomplete beta function I_x(a, b).
///
/// Numerical Recipes `betai`: uses the continued-fraction expansion (`betacf`)
/// together with the symmetry relation I_x(a, b) = 1 - I_{1-x}(b, a) for fast
/// convergence.
fn regularized_incomplete_beta(a: f64, b: f64, x: f64) -> f64 {
    if x <= 0.0 {
        return 0.0;
    }
    if x >= 1.0 {
        return 1.0;
    }

    // Beta prefactor bt = x^a * (1-x)^b / B(a, b), computed in log space.
    let ln_bt = ln_gamma(a + b) - ln_gamma(a) - ln_gamma(b)
        + a * x.ln()
        + b * (1.0 - x).ln();
    let bt = ln_bt.exp();

    if x < (a + 1.0) / (a + b + 2.0) {
        bt * betacf(a, b, x) / a
    } else {
        1.0 - bt * betacf(b, a, 1.0 - x) / b
    }
}

/// Continued-fraction evaluation for the incomplete beta function
/// (Numerical Recipes `betacf`, Lentz's algorithm).
fn betacf(a: f64, b: f64, x: f64) -> f64 {
    const MAXIT: usize = 200;
    const EPS: f64 = 3.0e-12;
    const FPMIN: f64 = 1.0e-300;

    let qab = a + b;
    let qap = a + 1.0;
    let qam = a - 1.0;
    let mut c = 1.0;
    let mut d = 1.0 - qab * x / qap;
    if d.abs() < FPMIN {
        d = FPMIN;
    }
    d = 1.0 / d;
    let mut h = d;

    for m in 1..=MAXIT {
        let m = m as f64;
        let m2 = 2.0 * m;

        // Even step of the recurrence.
        let aa = m * (b - m) * x / ((qam + m2) * (a + m2));
        d = 1.0 + aa * d;
        if d.abs() < FPMIN {
            d = FPMIN;
        }
        c = 1.0 + aa / c;
        if c.abs() < FPMIN {
            c = FPMIN;
        }
        d = 1.0 / d;
        h *= d * c;

        // Odd step of the recurrence.
        let aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2));
        d = 1.0 + aa * d;
        if d.abs() < FPMIN {
            d = FPMIN;
        }
        c = 1.0 + aa / c;
        if c.abs() < FPMIN {
            c = FPMIN;
        }
        d = 1.0 / d;
        let del = d * c;
        h *= del;
        if (del - 1.0).abs() < EPS {
            break;
        }
    }

    h
}

/// Natural log of the gamma function (Numerical Recipes `gammln`, Lanczos).
fn ln_gamma(xx: f64) -> f64 {
    const COF: [f64; 6] = [
        76.18009172947146,
        -86.50532032941677,
        24.01409824083091,
        -1.231739572450155,
        0.1208650973866179e-2,
        -0.5395239384953e-5,
    ];

    let x = xx;
    let mut y = xx;
    let tmp = x + 5.5 - (x + 0.5) * (x + 5.5).ln();
    let mut ser = 1.000000000190015;
    for c in COF.iter() {
        y += 1.0;
        ser += c / y;
    }
    -tmp + (2.5066282746310005 * ser / x).ln()
}

/// Standard normal CDF approximation (Abramowitz and Stegun)
fn standard_normal_cdf(x: f64) -> f64 {
    let a1 = 0.254829592;
    let a2 = -0.284496736;
    let a3 = 1.421413741;
    let a4 = -1.453152027;
    let a5 = 1.061405429;
    let p = 0.3275911;

    let sign = if x < 0.0 { -1.0 } else { 1.0 };
    let x = x.abs() / std::f64::consts::SQRT_2;

    let t = 1.0 / (1.0 + p * x);
    let y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * (-x * x).exp();

    0.5 * (1.0 + sign * y)
}

/// Determine if a change is statistically significant at p < 0.05.
pub fn is_significant(p_value: Option<f64>) -> bool {
    p_value.map(|p| p < 0.05).unwrap_or(false)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_create_time_windows() {
        let windows = create_time_windows(0.0, 300.0, 60.0);
        assert_eq!(windows.len(), 5);
        assert_eq!(windows[0].start, 0.0);
        assert_eq!(windows[0].end, 60.0);
        assert_eq!(windows[4].start, 240.0);
        assert_eq!(windows[4].end, 300.0);
    }

    #[test]
    fn test_time_window_contains() {
        let window = TimeWindow::new(100.0, 200.0);
        assert!(!window.contains(99.9));
        assert!(window.contains(100.0));
        assert!(window.contains(150.0));
        assert!(!window.contains(200.0)); // End is exclusive
    }

    #[test]
    fn test_calculate_stats() {
        let values = vec![Some(1.0), Some(2.0), Some(3.0), Some(4.0), Some(5.0)];
        let (mean, std) = calculate_stats(&values);
        assert!((mean.unwrap() - 3.0).abs() < 0.001);
        assert!((std.unwrap() - 1.5811).abs() < 0.01);
    }

    #[test]
    fn test_student_t_two_tailed_p() {
        // Reference two-tailed p-values from the Student's t distribution.
        assert!((student_t_two_tailed_p(2.228, 10.0) - 0.050).abs() < 1e-3);
        assert!((student_t_two_tailed_p(2.0, 10.0) - 0.0734).abs() < 1e-3);
        assert!((student_t_two_tailed_p(1.0, 5.0) - 0.363).abs() < 1e-3);
        assert!((student_t_two_tailed_p(12.706, 1.0) - 0.050).abs() < 1e-3);
        // Large df converges to the normal distribution.
        assert!((student_t_two_tailed_p(1.96, 1000.0) - 0.0501).abs() < 1e-3);
    }
}
