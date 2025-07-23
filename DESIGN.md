# Monerosim Design

This document outlines the design for `monerosim`, a simulation tool for the Monero network.

## 1. High-Level Architecture

`monerosim` will be a Rust project composed of a library and a main binary.

*   **`monerosim-lib`**: A library containing the core logic for generating simulation configurations.
*   **`monerosim`**: A command-line tool that uses `monerosim-lib` to generate `shadow.yaml` files for Monero network simulations.

This separation of concerns follows the pattern of `ethshadow`, allowing the core logic to be tested independently and potentially used by other tools.

## 2. Directory Structure

The proposed directory structure for the `monerosim` project is as follows:

```
monerosim/
├── Cargo.toml
├── src/
│   └── main.rs
├── lib/
│   ├── Cargo.toml
│   └── src/
│       ├── lib.rs
│       ├── config/
│       │   ├── mod.rs
│       │   └── shadow.rs
│       ├── clients/
│       │   └── mod.rs
│       └── error.rs
└── DESIGN.md
```

*   **`monerosim/`**: The root of the `monerosim` project.
*   **`monerosim/Cargo.toml`**: The main Cargo manifest for the `monerosim` workspace.
*   **`monerosim/src/main.rs`**: The entry point for the `monerosim` command-line tool.
*   **`monerosim/lib/`**: The `monerosim-lib` crate.
*   **`monerosim/lib/Cargo.toml`**: The Cargo manifest for the `monerosim-lib` crate.
*   **`monerosim/lib/src/lib.rs`**: The main library file.
*   **`monerosim/lib/src/config/`**: Module for handling simulation configuration.
    *   `mod.rs`: Defines the main configuration structures, similar to `ethshadow`. It will parse a user-provided YAML file and generate the `shadow.yaml` file.
    *   `shadow.rs`: Contains the data structures that represent the `shadow.yaml` format.
*   **`monerosim/lib/src/clients/`**: Module for defining Monero client configurations.
    *   `mod.rs`: Will define a `Client` trait, similar to `ethshadow`, that each Monero client implementation will need to satisfy. This will allow for different Monero node implementations to be used in the simulation.
*   **`monerosim/lib/src/error.rs`**: Defines the error types for the library.
*   **`monerosim/DESIGN.md`**: This design document.

## 3. Main Components

### 3.1. Configuration (`config` module)

The `config` module will be responsible for parsing a user-provided configuration file (e.g., `monerosim.yaml`) and translating it into a `shadow.yaml` file that the Shadow simulator can understand.

The `monerosim.yaml` file will specify:

*   Network topology (e.g., number of nodes, their geographic distribution).
*   Monero client configurations (e.g., which client implementation to use, custom arguments).
*   Simulation duration and other Shadow-specific parameters.

### 3.2. Clients (`clients` module)

The `clients` module will define a generic `Client` trait for Monero nodes. This trait will provide an interface for generating the necessary configuration and command-line arguments for a specific Monero client (e.g., `monerod`).

Initially, we will support `monerod`, but the design will be extensible to support other clients in the future.

### 3.3. Main Binary (`monerosim`)

The `monerosim` binary will be a simple command-line tool that takes the path to a `monerosim.yaml` file as input and generates the corresponding `shadow.yaml` file.

## 4. Workflow

1.  The user creates a `monerosim.yaml` file to describe the desired simulation.
2.  The user runs the `monerosim` tool, passing the `monerosim.yaml` file.
3.  `monerosim` parses the configuration file.
4.  It then uses the `clients` module to generate the process definitions for each node in the simulation.
5.  Finally, it generates the `shadow.yaml` file.
6.  The user can then run the simulation using `shadow shadow.yaml`.

This design provides a solid foundation for `monerosim`, mirroring the successful architecture of `ethshadow` while being tailored for the Monero ecosystem.