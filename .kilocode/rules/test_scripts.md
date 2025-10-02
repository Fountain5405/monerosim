# Shadow Simulation Test Scripts

When trying to analyze how the simulation is functioning, use these approaches. 

**CRITICAL**: The simulation environment is not accessible to scripts outside of the simulation. 

# Option 1 - Wait for the simulation to end

If you wait for the simulation to end, you can analyze all of the log files.
Do not use "tail -f" to watch the logs. This uses too many resources. 

# Option 2 - Design scripts to run inside of the shadow simulation

You can create scripts that can run inside of the shadow simulation. You have to make sure that the shadow config files will launch the script.
You can then monitor the output of these test scripts via the logs they produce. 

