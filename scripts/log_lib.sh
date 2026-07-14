#!/bin/bash
#
# log_lib.sh - Shared logging vocabulary for MoneroSim shell scripts.
#
# Sourced by run_sim.sh, setup.sh, update.sh, start_here.sh, and
# scripts/check_sim.sh so they all speak the same log_* vocabulary instead
# of each re-inventing print_status/say/header/etc. Sources scripts/colors.sh
# itself — callers only need to source this file, not colors.sh directly.
#
# Formats are lifted verbatim from run_sim.sh (the most complete of the
# prior implementations, and the de-facto standard in archived run logs)
# plus check_sim.sh's section header. One deliberate change from
# run_sim.sh's original: log_err is RED (run_sim.sh had it yellow, which
# made errors indistinguishable from warnings at a glance).

# Guard against double-sourcing.
if [[ -n "${MONEROSIM_LOG_LIB_SOURCED:-}" ]]; then
    return 0 2>/dev/null || exit 0
fi
MONEROSIM_LOG_LIB_SOURCED=1

source "$(dirname "${BASH_SOURCE[0]}")/colors.sh"

# log_header <title>  - section banner: "=== title ===" (check_sim.sh style)
log_header() {
    echo -e "\n${BOLD}${CYAN}=== $1 ===${NC}"
}

# log_step <title>    - phase banner: blank line + "==> title" (run_sim.sh style)
log_step() {
    echo ""
    echo -e "${BOLD}${CYAN}==> $1${NC}"
}

# log_ok <msg>        - success line, indented, green
log_ok() {
    echo -e "  ${GREEN}$1${NC}"
}

# log_warn <msg>      - warning line, indented, yellow, "WARNING: " prefix
log_warn() {
    echo -e "  ${YELLOW}WARNING: $1${NC}"
}

# log_err <msg>       - error line, indented, red, "ERROR: " prefix
log_err() {
    echo -e "  ${RED}ERROR: $1${NC}"
}

# log_info <msg>      - plain indented line, no color
log_info() {
    echo -e "  $1"
}
