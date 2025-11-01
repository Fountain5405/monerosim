# Testing Simulation Behavior

**CRITICAL**: Simulation environment isolated - external scripts cannot access it during runtime.

## Two Testing Approaches

**1. Post-Simulation Analysis** (Recommended):
- Wait for simulation completion
- Analyze logs in `shadow.data/hosts/`
- Never use `tail -f` (resource intensive)
- Use processed logs (`.processed_log` files) first

**2. In-Simulation Monitoring**:
- Add monitoring agents to Shadow config
- Agents write logs internally
- Review logs post-simulation
- Example: `simulation_monitor.py` agent 

