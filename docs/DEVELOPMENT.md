# MoneroSim Development Guide

This document provides comprehensive guidance for developers working on MoneroSim, including setup, architecture, testing, and contribution guidelines.

## Development Environment Setup

### Prerequisites

1. **Rust Development Environment**
   ```bash
   # Install Rust (if not already installed)
   curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
   source ~/.cargo/env
   
   # Install required components
   rustup component add clippy rustfmt
   ```

2. **System Dependencies**
   ```bash
   # Ubuntu/Debian
   sudo apt-get install git cmake make gcc g++ pkg-config libssl-dev

   # Fedora/RHEL
   sudo dnf install git cmake make gcc gcc-c++ pkgconfig openssl-devel

   # Arch Linux
   sudo pacman -S git cmake make gcc pkgconf openssl
   ```

3. **Shadow Simulator**
   - Follow the official installation guide: https://shadow.github.io/docs/guide/install/
   - Ensure Shadow is in your PATH

### Repository Setup

```bash
# Clone the repository
git clone <repository-url>
cd monerosim

# Set up the monero-shadow repository (required for building)
cd ..
git clone <monero-shadow-repository-url> monero-shadow
cd monero-shadow
git checkout shadow-complete
cd ../monerosim

# Build MoneroSim
cargo build --release
```

## Project Structure

```
monerosim/
├── src/
│   ├── main.rs              # CLI entry point and orchestration
│   ├── config.rs            # Configuration parsing and validation
│   ├── build.rs             # Monero build management
│   └── shadow.rs            # Shadow configuration generation
├── patches/                 # Monero patches for simulation compatibility
├── builds/                  # Compiled Monero binaries (created during build)
├── docs/                    # Project documentation
├── config.yaml             # Default simulation configuration
├── setup.sh                # Automated setup script
├── Cargo.toml              # Rust dependencies and metadata
├── Cargo.lock              # Locked dependency versions
└── README.md               # Basic project information
```

## Code Architecture

### Module Overview

#### `main.rs`
- **Purpose**: CLI interface and main application orchestration
- **Key Functions**:
  - Command-line argument parsing
  - Configuration loading and validation
  - Build process coordination
  - Shadow configuration generation

#### `config.rs`
- **Purpose**: Configuration file parsing and data structures
- **Key Components**:
  - YAML parsing with serde
  - Configuration validation
  - Error handling and user feedback
  - Default value management

#### `build.rs`
- **Purpose**: Monero source code and binary management
- **Key Responsibilities**:
  - Git repository operations
  - Patch application
  - CMake configuration and building
  - Binary location and verification

#### `shadow.rs`
- **Purpose**: Shadow simulator configuration generation
- **Key Features**:
  - Network topology creation
  - IP address and port allocation
  - Shadow YAML configuration output
  - EthShadow compatibility

## Development Workflow

### 1. Making Changes

```bash
# Create a feature branch
git checkout -b feature/your-feature-name

# Make your changes
vim src/config.rs

# Test your changes
cargo test
cargo clippy
cargo fmt

# Build and test locally
cargo build --release
./target/release/monerosim --config config.yaml --output test_output
```

### 2. Code Quality

#### Formatting
```bash
# Format code
cargo fmt

# Check formatting
cargo fmt -- --check
```

#### Linting
```bash
# Run Clippy for lint warnings
cargo clippy -- -D warnings

# Fix common issues automatically
cargo clippy --fix
```

#### Testing
```bash
# Run unit tests
cargo test

# Run tests with output
cargo test -- --nocapture

# Run specific test
cargo test test_config_parsing
```

### 3. Building and Testing

#### Development Build
```bash
# Fast development build
cargo build

# Run with debug output
RUST_LOG=debug ./target/debug/monerosim --config config.yaml --output debug_output
```

#### Release Build
```bash
# Optimized release build
cargo build --release

# Performance testing
time ./target/release/monerosim --config config.yaml --output perf_test
```

## Testing Guidelines

### Unit Tests

