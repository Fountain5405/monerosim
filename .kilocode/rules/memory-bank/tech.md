# Monerosim Technology Stack

## Core Technologies

### Programming Languages

- **Rust**: Primary implementation language for the Monerosim tool
  - Used for configuration parsing, build management, and Shadow configuration generation
  - Provides memory safety and robust error handling
  - Version: Latest stable (1.70+)

- **Python**: Primary language for testing and monitoring scripts (pending verification)
  - Used for all test orchestration, monitoring, and automation
  - Provides better error handling and cross-platform compatibility than bash
  - Version: 3.6+ (3.8+ recommended)
  - Virtual environment established at `/home/lever65/monerosim_dev/monerosim/venv`

- **Bash**: Legacy scripting language, being phased out
  - Original testing scripts still available as fallback
  - Used for system-level operations (setup.sh, logfileprocessor.sh)
  - Version: 4.0+

### Frameworks and Libraries

#### Rust Dependencies
- **Clap**: Command-line argument parsing for Rust
  - Used for handling CLI options and arguments
  - Version: 4.0+

- **Serde**: Serialization/deserialization framework for Rust
  - Used for YAML configuration parsing
  - Version: 1.0+

- **Color-eyre**: Error handling and reporting library
  - Provides rich error context and backtraces
  - Version: 0.6+

#### Python Dependencies
- **requests**: HTTP library for RPC communication
  - Used for all Monero daemon and wallet RPC calls
  - Version: 2.25+

- **Standard Library Modules**:
  - `argparse`: Command-line argument parsing
  - `json`: JSON parsing and generation
  - `logging`: Structured logging with color support
  - `subprocess`: Process management
  - `typing`: Type hints for better code clarity
  - `unittest`: Testing framework

### External Dependencies

- **Shadow Network Simulator**: Discrete-event network simulator
  - Used to run the Monero network simulation
  - Version: 2.0+
  - Repository: https://github.com/shadow/shadow

- **Monero**: Privacy-focused cryptocurrency
  - Modified with Shadow compatibility patches
  - Repository: https://github.com/monero-project/monero
  - Custom fork: monero-shadow (with Shadow compatibility patches)

## Development Environment

### Build Requirements

- **Rust Toolchain**: 
  - rustc, cargo, rustfmt, clippy
  - Install via rustup: `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh`

- **Python Environment**:
  - Python 3.6+ (3.8+ recommended)
  - pip for package management
  - venv for virtual environments

- **Build Tools**:
  - CMake (3.10+)
  - GCC/Clang (C++17 compatible)
  - Make
  - Git

- **Shadow Dependencies**:
  - libc, libpthread, libevent, libglib, libigraph
  - Install via package manager (e.g., `apt-get install libevent-dev libglib2.0-dev libigraph-dev`)

### Development Workflow

1. **Setup**:
   - Clone the Monerosim repository
   - Run `./setup.sh` to install dependencies and prepare the environment
   - This script will also clone and patch the Monero source code
   - Set up Python virtual environment:
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     pip install -r scripts/requirements.txt
     ```

2. **Build**:
   - Run `cargo build --release` to build the Monerosim tool
   - The build process will compile both Monerosim and the Shadow-compatible Monero binaries

3. **Configuration**:
   - Edit `config.yaml` to define simulation parameters
   - Key parameters include:
     - Simulation duration
     - Node configurations
     - Mining settings

4. **Execution**:
   - Run `./target/release/monerosim --config config.yaml --output shadow_output`
   - This generates the Shadow configuration files
   - Run `shadow shadow_output/shadow.yaml` to start the simulation

5. **Testing**:
   - **Python Scripts (Pending Verification)**:
     - Use `python3 scripts/simple_test.py` for basic functionality testing
     - Use `python3 scripts/transaction_script.py` for transaction testing
     - Use `python3 scripts/sync_check.py` to verify network synchronization
     - Use `python3 scripts/monitor.py` for real-time monitoring
   - **Bash Scripts (Legacy/Fallback)**:
     - Use `simple_test.sh` for basic functionality testing
     - Use `sync_check.sh` to verify network synchronization

6. **Test Suite**:
   - Run all tests: `python3 scripts/run_all_tests.py`
   - Run with coverage: `python3 scripts/run_all_tests.py --coverage`
   - View coverage report: `open scripts/htmlcov/index.html`

## Python Virtual Environment

The project uses a Python virtual environment to manage dependencies:

- **Location**: `/home/lever65/monerosim_dev/monerosim/venv`
- **Activation**: `source venv/bin/activate`
- **Deactivation**: `deactivate`
- **Requirements**: Listed in `scripts/requirements.txt`

Benefits of using virtual environment:
- Isolated dependencies from system Python
- Reproducible development environment
- Easy dependency management
- No conflicts with other Python projects

## Deployment

### System Requirements

- **Operating System**: Linux (Ubuntu 20.04+ recommended)
- **CPU**: 4+ cores recommended for medium-sized simulations
- **Memory**: 8GB+ RAM (16GB+ recommended for larger simulations)
- **Storage**: 10GB+ free space for build artifacts and simulation data
- **Python**: 3.6+ (3.8+ recommended)

### Installation

The project can be installed using the provided setup script:

```bash
git clone <repository_url>
cd monerosim
./setup.sh

# Set up Python environment
python3 -m venv venv
source venv/bin/activate
pip install -r scripts/requirements.txt
```

This script handles:
- Installing system dependencies
- Setting up the Rust toolchain
- Cloning and patching Monero source code
- Building Shadow-compatible Monero binaries
- Building the Monerosim tool

## Technical Constraints

- **Shadow Compatibility**: Monero code must be patched for Shadow compatibility
  - Requires modifications to networking code
  - Must disable seed nodes and DNS checkpoints
  - Needs special handling for time-based operations

- **Simulation Scale**: 
  - Small simulations (1-10 nodes): Near real-time performance
  - Medium simulations (10-50 nodes): 2-5x slower than real-time
  - Large simulations (50+ nodes): Significantly slower, requires substantial resources

- **Network Fidelity**:
  - Shadow provides high-fidelity network simulation
  - Some real-world conditions may be difficult to simulate precisely
  - Latency and bandwidth can be configured but may not perfectly match real-world behavior

- **Python Script Verification**:
  - Python scripts are feature-complete but pending production verification
  - Bash scripts remain available as fallback until verification complete
  - Virtual environment ensures consistent execution environment