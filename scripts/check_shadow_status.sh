#!/bin/bash

# Robust Shadow Simulation Status Checker
# This script provides multiple methods to determine if a Shadow simulation is still running

# Configuration
SHADOW_CONFIG="shadow_output/shadow_agents.yaml"
LOG_FILE="shadow.log"
PID_FILE="shadow.pid"
CHECK_INTERVAL=30

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check if Shadow is running by PID
check_by_pid() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0  # Running
        else
            rm -f "$PID_FILE"  # Clean up stale PID file
            return 1  # Not running
        fi
    fi
    return 1  # No PID file
}

# Function to check if Shadow is running by process name
check_by_process() {
    # Look for shadow processes, excluding grep itself
    if pgrep -f "shadow.*shadow_agents.yaml" > /dev/null 2>&1; then
        return 0  # Running
    fi
    return 1  # Not running
}

# Function to check if Shadow is still writing to log
check_log_activity() {
    if [ -f "$LOG_FILE" ]; then
        # Get the last modification time of the log file
        local last_modified=$(stat -c %Y "$LOG_FILE" 2>/dev/null || echo 0)
        local current_time=$(date +%s)
        local time_diff=$((current_time - last_modified))
        
        # If log was modified in the last 2 minutes, consider it active
        if [ "$time_diff" -lt 120 ]; then
            return 0  # Active
        fi
    fi
    return 1  # Inactive or no log
}

# Function to check if simulation completed successfully
check_completion_status() {
    if [ -f "$LOG_FILE" ]; then
        # Look for completion indicators in the log
        if grep -q "Simulation terminated" "$LOG_FILE" 2>/dev/null; then
            return 0  # Completed
        fi
        if grep -q "managed processes in unexpected final state" "$LOG_FILE" 2>/dev/null; then
            return 0  # Completed (with expected warning)
        fi
    fi
    return 1  # Not completed
}

# Function to wait for simulation completion
wait_for_completion() {
    echo -e "${GREEN}Starting Shadow simulation monitoring...${NC}"
    echo "Checking every $CHECK_INTERVAL seconds"
    
    # Store initial PID if available
    local initial_pid=$(pgrep -f "shadow.*shadow_agents.yaml" | head -1)
    if [ -n "$initial_pid" ]; then
        echo "$initial_pid" > "$PID_FILE"
        echo "Shadow PID: $initial_pid"
    else
        echo -e "${YELLOW}No Shadow process found initially. Will continue monitoring...${NC}"
    fi
    
    local check_count=0
    while true; do
        check_count=$((check_count + 1))
        
        # Check multiple indicators
        local pid_running=false
        local process_running=false
        local log_active=false
        
        if check_by_pid; then
            pid_running=true
        fi
        
        if check_by_process; then
            process_running=true
        fi
        
        if check_log_activity; then
            log_active=true
        fi
        
        # If no PID file exists but process is running, create PID file
        if [ "$pid_running" = false ] && [ "$process_running" = true ]; then
            local current_pid=$(pgrep -f "shadow.*shadow_agents.yaml" | head -1)
            if [ -n "$current_pid" ]; then
                echo "$current_pid" > "$PID_FILE"
                echo "Created PID file for Shadow process: $current_pid"
                pid_running=true
            fi
        fi
        
        # Check if simulation completed
        if check_completion_status; then
            echo -e "${GREEN}Simulation completed successfully!${NC}"
            rm -f "$PID_FILE"
            return 0
        fi
        
        # If no indicators show activity, simulation likely ended
        if [ "$pid_running" = false ] && [ "$process_running" = false ] && [ "$log_active" = false ]; then
            echo -e "${YELLOW}No simulation activity detected. Checking completion status...${NC}"
            sleep 5  # Brief pause to allow for final log writes
            
            if check_completion_status; then
                echo -e "${GREEN}Simulation completed successfully!${NC}"
            else
                echo -e "${RED}Simulation appears to have stopped without completion markers.${NC}"
                echo "Check the log file: $LOG_FILE"
            fi
            rm -f "$PID_FILE"
            return 0
        fi
        
        # Status update
        if [ $((check_count % 2)) -eq 0 ]; then  # Every other check
            echo -e "${YELLOW}Simulation still running... (check #$check_count)${NC}"
            if [ "$pid_running" = true ]; then
                echo "  - PID check: Active"
            fi
            if [ "$process_running" = true ]; then
                echo "  - Process check: Active"
            fi
            if [ "$log_active" = true ]; then
                echo "  - Log activity: Active"
            fi
        fi
        
        sleep "$CHECK_INTERVAL"
    done
}

# Function to check current status without waiting
check_status() {
    echo "Shadow Simulation Status Check:"
    echo "=============================="
    
    # Check if PID file exists but process is running, create it
    if [ ! -f "$PID_FILE" ] && check_by_process; then
        local current_pid=$(pgrep -f "shadow.*shadow_agents.yaml" | head -1)
        if [ -n "$current_pid" ]; then
            echo "$current_pid" > "$PID_FILE"
            echo "Created PID file for Shadow process: $current_pid"
        fi
    fi
    
    if check_by_pid; then
        echo -e "PID Check: ${GREEN}Running${NC} ($(cat $PID_FILE))"
    else
        echo -e "PID Check: ${RED}Not Running${NC}"
    fi
    
    if check_by_process; then
        echo -e "Process Check: ${GREEN}Running${NC}"
    else
        echo -e "Process Check: ${RED}Not Running${NC}"
    fi
    
    if check_log_activity; then
        echo -e "Log Activity: ${GREEN}Active${NC}"
    else
        echo -e "Log Activity: ${RED}Inactive${NC}"
    fi
    
    if check_completion_status; then
        echo -e "Completion Status: ${GREEN}Completed${NC}"
    else
        echo -e "Completion Status: ${YELLOW}Not Completed${NC}"
    fi
}

# Main script logic
case "${1:-wait}" in
    "wait")
        wait_for_completion
        ;;
    "check")
        check_status
        ;;
    "help"|"-h"|"--help")
        echo "Usage: $0 [wait|check|help]"
        echo "  wait  - Wait for simulation to complete (default)"
        echo "  check - Check current status without waiting"
        echo "  help  - Show this help message"
        ;;
    *)
        echo "Unknown option: $1"
        echo "Use '$0 help' for usage information"
        exit 1
        ;;
esac