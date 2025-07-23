# Monerosim

`monerosim` is a tool for generating configuration files for the Shadow network simulator to run Monero simulations. This document outlines the project's structure and design.

## Project Structure

The project is organized into several directories, each with a specific purpose. This structure is designed to be scalable and maintainable.

```
monerosim/
├── Cargo.toml
├── README.md
├── src/
│   ├── main.rs
│   ├── lib.rs
│   ├── config/
│   │   ├── mod.rs
│   │   ├── generator.rs
│   │   ├── shadow.rs
│   │   └── node.rs
│   ├── network/
│   │   ├── mod.rs
│   │   └── topology.rs
│   └── utils/
│       ├── mod.rs
│       └── fs.rs
├── templates/
│   ├── shadow.yaml.tera
│   └── node.yaml.tera
├── data/
├── docs/
└── scripts/
```

### Root Directory (`monerosim/`)

*   **`Cargo.toml`**: The Rust package manifest, containing metadata and dependencies for the project.
*   **`README.md`**: This file, providing an overview of the project and its design.

### Source Directory (`src/`)

This is the main directory for the Rust source code.

*   **`main.rs`**: The entry point of the application. It is responsible for parsing command-line arguments and orchestrating the configuration generation process.
*   **`lib.rs`**: The library entry point. It contains the core logic of `monerosim`, making it possible to use `monerosim` as a library in other projects.

#### Configuration Module (`src/config/`)

This module is responsible for handling the generation of configuration files.

*   **`mod.rs`**: Declares the `config` module.
*   **`generator.rs`**: Contains the main configuration generator, which coordinates the creation of all necessary configuration files.
*   **`shadow.rs`**: Contains the logic for generating the main `shadow.yaml` file from a template.
*   **`node.rs`**: Contains the logic for generating the configuration files for each individual Monero node.

#### Network Module (`src/network/`)

This module defines the network topology for the simulation.

*   **`mod.rs`**: Declares the `network` module.
*   **`topology.rs`**: Defines the data structures and logic for representing the network graph, including nodes, connections, and their properties.

#### Utilities Module (`src/utils/`)

This module contains utility functions used throughout the project.

*   **`mod.rs`**: Declares the `utils` module.
*   **`fs.rs`**: Provides filesystem-related utilities, such as reading from and writing to files.

### Templates Directory (`templates/`)

This directory holds the templates for the configuration files. A templating engine like Tera can be used to render these templates with dynamic data.

*   **`shadow.yaml.tera`**: The template for the main Shadow configuration file.
*   **`node.yaml.tera`**: The template for the configuration of an individual Monero node.

### Data Directory (`data/`)

This directory is for static data required by the application, such as genesis block information or default configuration parameters.

### Docs Directory (`docs/`)

This directory contains project documentation, such as design documents, user guides, and API documentation.

### Scripts Directory (`scripts/`)

This directory contains helper scripts for various tasks, such as building the project, running simulations, and analyzing simulation results.
