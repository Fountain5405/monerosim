//! Duration parsing utilities.
//!
//! This module provides utilities for parsing duration strings
//! (e.g., "3h", "30m") into appropriate formats.

/// Parse duration string (e.g., "5h", "30m", "1800s") to seconds
///
/// Supports various duration formats:
/// - Raw seconds: "1800"
/// - Seconds: "1800s", "1800sec", "1800secs", "1800second", "1800seconds"
/// - Minutes: "30m", "30min", "30mins", "30minute", "30minutes"
/// - Hours: "5h", "5hr", "5hrs", "5hour", "5hours"
///
/// # Arguments
/// * `duration` - The duration string to parse
///
/// Compound forms (e.g. `"5m30s"`) are NOT supported and are rejected with an
/// error rather than being silently mis-parsed — use a single unit instead.
///
/// # Returns
/// * `Ok(u64)` - The duration in seconds if parsing succeeds
/// * `Err(String)` - An error message if the string cannot be fully parsed
///
/// # Examples
/// ```
/// use monerosim::utils::duration::parse_duration_to_seconds;
///
/// assert_eq!(parse_duration_to_seconds("1800"), Ok(1800));
/// assert_eq!(parse_duration_to_seconds("30m"), Ok(1800));
/// assert_eq!(parse_duration_to_seconds("5h"), Ok(18000));
/// assert!(parse_duration_to_seconds("invalid").is_err());
/// assert!(parse_duration_to_seconds("5m30s").is_err());
/// ```
pub fn parse_duration_to_seconds(duration: &str) -> Result<u64, String> {
    let duration = duration.trim();

    // Split into a leading numeric part and a trailing unit suffix. Anything
    // left over that is neither (e.g. the "30s" in "5m30s") makes the whole
    // string invalid — we refuse to guess rather than return a wrong value.
    let num_str = extract_number_part(duration);
    let unit = &duration[num_str.len()..];

    // The numeric part must be present and fully valid.
    let value: f64 = num_str.parse().map_err(|_| {
        format!(
            "Invalid duration format: '{}' (expected a single value with an optional unit, e.g. '30s', '5m', '2h')",
            duration
        )
    })?;

    let seconds = match unit {
        "" => value, // raw seconds
        "s" | "sec" | "secs" | "second" | "seconds" => value,
        "m" | "min" | "mins" | "minute" | "minutes" => value * 60.0,
        "h" | "hr" | "hrs" | "hour" | "hours" => value * 3600.0,
        other => {
            return Err(format!(
                "Invalid duration '{}': unrecognized unit '{}'. Use a single unit like '30s', '5m', or '2h'; compound forms such as '5m30s' are not supported.",
                duration, other
            ));
        }
    };

    Ok(seconds as u64)
}

/// Extract the numeric part from a duration string by finding the first non-numeric character.
///
/// Uses `char_indices()` so the slice index is a valid byte boundary even when the
/// non-numeric character is multi-byte (UTF-8).
fn extract_number_part(duration: &str) -> &str {
    for (i, c) in duration.char_indices() {
        if !c.is_ascii_digit() && c != '.' {
            return &duration[0..i];
        }
    }
    duration // If all characters are digits/dots
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_duration_seconds() {
        // Test raw seconds
        assert_eq!(parse_duration_to_seconds("1800"), Ok(1800));
        assert_eq!(parse_duration_to_seconds("0"), Ok(0));
        assert_eq!(parse_duration_to_seconds("3600"), Ok(3600));

        // Test second formats
        assert_eq!(parse_duration_to_seconds("1800s"), Ok(1800));
        assert_eq!(parse_duration_to_seconds("1800sec"), Ok(1800));
        assert_eq!(parse_duration_to_seconds("1800secs"), Ok(1800));
        assert_eq!(parse_duration_to_seconds("1800second"), Ok(1800));
        assert_eq!(parse_duration_to_seconds("1800seconds"), Ok(1800));

        // Test minute formats
        assert_eq!(parse_duration_to_seconds("30m"), Ok(1800));
        assert_eq!(parse_duration_to_seconds("30min"), Ok(1800));
        assert_eq!(parse_duration_to_seconds("30mins"), Ok(1800));
        assert_eq!(parse_duration_to_seconds("30minute"), Ok(1800));
        assert_eq!(parse_duration_to_seconds("30minutes"), Ok(1800));
        assert_eq!(parse_duration_to_seconds("1m"), Ok(60));
        assert_eq!(parse_duration_to_seconds("30min"), Ok(1800));
        assert_eq!(parse_duration_to_seconds("30mins"), Ok(1800));
        assert_eq!(parse_duration_to_seconds("30minute"), Ok(1800));
        assert_eq!(parse_duration_to_seconds("30minutes"), Ok(1800));
        assert_eq!(parse_duration_to_seconds("1m"), Ok(60));

        // Test hour formats
        assert_eq!(parse_duration_to_seconds("5h"), Ok(18000));
        assert_eq!(parse_duration_to_seconds("5hr"), Ok(18000));
        assert_eq!(parse_duration_to_seconds("5hrs"), Ok(18000));
        assert_eq!(parse_duration_to_seconds("5hour"), Ok(18000));
        assert_eq!(parse_duration_to_seconds("5hours"), Ok(18000));

        // Test decimal values
        assert_eq!(parse_duration_to_seconds("2.5h"), Ok(9000));
        assert_eq!(parse_duration_to_seconds("1.5h"), Ok(5400));
        assert_eq!(parse_duration_to_seconds("0.5m"), Ok(30));

        // Test edge cases
        assert_eq!(parse_duration_to_seconds("1m"), Ok(60));
        assert_eq!(parse_duration_to_seconds("1h"), Ok(3600));
        assert_eq!(parse_duration_to_seconds("1s"), Ok(1));

        // Single-unit forms parse cleanly.
        assert_eq!(parse_duration_to_seconds("30s"), Ok(30));
        assert_eq!(parse_duration_to_seconds("5m"), Ok(300));
        assert_eq!(parse_duration_to_seconds("2h"), Ok(7200));

        // Test invalid formats
        assert!(parse_duration_to_seconds("").is_err());
        assert!(parse_duration_to_seconds("invalid").is_err());
        assert!(parse_duration_to_seconds("abc").is_err());
        assert!(parse_duration_to_seconds("5x").is_err());
        assert!(parse_duration_to_seconds("5minutesx").is_err());

        // Compound forms must be rejected, not silently mis-parsed
        // ("5m30s" previously returned 5 via the ends_with cascade).
        assert!(parse_duration_to_seconds("5m30s").is_err());
        assert!(parse_duration_to_seconds("1h30m").is_err());
    }

    #[test]
    fn test_extract_number_part_handles_multibyte_char_boundary() {
        // Regression for the char-index vs byte-index bug at duration.rs:70.
        // Before fix: `chars().enumerate()` yielded a char index, then sliced
        // the &str with that index — which panics if the non-numeric
        // character is multi-byte (e.g. CJK, emoji).
        assert_eq!(extract_number_part("3小时"), "3");
        assert_eq!(extract_number_part("12.5秒"), "12.5");
        assert_eq!(extract_number_part("100🦀"), "100");
    }
}
