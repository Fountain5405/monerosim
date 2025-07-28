# Task: Fix Python Script Exit Code Handling in Shadow YAML Generation

## Context
During our diagnostic analysis of MoneroSim simulations, we discovered that Python scripts executed through bash wrappers in Shadow are incorrectly reporting exit codes. When a Python script completes successfully with `sys.exit(0)`, the bash wrapper reports exit code 1 to Shadow, causing false simulation failures.

## Current Problem
The Shadow YAML generator currently creates process commands like this:
```yaml
- path: /bin/bash
  args: -c 'cd /home/lever65/monerosim_dev/monerosim && source venv/bin/activate && python3 scripts/transaction_script.py'
```

This command structure doesn't properly propagate the Python script's exit code to Shadow.

## Required Fix
Modify the Shadow YAML generation code in the MoneroSim Rust codebase to ensure all Python script executions properly handle exit codes. The generated commands should be:

```yaml
- path: /bin/bash
  args: -c 'cd /home/lever65/monerosim_dev/monerosim && source venv/bin/activate && python3 scripts/transaction_script.py || exit $?'
```

## Specific Instructions

1. **Locate the Shadow YAML generation code**:
   - Look in `src/shadow.rs` or similar files that generate Shadow configuration
   - Find where process commands are constructed, especially for test scripts

2. **Identify Python script executions**:
   - Look for patterns where Python scripts are executed through bash
   - This typically involves:
     - Activating a virtual environment (`source venv/bin/activate`)
     - Running Python scripts (`python3` or `python`)

3. **Implement the fix**:
   - For any command that executes Python through bash, append `|| exit $?` to ensure proper exit code propagation
   - Ensure this applies to all test scripts:
     - `simple_test.py`
     - `block_controller.py`
     - `transaction_script.py`
     - `sync_check.py`
     - `monitor.py`
     - Any other Python scripts

4. **Consider alternative approaches**:
   - If possible, investigate whether Shadow can execute Python scripts directly without bash wrappers
   - Consider using `exec` to replace the bash process: `exec python3 script.py`
   - Evaluate if the virtual environment activation can be handled differently

5. **Test the changes**:
   - Generate new Shadow YAML files
   - Verify that all Python script commands include proper exit code handling
   - Run a test simulation to confirm exit codes are correctly reported

## Example Code Pattern to Look For
```rust
// Current pattern (needs fixing):
format!("cd {} && source venv/bin/activate && python3 {}", 
        working_dir, script_path)

// Fixed pattern:
format!("cd {} && source venv/bin/activate && python3 {} || exit $?", 
        working_dir, script_path)
```

## Additional Considerations
- This fix should be applied systematically to ALL Python script executions
- Consider adding a helper function to generate Python execution commands with proper exit code handling
- Document this requirement for future script additions
- Consider adding a test to verify exit code propagation works correctly

## Success Criteria
- All generated Shadow YAML files contain Python commands with proper exit code handling
- Python scripts that exit with code 0 are correctly reported as successful by Shadow
- No false failures due to exit code mishandling
- The fix is applied at the source (generation) rather than requiring post-processing

## Background Information
This issue was discovered during simulation analysis where the transaction script completed successfully but was reported as failed by Shadow. The root cause is that bash doesn't automatically propagate the exit code of the last command in a `-c` string unless explicitly instructed to do so with `|| exit $?` or similar constructs.