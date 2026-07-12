//! Shared statistical helpers for the analysis pipeline.
//!
//! These consolidate mean/median/percentile/gini implementations that were
//! previously duplicated (and, in a couple of places, subtly wrong — bare
//! `[len / 2]` medians that ignored even-length inputs) across the analysis
//! modules.

/// Arithmetic mean of a slice. Returns `0.0` for an empty slice.
pub(crate) fn mean(values: &[f64]) -> f64 {
    if values.is_empty() {
        return 0.0;
    }
    values.iter().sum::<f64>() / values.len() as f64
}

/// Median of a slice. Even-length inputs return the average of the two middle
/// elements (the standard convention). Returns `0.0` for an empty slice.
pub(crate) fn median(values: &[f64]) -> f64 {
    if values.is_empty() {
        return 0.0;
    }
    let mut sorted = values.to_vec();
    sorted.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
    let mid = sorted.len() / 2;
    if sorted.len() % 2 == 0 {
        (sorted[mid - 1] + sorted[mid]) / 2.0
    } else {
        sorted[mid]
    }
}

/// The `p`th percentile (`p` in `0..=100`) via nearest-rank on the sorted
/// values. Returns `0.0` for an empty slice.
pub(crate) fn percentile(values: &[f64], p: f64) -> f64 {
    if values.is_empty() {
        return 0.0;
    }
    let mut sorted = values.to_vec();
    sorted.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
    let idx = ((p / 100.0) * (sorted.len() - 1) as f64).round() as usize;
    sorted[idx.min(sorted.len() - 1)]
}

/// Gini coefficient for a slice of non-negative values.
///
/// Returns `0.0` for empty input or when all values are zero (perfect
/// equality). The result ranges from `0.0` (perfect equality) toward `1.0`
/// (maximum concentration).
pub(crate) fn gini(values: &[f64]) -> f64 {
    if values.is_empty() {
        return 0.0;
    }

    let n = values.len() as f64;
    let mut sorted = values.to_vec();
    sorted.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));

    let sum: f64 = sorted.iter().sum();
    if sum == 0.0 {
        return 0.0;
    }

    let mut gini_sum = 0.0;
    for (i, &val) in sorted.iter().enumerate() {
        gini_sum += val * (2.0 * (i as f64 + 1.0) - n - 1.0);
    }

    gini_sum / (n * sum)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_mean() {
        assert_eq!(mean(&[]), 0.0);
        assert_eq!(mean(&[5.0]), 5.0);
        assert!((mean(&[1.0, 2.0, 3.0, 4.0]) - 2.5).abs() < 1e-9);
    }

    #[test]
    fn test_median_odd_and_even() {
        assert_eq!(median(&[]), 0.0);
        // Unsorted input, odd length -> middle element.
        assert_eq!(median(&[3.0, 1.0, 2.0]), 2.0);
        assert_eq!(median(&[5.0]), 5.0);
        // Even length -> average of the two middle elements.
        assert!((median(&[1.0, 2.0, 3.0, 4.0]) - 2.5).abs() < 1e-9);
        assert!((median(&[4.0, 1.0, 3.0, 2.0]) - 2.5).abs() < 1e-9);
    }

    #[test]
    fn test_percentile_edges() {
        assert_eq!(percentile(&[], 95.0), 0.0);
        let v = [1.0, 2.0, 3.0, 4.0, 5.0];
        assert_eq!(percentile(&v, 0.0), 1.0); // min
        assert_eq!(percentile(&v, 100.0), 5.0); // max
        assert_eq!(percentile(&v, 50.0), 3.0); // middle
    }

    #[test]
    fn test_gini_uniform_is_zero() {
        assert_eq!(gini(&[]), 0.0);
        assert_eq!(gini(&[0.0, 0.0, 0.0]), 0.0);
        assert!(gini(&[5.0, 5.0, 5.0, 5.0]).abs() < 1e-9);
    }

    #[test]
    fn test_gini_concentrated_approaches_one() {
        // 99 zeros and a single large value -> near-maximal concentration.
        let mut v = vec![0.0; 99];
        v.push(100.0);
        let g = gini(&v);
        assert!(g > 0.9, "expected concentrated gini near 1, got {}", g);
    }
}
