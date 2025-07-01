# MoneroSim Code Structure

This document explains the structure and purpose of each component in the MoneroSim project.

## Project Overview

MoneroSim is designed as a configuration utility for Monero network simulations using the Shadow simulator. The project follows a modular architecture inspired by the ethshadow project.

## File Structure

```
monerosim/
├── Cargo.toml          # Project dependencies and metadata
├── src/
│   └── main.rs         # Main application entry point
├── config.yaml         # Sample configuration file
├── test_config.yaml    # Test configuration file
├── README.md           # Project documentation
└── CODE_STRUCTURE.md   # This file
```

## Core Components

### 1. Cargo.toml

The project manifest file that defines:
- **Project metadata**: name, version, edition, license
- **Dependencies**: 
  - `clap` with derive feature for command-line argument parsing
  - `serde` and `serde_yaml` for YAML configuration parsing
  - `log` and `env_logger` for structured logging
  - `color-eyre` for enhanced error handling
  - `thiserror` for custom error types
  - `humantime-serde` for human-readable time parsing

### 2. src/main.rs

The main application file containing:

#### Command-Line Interface (Args struct)
```rust
#[derive(Parser, Debug)]
struct Args {
    #[arg(short, long)]
    config: PathBuf,
}
```
- Uses clap's derive feature for automatic CLI generation
- Accepts a required `--config` argument for the YAML file path

#### Configuration Structures
```rust
struct Config {
    pub general: GeneralConfig,
    pub monero: MoneroConfig,
}

struct GeneralConfig {
    pub stop_time: String,
}

struct MoneroConfig {
    pub nodes: u32,
}
```
- **Config**: Top-level configuration container
- **GeneralConfig**: General simulation parameters (stop time)
- **MoneroConfig**: Monero-specific parameters (number of nodes)
- All structs implement `Serialize`, `Deserialize`, and `Default` traits

#### Main Function Flow
1. **Parse arguments**: Extract configuration file path
2. **Initialize logging**: Set up env_logger with info level
3. **Load configuration**: Read and parse YAML file
4. **Log results**: Display parsed configuration values
5. **Error handling**: Robust error handling with color-eyre

#### Configuration Loading Function
```rust
fn load_config(config_path: &PathBuf) -> Result<Config>
```
- Opens and reads the YAML file
- Deserializes content into Config struct
- Provides detailed error messages for debugging

### 3. Configuration Files

#### config.yaml
- Main sample configuration file
- Demonstrates the expected YAML structure
- Contains realistic values for testing

#### test_config.yaml
- Alternative configuration for testing
- Shows different parameter values
- Validates configuration flexibility

## Design Principles

### 1. Error Handling
- Uses `color-eyre` for enhanced error reporting
- Provides context-aware error messages
- Graceful handling of file I/O and parsing errors

### 2. Logging
- Structured logging with the `log` crate
- Configurable log levels via environment variables
- Informative messages for debugging and monitoring

### 3. Configuration
- YAML-based configuration for human readability
- Strongly typed configuration structures
- Default values for optional parameters
- Extensible design for future parameters

### 4. Command-Line Interface
- Clean, intuitive CLI using clap
- Automatic help generation
- Type-safe argument parsing

## Future Extensions

The current structure is designed to be easily extensible:

1. **Additional Configuration Fields**: New fields can be added to the config structs
2. **Shadow Integration**: Configuration can be extended to include Shadow-specific parameters
3. **Monero Protocol**: Monero-specific parameters can be added to MoneroConfig
4. **Validation**: Configuration validation logic can be added
5. **Multiple Configuration Sources**: Support for environment variables, command-line overrides

## Testing Strategy

While Rust/Cargo is not currently available on this system, the code is designed to be testable:

1. **Unit Tests**: Individual functions can be tested
2. **Integration Tests**: Configuration parsing can be tested
3. **Property Tests**: Configuration validation can be tested
4. **Manual Testing**: YAML files are validated for syntax correctness

## Next Steps

1. Install Rust toolchain for compilation and testing
2. Add configuration validation logic
3. Integrate with Shadow simulator APIs
4. Add Monero protocol-specific configuration options
5. Implement simulation orchestration logic 