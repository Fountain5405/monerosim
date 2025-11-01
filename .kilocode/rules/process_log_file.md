# Log File Processing

**Location**: `shadow.data/hosts/[hostname]/[logfile]`

## Processing Workflow

### 1. Check for Processed Logs
Look for `.processed_log` files first - skip processing if they exist.

### 2. Process Logs (If Needed)
```bash
source venv/bin/activate && python scripts/log_processor.py
```
Wait for completion before analysis.

### 3. Analysis Priority
1. **Start with `.processed_log`** files (summarized, efficient)
2. **Use grep on originals** for detailed investigation:
   ```bash
   grep "ERROR" shadow.data/hosts/node000/bash.1000.stdout
   grep -A 5 -B 5 "pattern" shadow.data/hosts/node000/bash.1000.stdout
   ```

## Critical Rules

**NEVER directly read raw logs** unless explicitly instructed
**ALWAYS use processed logs first** for analysis
**Reference source** when reporting: "Analyzed `.processed_log` file..." 