Write unit tests for all public functions:

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_config_parsing() {
        let yaml = r#"
            general:
              stop_time: "10m"
            monero:
              nodes:
                - count: 5
                  name: "test"
        "#;
        
        let config: Config = serde_yaml::from_str(yaml).unwrap();
        assert_eq!(config.general.stop_time, "10m");
        assert_eq!(config.monero.nodes.len(), 1);
        assert_eq!(config.monero.nodes[0].count, 5);
        assert_eq!(config.monero.nodes[0].name, "test");
    }
}
```

### Integration Tests

Create integration tests in `tests/` directory:

```rust
// tests/integration_test.rs
use std::process::Command;
use tempfile::TempDir;

#[test]
fn test_full_simulation_generation() {
    let temp_dir = TempDir::new().unwrap();
    let output_path = temp_dir.path().join("test_output");
    
    let output = Command::new("./target/release/monerosim")
        .args(&["--config", "config.yaml", "--output", output_path.to_str().unwrap()])
        .output()
        .expect("Failed to execute monerosim");
    
    assert!(output.status.success());
    assert!(output_path.join("shadow.yaml").exists());
}
```

## Adding New Features

### 1. Adding Configuration Options

To add a new configuration option:

1. **Update the configuration struct** in `src/config.rs`:
   ```rust
   #[derive(Debug, Deserialize)]
   pub struct GeneralConfig {
       pub stop_time: String,
       pub new_option: Option<String>,  // Add your new option
   }
   ```

2. **Add validation logic** if needed:
   ```rust
   impl GeneralConfig {
       pub fn validate(&self) -> Result<(), String> {
           // Validate stop_time
           // ...
           
           // Validate new option
           if let Some(ref value) = self.new_option {
               if value.is_empty() {
                   return Err("new_option cannot be empty".to_string());
               }
           }
           
           Ok(())
       }
   }
   ```

3. **Update Shadow configuration generation** in `src/shadow.rs`:
   ```rust
   pub fn generate_shadow_config(config: &Config) -> Result<String, Box<dyn std::error::Error>> {
       // Use the new configuration option
       let new_value = config.general.new_option.as_deref().unwrap_or("default");
       
       // Include in Shadow config generation
       // ...
   }
   ```

4. **Add tests** and **update documentation**.

## Error Handling Guidelines

### 1. Use Result Types

Always use `Result<T, E>` for operations that can fail:

```rust
use color_eyre::Result;

pub fn parse_config(path: &str) -> Result<Config> {
    let content = std::fs::read_to_string(path)
        .wrap_err_with(|| format!("Failed to read config file: {}", path))?;
    
    let config: Config = serde_yaml::from_str(&content)
        .wrap_err("Failed to parse YAML configuration")?;
    
    config.validate()
        .wrap_err("Configuration validation failed")?;
    
    Ok(config)
}
```

### 2. Provide Helpful Error Messages

Include context and suggestions in error messages:

```rust
if !path.exists() {
    return Err(color_eyre::eyre::eyre!(
        "Configuration file not found: {}\n\
         Hint: Create a config.yaml file or specify a different path with --config",
        path.display()
    ));
}
```

## Contributing Guidelines

### 1. Commit Messages

Use conventional commit format:

```
feat: add support for custom network topologies

- Add NetworkTopology enum with Star, Mesh, Ring variants
- Implement topology generation functions
- Update configuration schema
- Add tests for new topology types

Closes #123
```

### 2. Pull Request Process

1. **Create an issue** describing the feature or bug
2. **Fork the repository** and create a feature branch
3. **Implement changes** with tests and documentation
4. **Ensure all tests pass** and code is formatted
5. **Submit pull request** with clear description
6. **Respond to review feedback** promptly

### 3. Code Review Checklist

- [ ] Code follows Rust best practices
- [ ] All tests pass (`cargo test`)
- [ ] Code is formatted (`cargo fmt`)
- [ ] No clippy warnings (`cargo clippy`)
- [ ] Documentation is updated
- [ ] New features have tests
- [ ] Error handling is appropriate
- [ ] Performance impact is considered

## Useful Development Commands

```bash
# Quick development cycle
cargo check                    # Fast syntax checking
cargo test                     # Run tests
cargo clippy                   # Lint checking
cargo fmt                      # Format code

# Performance analysis
cargo build --release          # Optimized build
time ./target/release/monerosim # Time execution

# Documentation
cargo doc --open               # Generate and view docs

# Dependency management
cargo update                   # Update dependencies
cargo audit                    # Security audit
```
