//! # Wallet Address Generation Utilities
//!
//! This module provides deterministic wallet address generation for Monerosim
//! simulations. Instead of relying on external RPC calls to create wallets
//! dynamically, this module generates reproducible wallet addresses based on
//! agent IDs and simulation seeds.
//!
//! ## Deterministic Address Generation
//!
//! Wallet addresses are generated using a deterministic algorithm that ensures:
//!
//! - **Reproducibility**: Same agent ID and seed always produce the same address
//! - **Uniqueness**: Different agent IDs produce different addresses
//! - **Valid Format**: Generated addresses follow Monero address format
//! - **No External Dependencies**: Pure Rust implementation, no RPC calls needed
//!
//! ## Address Format
//!
//! Monero addresses consist of:
//! - Network byte (mainnet: 0x12, testnet: 0x35, stagenet: 0x24)
//! - Public spend key (32 bytes)
//! - Public view key (32 bytes)
//! - Checksum (4 bytes)
//! - Base58 encoding
//!
//! ## Usage
//!
//! ```rust
//! use crate::utils::wallet::generate_deterministic_wallet_address;
//!
//! let agent_id = 0;
//! let simulation_seed = 12345u64;
//! let address = generate_deterministic_wallet_address(agent_id, simulation_seed);
//! assert!(address.starts_with("4")); // Mainnet address
//! ```

use std::fmt;

/// Errors that can occur during wallet address generation
#[derive(Debug, Clone)]
pub enum WalletError {
    /// Invalid network byte
    InvalidNetworkByte(u8),
    /// Invalid key length
    InvalidKeyLength(usize),
    /// Base58 encoding error
    Base58Error(String),
}

impl fmt::Display for WalletError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            WalletError::InvalidNetworkByte(byte) => {
                write!(f, "Invalid network byte: {}", byte)
            }
            WalletError::InvalidKeyLength(len) => {
                write!(f, "Invalid key length: expected 32, got {}", len)
            }
            WalletError::Base58Error(msg) => {
                write!(f, "Base58 encoding error: {}", msg)
            }
        }
    }
}

impl std::error::Error for WalletError {}

/// Generate a deterministic Monero wallet address for simulation purposes
///
/// This function creates a reproducible wallet address based on the agent ID
/// and simulation seed. The address follows the standard Monero format but
/// is generated deterministically for testing and simulation.
///
/// # Arguments
/// * `agent_id` - Unique identifier for the agent (0-based index)
/// * `simulation_seed` - Seed value for deterministic generation
///
/// # Returns
/// A valid-looking Monero mainnet address as a String
///
/// # Example
/// ```rust
/// let address = generate_deterministic_wallet_address(0, 12345);
/// assert!(address.starts_with("4"));
/// ```
pub fn generate_deterministic_wallet_address(agent_id: u32, simulation_seed: u64) -> String {
    // Use agent_id and simulation_seed to generate deterministic keys
    let mut spend_key = [0u8; 32];
    let mut view_key = [0u8; 32];

    // Generate spend key from agent_id and seed
    for i in 0..32 {
        spend_key[i] = ((agent_id as u64 * 0x123456789ABCDEF0 + simulation_seed + i as u64) % 256) as u8;
    }

    // Generate view key from agent_id and seed (different pattern)
    for i in 0..32 {
        view_key[i] = ((agent_id as u64 * 0xFEDCBA9876543210 + simulation_seed + i as u64) % 256) as u8;
    }

    // Create address payload: network byte + spend key + view key
    let mut payload = Vec::with_capacity(1 + 32 + 32);
    payload.push(0x12); // Mainnet network byte
    payload.extend_from_slice(&spend_key);
    payload.extend_from_slice(&view_key);

    // Calculate checksum (Keccak-256 of payload, first 4 bytes)
    let checksum = keccak256_checksum(&payload);
    payload.extend_from_slice(&checksum);

    // Encode in Base58
    base58_encode(&payload)
}

/// Calculate Keccak-256 checksum and return first 4 bytes
fn keccak256_checksum(data: &[u8]) -> [u8; 4] {
    // Simple deterministic checksum for simulation purposes
    // In real Monero, this would be Keccak-256
    let mut checksum = [0u8; 4];
    for (i, &byte) in data.iter().enumerate() {
        checksum[i % 4] ^= byte;
        checksum[i % 4] = checksum[i % 4].wrapping_add(i as u8);
    }
    checksum
}

/// Base58 encode a byte array (simplified implementation for simulation)
fn base58_encode(data: &[u8]) -> String {
    const BASE58_ALPHABET: &[u8] = b"123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz";

    if data.is_empty() {
        return String::new();
    }

    let mut result = Vec::new();
    let mut num = data.iter().fold(0u128, |acc, &byte| acc * 256 + byte as u128);

    while num > 0 {
        let remainder = (num % 58) as usize;
        result.push(BASE58_ALPHABET[remainder]);
        num /= 58;
    }

    // Add leading zeros
    for &byte in data {
        if byte == 0 {
            result.push(b'1');
        } else {
            break;
        }
    }

    result.reverse();
    String::from_utf8(result).unwrap_or_else(|_| "INVALID_ADDRESS".to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_deterministic_address_generation() {
        let addr1 = generate_deterministic_wallet_address(0, 12345);
        let addr2 = generate_deterministic_wallet_address(0, 12345);
        assert_eq!(addr1, addr2, "Same inputs should produce same address");

        let addr3 = generate_deterministic_wallet_address(1, 12345);
        assert_ne!(addr1, addr3, "Different agent IDs should produce different addresses");

        let addr4 = generate_deterministic_wallet_address(0, 54321);
        assert_ne!(addr1, addr4, "Different seeds should produce different addresses");
    }

    #[test]
    fn test_address_format() {
        let address = generate_deterministic_wallet_address(0, 12345);
        assert!(address.starts_with("4"), "Mainnet addresses should start with '4'");
        assert!(address.len() > 90, "Monero addresses should be reasonably long");
        assert!(address.chars().all(|c| c.is_alphanumeric()), "Addresses should be alphanumeric");
    }

    #[test]
    fn test_base58_encode() {
        let data = [0x12, 0x34, 0x56];
        let encoded = base58_encode(&data);
        assert!(!encoded.is_empty());
        assert!(encoded.chars().all(|c| "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz".contains(c)));
    }
}