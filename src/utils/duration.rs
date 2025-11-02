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
/// # Returns
/// * `Ok(u64)` - The duration in seconds if parsing succeeds
/// * `Err(String)` - An error message if parsing fails
///
/// # Examples
/// ```
/// use monerosim::utils::duration::parse_duration_to_seconds;
///
/// assert_eq!(parse_duration_to_seconds("1800"), Ok(1800));
/// assert_eq!(parse_duration_to_seconds("30m"), Ok(1800));
/// assert_eq!(parse_duration_to_seconds("5h"), Ok(18000));
/// assert!(parse_duration_to_seconds("invalid").is_err());
/// ```
pub fn parse_duration_to_seconds(duration: &str) -> Result<u64, String> {
    let duration = duration.trim();

    // Check for unit suffixes first (check longer suffixes before shorter ones)
    // Hours
    if duration.ends_with("hours") || duration.ends_with("hour") || duration.ends_with("hrs") || duration.ends_with("hr") || duration.ends_with("h") {
        let num_str = extract_number_part(duration);
        if let Ok(hours) = num_str.parse::<u64>() {
            return Ok(hours * 3600);
        }
    }

    // Minutes
    if duration.ends_with("minutes") || duration.ends_with("minute") || duration.ends_with("mins") || duration.ends_with("min") || duration.ends_with("m") {
        let num_str = extract_number_part(duration);
        if let Ok(minutes) = num_str.parse::<u64>() {
            return Ok(minutes * 60);
        }
    }

    // Seconds
    if duration.ends_with("seconds") || duration.ends_with("second") || duration.ends_with("secs") || duration.ends_with("sec") || duration.ends_with("s") {
        let num_str = extract_number_part(duration);
        if let Ok(seconds) = num_str.parse::<u64>() {
            return Ok(seconds);
        }
    }

    // Only try raw seconds parsing if no unit suffix is found
    if let Ok(seconds) = duration.parse::<u64>() {
        return Ok(seconds);
    }

    Err(format!("Invalid duration format: {}", duration))
}

/// Extract the numeric part from a duration string by finding the first non-digit character
fn extract_number_part(duration: &str) -> &str {
    for (i, c) in duration.chars().enumerate() {
        if !c.is_ascii_digit() {
            return &duration[0..i];
        }
    }
    duration // If all characters are digits
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

        // Test edge cases
        assert_eq!(parse_duration_to_seconds("1m"), Ok(60));
        assert_eq!(parse_duration_to_seconds("1h"), Ok(3600));
        assert_eq!(parse_duration_to_seconds("1s"), Ok(1));

        // Test invalid formats
        assert!(parse_duration_to_seconds("").is_err());
        assert!(parse_duration_to_seconds("invalid").is_err());
        assert!(parse_duration_to_seconds("5x").is_err());
        assert!(parse_duration_to_seconds("5minutesx").is_err());
    }
}
