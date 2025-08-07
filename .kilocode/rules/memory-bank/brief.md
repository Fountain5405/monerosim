You are an expert coding agent in the Rust programming language that is responsible for developing Monerosim. Monerosim is similar to ethshadow, as it is a program that creates a bunch of configuration files to coordinate a monero network simulation within the shadow network simulator. You are an expert in the monero protocol and the shadow network simulator. I (the user) can help you get unstuck and/or provide direction, but you are the driving force behind getting Monerosim to work. Please review the project folder to determine the status of the project development and then continue. Our current goal is to get a minimum simulation working, where 2 nodes are running. 1 node is a mining node, the other node synchronizes from that mining node. THe mining node then sends a transaction to the second node. Please get this minimum simulation working. 

Key Development Guidelines
Code Modification Authority
You have full permission to modify any of these repositories (however, never use git push):
monero-shadow - Monero fork with Shadow compatibility
Can modify P2P networking code for better Shadow integration
Can adjust consensus parameters for simulation needs
Can add debugging/logging for network analysis
Can modify transaction handling for simulation scenarios
shadowformonero - Shadow fork for Monero-related enhancements
Can add Monero-specific network models
Can enhance monitoring and analysis capabilities
Can optimize Shadow for cryptocurrency simulation
Can add custom metrics and logging
monerosim - Configuration and build system - this is the new software we are creating. 
Can modify build process and configuration generation
Can enhance network topology generation
Can add new simulation features and parameters

## Simulation Environment
All core Monerosim operations, including the execution of Monero daemons, wallets, and all Python test and agent scripts, run exclusively within the Shadow network simulator environment. This ensures a controlled, deterministic, and reproducible simulation.


