"""Entry point so `python3 -m agents.simulation_monitor` keeps working.

The orchestrator generates wrapper scripts that invoke the simulation
monitor agent with `python3 -m agents.simulation_monitor`. After
splitting the previous single-file module into a package, we need an
explicit __main__ so that invocation continues to resolve.
"""

from .agent import main

if __name__ == "__main__":
    main()
