# Shadow Simulation Execution Protocol

When executing Shadow simulations, follow this protocol to ensure proper execution, logging, and monitoring.

## 1. Clean Previous Data

**CRITICAL**: Always clean up data from previous runs to prevent conflicts and ensure a clean state.

```bash
rm -rf shadow.data shadow.log
```

**CRITICAL**: Always make sure there are no current shadow processes running. 

## 2. Run the simulation

### Method C: Background Mode (for Long-Running Simulations)

This runs the simulation as a background process and saves all output to a log file. The terminal is immediately available for other commands. This is the recommended approach for long or non-interactive simulation runs.

```bash
rm -rf shadow.data && nohup shadow shadow_agents_output/shadow_agents.yaml > shadow.log 2>&1 &
```
*   `nohup`: Allows the process to continue running even if the terminal session is closed.
*   `&`: Puts the command into a background process.

## 3. Monitoring a Background Simulation

If you use Method C to run the simulation in the background, you can monitor its progress by "tailing" the log file:

```bash
tail shadow.log
```
This command will display the last few lines of the file. Run it occasionally to see where things are. You shouldn't just watch the logs constantly, this uses a lot of resources. 

**CRITICAL**: DO NOT USE "tail -f" to watch the logs. This uses too many resources.
