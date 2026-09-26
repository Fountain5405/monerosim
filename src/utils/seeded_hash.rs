//! Deterministic, seeded hashing shared by every selection function that
//! needs a reproducible-but-well-mixed ordering over agent ids (unreachable
//! set, turnover set, node-implementation set, prefix-sharing set).

/// Stable FNV-1a hash of (seed, id) — deterministic and reproducible without
/// depending on std's (unstable across versions) hasher, so the same binary +
/// seed always selects the same set.
pub(crate) fn seeded_hash(seed: u64, s: &str) -> u64 {
    let mut h: u64 = 0xcbf2_9ce4_8422_2325 ^ seed;
    for b in s.bytes() {
        h ^= b as u64;
        h = h.wrapping_mul(0x0000_0100_0000_01b3);
    }
    h
}

/// splitmix64 finalizer: any 1-bit input change flips ~half the output bits,
/// giving well-distributed top bits regardless of key layout.
///
/// FNV-1a's avalanche in its *high* bits is poor when only a trailing byte
/// changes (e.g. the session index in `cs:<id>:<k>`, or a numeric id suffix in
/// `relay-001` vs `relay-002`) — sorting or bucketing on the raw FNV value
/// selects contiguous blocks of keys instead of a uniform sample. Always run
/// `seeded_hash` output through this finalizer before using it as a sort key
/// or a uniform draw.
pub(crate) fn finalize_hash(mut h: u64) -> u64 {
    h ^= h >> 30;
    h = h.wrapping_mul(0xbf58_476d_1ce4_e5b9);
    h ^= h >> 27;
    h = h.wrapping_mul(0x94d0_49bb_1331_11eb);
    h ^= h >> 31;
    h
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn seeded_hash_is_deterministic() {
        assert_eq!(seeded_hash(1, "a"), seeded_hash(1, "a"));
        assert_ne!(seeded_hash(1, "a"), seeded_hash(2, "a"));
    }

    #[test]
    fn finalize_hash_changes_with_one_bit() {
        assert_ne!(finalize_hash(0), finalize_hash(1));
    }
}
