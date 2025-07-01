# MoneroSim

A configuration utility for Monero network simulations in Shadow.

## Overview

MoneroSim is a Rust-based tool designed to facilitate large-scale, discrete-event network simulations of the Monero cryptocurrency network using the Shadow simulator. It provides a structured approach to configuring and orchestrating Monero node simulations.

## Features

- YAML-based configuration system
- Command-line interface with clap
- Structured logging with env_logger
- Robust error handling with color-eyre
- Extensible configuration architecture

## Quick Start

### Prerequisites

- Rust 1.77 or later
- Cargo (Rust package manager)

### Building

```bash
cd monerosim
cargo build --release
```

### Running

```bash
# Run with a configuration file
./target/release/monerosim --config config.yaml

# Or with cargo
cargo run --release -- --config config.yaml
```

## Configuration

The tool expects a YAML configuration file with the following structure:

```yaml
general:
  stop_time: "2h"  # Simulation duration

monero:
  nodes: 8  # Number of Monero nodes to simulate
```

## Project Structure

- `src/main.rs` - Main application entry point and configuration parsing
- `Cargo.toml` - Project dependencies and metadata
- `config.yaml` - Sample configuration file

## Development

This project is designed to be extensible. The configuration system can be easily extended to support additional Monero-specific parameters and Shadow simulator integration.

## License

GPL-3
