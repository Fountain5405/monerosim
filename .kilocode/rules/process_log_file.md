# process_log_file.md

This rule tells you how to handle log files efficiently.

## How to Process Log Files

The log files are located in individual folders for each host in shadow.data/hosts/[name_of_host]/[name_of_log_file]

### First, Prepare the Log Files:
1. If the files have already been processed, do not run the log processor script again. You only need to run this once after the simulation has finished. If you have already processed the logs, you can proceed to analysis. 

2. **Activate the Python virtual environment and run the Python log processor**:
   ```bash
   source venv/bin/activate && python scripts/log_processor.py
   ```

3. **Wait for the processor to finish completely** before proceeding with analysis.

### Second, Analyze the Prepared Logs:

1. **ALWAYS look for `.processed_log` files first** when analyzing logs. These are the summarized versions created by the Python processor.

2. **Treat `.processed_log` files as your primary source** for initial analysis and getting a quick overview.

3. **You can access original log files directly when needed** for detailed investigation or use grep commands to find specific context:
   ```bash
   # Find specific patterns in original logs
   grep "ERROR" shadow.data/hosts/node000/bash.1000.stdout
   
   # Find context around specific log entries
   grep -A 5 -B 5 "specific_pattern" shadow.data/hosts/node000/bash.1000.stdout
   ```

## Critical Instructions for Kilo Code

**YOU MUST FOLLOW THIS EXACT WORKFLOW** when log analysis is required:

1. **Before reading ANY log file**, check to see if there are already processed log files available (visible as .processed_log). If not, run the Python log processor:
   ```bash
   source venv/bin/activate && python scripts/log_processor.py
   ```

2. **ALWAYS check for `.processed_log` files first** when analyzing logs.

3. **When referencing logs in your responses**, explicitly state you're using the processed version:
   "I've analyzed the processed log file `shadow.data/hosts/node000/bash.1000.stdout.processed_log` which shows..."

4. **Access original log files directly when detailed investigation is needed**.

5. **NEVER DIRECTLY INGEST UNPROCESSED LOG FILES UNLESS EXPLICITY INSTRUCTED TO BY THE USER**
   Instead use grep to look for specific lines if needed. But always start with the processed log files. 
