#!/usr/bin/env bash
#
# start_here.sh — interactive onboarding wizard for Monerosim.
#
# Designed for users who'd rather be walked through the workflow than read
# the docs. Power users: see QUICKSTART.md, docs/, or call ./run_sim.sh,
# scripts/scenario_parser.py, scripts/generate_config.py, or scripts/ai_config
# directly — no wizard needed.

set -u

# ---------- pretty output ----------
BOLD='\033[1m'
DIM='\033[2m'
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

say()  { printf "%b\n" "$*"; }
info() { printf "${CYAN}%s${NC}\n" "$*"; }
ok()   { printf "${GREEN}%s${NC}\n" "$*"; }
warn() { printf "${YELLOW}%s${NC}\n" "$*"; }
err()  { printf "${RED}%s${NC}\n" "$*"; }
hr()   { printf "${DIM}%s${NC}\n" "----------------------------------------------------------------------"; }

# Clear + title bar — every screen starts with this so terminals don't fill up.
screen() {
    clear 2>/dev/null || true
    hr
    printf "%b\n" "${BOLD}$1${NC}"
    hr
}

pause() {
    local prompt="${1:-Press Enter to continue...}"
    say ""
    read -r -p "$prompt " _
}

# Always run from the repo root so relative paths work.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

MONEROSIM_BIN="$HOME/.monerosim/bin"
SCENARIO_TEMPLATE="test_configs/quickstart.scenario.yaml"
CONFIG_TEMPLATE="test_configs/quickstart.yaml"

# ---------- setup detection ----------
is_installed() {
    [[ -x "$MONEROSIM_BIN/shadow" ]] \
        && [[ -x "$MONEROSIM_BIN/monerod" ]] \
        && [[ -x "$MONEROSIM_BIN/monero-wallet-rpc" ]] \
        && [[ -x "./target/release/monerosim" ]] \
        && [[ -d "./venv" ]]
}

prompt_run_setup() {
    screen "Setup required"
    say "${BOLD}setup.sh${NC} installs system deps, builds Shadow and Monero from"
    say "source, sets up a Python venv, and puts binaries in ~/.monerosim/bin/."
    say "First run takes 30-60 minutes."
    say ""
    read -r -p "Run ./setup.sh now? [y/N] " ans
    if [[ "$ans" =~ ^[Yy] ]]; then
        ./setup.sh
        local rc=$?
        if [[ $rc -ne 0 ]]; then
            err "setup.sh exited with code $rc. Re-run this wizard once it completes."
            exit $rc
        fi
        ok "Setup done."
        sleep 1
    else
        say ""
        info "When ready: ./setup.sh    then: ./start_here.sh"
        exit 0
    fi
}

# ---------- editor helper ----------
open_in_editor() {
    local file="$1"
    local ed="${EDITOR:-${VISUAL:-}}"
    if [[ -z "$ed" ]]; then
        if   command -v nano >/dev/null 2>&1; then ed=nano
        elif command -v vim  >/dev/null 2>&1; then ed=vim
        elif command -v vi   >/dev/null 2>&1; then ed=vi
        else
            warn "No editor found. Set \$EDITOR or open this file yourself:"
            say  "  $file"
            return 1
        fi
    fi
    info "Opening $file in $ed..."
    "$ed" "$file"
}

# ---------- learn walkthrough (4 short screens) ----------
learn_walkthrough() {
    screen "What is Monerosim? (1/4)"
    say "A suite of tools to run Monero networks (miners, users, relays) inside"
    say "Shadow, a discrete-event network simulator. The whole network runs on"
    say "one machine in scaled-up time, with the same simulation_seed in every"
    say "run — so it ${BOLD}aims${NC} to be reproducible, though several known issues"
    say "currently break full bit-for-bit determinism."
    say ""
    say "Useful for protocol research, scaling tests, and reproducing incidents"
    say "without touching real mainnet."
    pause

    screen "The pipeline (2/4)"
    say "  ${BOLD}scenario.yaml${NC} ─▶ ${BOLD}scenario_parser${NC} ─▶ ${BOLD}config.yaml${NC} ─▶ ${BOLD}run_sim.sh${NC} ─▶ Shadow"
    say ""
    say "  ${BOLD}scenario.yaml${NC}  Compact, human-friendly. Range syntax like"
    say "                 user-{001..100}, and can use ${BOLD}auto${NC} for timing fields."
    say ""
    say "  ${BOLD}config.yaml${NC}    Fully-expanded — one entry per agent. The format"
    say "                 the Monerosim binary consumes."
    say ""
    say "  ${BOLD}run_sim.sh${NC}     Runs the ${BOLD}monerosim${NC} binary to translate"
    say "                 config.yaml into shadow_agents.yaml (Shadow's native"
    say "                 format), then launches Shadow on it. Also handles"
    say "                 disk checks, live monitoring, and post-run archiving."
    pause

    screen "auto vs explicit values (3/4)"
    say "Several timing fields accept ${BOLD}auto${NC} — the parser picks safe defaults"
    say "based on agent count and calibration data (so wallets don't starve)."
    say ""
    say "But ${BOLD}every auto field can be set explicitly${NC} if you want exact control:"
    say ""
    say "  ${DIM}# auto-picked:${NC}              ${DIM}# explicit:${NC}"
    say "  activity_start_time: auto      activity_start_time: 18000s"
    say "  transaction_interval: auto     transaction_interval: 600"
    say "  bootstrap_end_time: auto       bootstrap_end_time: 6h"
    say "  start_time_stagger: auto       start_time_stagger: 30s"
    say "  wait_time: auto                wait_time: 25200"
    say ""
    say "${DIM}If you set transaction_interval to a number that's too low for the${NC}"
    say "${DIM}user count, the parser will bump it to the calibrated minimum and${NC}"
    say "${DIM}print a warning. 'auto' just asks for that minimum directly.${NC}"
    pause

    screen "Three ways to author a simulation (4/4)"
    say "  ${BOLD}A)${NC} ${CYAN}AI tool${NC}  — describe it in English; writes scenario.yaml"
    say "              and expands to config.yaml. Slow (~5 min on old GPU)."
    say ""
    say "  ${BOLD}B)${NC} ${CYAN}Scenario${NC} — copy & edit a small commented scenario.yaml,"
    say "              then auto-expand. Best for range+auto-driven setups."
    say ""
    say "  ${BOLD}C)${NC} ${CYAN}Config${NC}   — copy & edit a fully-expanded config.yaml."
    say "              No expand step. Full per-agent control."
    say ""
    say "${DIM}Power-user alternative: scripts/generate_config.py takes CLI flags.${NC}"
    pause "Press Enter to go to the create menu..."
    create_menu
}

# ---------- option A: AI config ----------
run_ai_config() {
    screen "AI config tool"
    say "Launches the AI generator in interactive mode. It asks for LLM"
    say "credentials on first run (saved to ~/.monerosim/ai_config.yaml),"
    say "then prompts you for a description."
    say ""
    say "Output: a ${BOLD}scenario.yaml${NC} + expanded ${BOLD}config.yaml${NC}."
    say ""
    warn "Default LLM backend runs on an old GPU — ~5 min per scenario."
    say ""
    read -r -p "Press Enter to launch, or Ctrl-C to cancel... " _
    ./smart_config_tool.sh
    say ""
    ok "AI tool finished. Press Enter to return to the menu..."
    read -r _
}

# ---------- option B: scenario template ----------
run_scenario_template() {
    screen "Edit a scenario template"
    say "Copies ${DIM}$SCENARIO_TEMPLATE${NC} to a new name, opens it in"
    say "your editor, then expands it into a runnable config.yaml."
    say ""
    read -r -p "Name for your new scenario (no extension, e.g. 'myrun'): " name
    if [[ -z "$name" ]]; then
        err "No name given."
        pause
        return 1
    fi
    local out="test_configs/${name}.scenario.yaml"
    if [[ -e "$out" ]]; then
        warn "$out already exists."
        read -r -p "Overwrite? [y/N] " ans
        [[ "$ans" =~ ^[Yy] ]] || { pause; return 1; }
    fi
    cp "$SCENARIO_TEMPLATE" "$out"
    ok "Created $out"
    say ""
    say "The template comments explain every field. Tweak agent counts,"
    say "hashrates, durations — or replace ${BOLD}auto${NC} with explicit values."
    pause "Press Enter to open the editor..."
    open_in_editor "$out"

    local expanded="test_configs/${name}.yaml"
    screen "Expand scenario"
    say "Next: expand ${DIM}$out${NC} into ${DIM}$expanded${NC}."
    say ""
    read -r -p "Expand it now? [Y/n] " ans
    if [[ ! "$ans" =~ ^[Nn] ]]; then
        # shellcheck disable=SC1091
        source venv/bin/activate
        if ! python -m scripts.scenario_parser "$out" -o "$expanded"; then
            err "Expansion failed. Fix the scenario and re-run:"
            say "  python -m scripts.scenario_parser $out -o $expanded"
            pause
            return 1
        fi
        ok "Expanded → $expanded"
        offer_run "$expanded"
    else
        say ""
        info "When ready:"
        say  "  python -m scripts.scenario_parser $out -o $expanded"
        say  "  ./run_sim.sh --config $expanded"
        pause
    fi
}

# ---------- option C: config template ----------
run_config_template() {
    screen "Edit a config template"
    say "Copies ${DIM}$CONFIG_TEMPLATE${NC} to a new name and opens it in"
    say "your editor. No expand step — you edit the final config directly."
    say ""
    read -r -p "Name for your new config (no extension, e.g. 'myrun'): " name
    if [[ -z "$name" ]]; then
        err "No name given."
        pause
        return 1
    fi
    local out="test_configs/${name}.yaml"
    if [[ -e "$out" ]]; then
        warn "$out already exists."
        read -r -p "Overwrite? [y/N] " ans
        [[ "$ans" =~ ^[Yy] ]] || { pause; return 1; }
    fi
    cp "$CONFIG_TEMPLATE" "$out"
    ok "Created $out"
    pause "Press Enter to open the editor..."
    open_in_editor "$out"
    offer_run "$out"
}

# ---------- run helper ----------
offer_run() {
    local cfg="$1"
    screen "Run the simulation"
    say "Command: ${DIM}./run_sim.sh --config $cfg${NC}"
    say ""
    read -r -p "Launch it now? [y/N] " ans
    if [[ "$ans" =~ ^[Yy] ]]; then
        ./run_sim.sh --config "$cfg"
        say ""
        ok "Simulation finished. Press Enter to return to the menu..."
        read -r _
    else
        say ""
        info "When ready: ./run_sim.sh --config $cfg"
        pause
    fi
}

# ---------- prune archived runs ----------
# A typical 1k-host run produces ~150 GB of per-host stdout in shadow.data/hosts/.
# scripts/prune_archives.sh trims each archive down to the small files plus a
# handful of representative hosts (~1.5 GB), enough to compare wall-time / RAM
# against future runs without keeping the full per-host log set.
run_prune_archives() {
    screen "Prune archived runs"

    if [[ ! -d archived_runs ]] || [[ -z "$(ls -A archived_runs 2>/dev/null)" ]]; then
        warn "No archives in ./archived_runs/."
        pause
        return
    fi

    say "Each archive's per-host stdout dominates its size (often >99%)."
    say "Pruning keeps the small files plus a few sample hosts — enough"
    say "to compare wall-time, RAM use, and Shadow stats against future"
    say "runs without keeping the full ${DIM}shadow.data/hosts/${NC} tree."
    say ""

    # Build a sized, indexed list. du is slow on big trees, so show a
    # one-line "scanning…" hint while it runs.
    info "Scanning archive sizes..."
    mapfile -t lines < <(
        du -sb archived_runs/*/ 2>/dev/null \
            | sort -rn \
            | awk '{
                size = $1
                # Format as human-readable
                if (size >= 1099511627776)      printf "%.1fT\t%s\n", size/1099511627776, $2
                else if (size >= 1073741824)    printf "%.1fG\t%s\n", size/1073741824, $2
                else if (size >= 1048576)       printf "%.0fM\t%s\n", size/1048576, $2
                else                            printf "%dK\t%s\n", size/1024, $2
            }'
    )

    if [[ ${#lines[@]} -eq 0 ]]; then
        warn "No archives found."
        pause
        return
    fi

    screen "Prune archived runs"
    say "${BOLD}#  Size      Archive${NC}"
    local i=1
    local -a paths=()
    for line in "${lines[@]}"; do
        local size path
        size=$(printf "%s" "$line" | cut -f1)
        path=$(printf "%s" "$line" | cut -f2)
        path="${path%/}"
        paths+=("$path")
        printf "%-2d %-9s %s\n" "$i" "$size" "${path##*/}"
        i=$((i + 1))
    done
    say ""
    say "Enter a comma-separated list of numbers (e.g. ${DIM}1,3,5${NC}),"
    say "or ${BOLD}all${NC} to prune every archive, or ${BOLD}M${NC} to go back."
    say ""
    read -r -p "Selection: " sel

    case "${sel,,}" in
        m|"") return ;;
        all)  local -a chosen=("${paths[@]}") ;;
        *)
            local -a chosen=()
            IFS=',' read -ra parts <<< "$sel"
            for p in "${parts[@]}"; do
                p="${p// /}"
                if [[ "$p" =~ ^[0-9]+$ ]] && (( p >= 1 && p <= ${#paths[@]} )); then
                    chosen+=("${paths[$((p - 1))]}")
                else
                    warn "Skipping invalid entry: $p"
                fi
            done
            ;;
    esac

    if [[ ${#chosen[@]} -eq 0 ]]; then
        warn "Nothing selected."
        pause
        return
    fi

    say ""
    say "Will prune ${BOLD}${#chosen[@]}${NC} archive(s):"
    for c in "${chosen[@]}"; do say "  ${c##*/}"; done
    say ""
    read -r -p "Proceed? [y/N] " ans
    if [[ ! "$ans" =~ ^[Yy] ]]; then
        info "Cancelled."
        pause
        return
    fi

    local before_total=0 after_total=0
    for c in "${chosen[@]}"; do
        local before
        before=$(du -sb "$c" 2>/dev/null | awk '{print $1}')
        before_total=$((before_total + before))
        say ""
        info "Pruning ${c##*/}..."
        if scripts/prune_archives.sh "$c"; then
            local after
            after=$(du -sb "$c" 2>/dev/null | awk '{print $1}')
            after_total=$((after_total + after))
            ok "Done."
        else
            err "prune_archives.sh failed for $c. Skipping rest."
            break
        fi
    done

    say ""
    hr
    if (( before_total > 0 )); then
        local saved=$((before_total - after_total))
        printf "Total: %.1fG -> %.1fG (saved %.1fG)\n" \
            "$(echo "$before_total / 1073741824" | bc -l)" \
            "$(echo "$after_total / 1073741824" | bc -l)" \
            "$(echo "$saved / 1073741824" | bc -l)"
    fi
    pause
}

# ---------- advanced menu ----------
advanced_menu() {
    while true; do
        screen "Advanced tools"
        say "  ${BOLD}P)${NC} Prune archived runs (free disk space)"
        say "  ${BOLD}M)${NC} Back to main menu"
        say ""
        read -r -p "Choose [P/M]: " choice
        case "${choice^^}" in
            P)    run_prune_archives ;;
            M|"") return ;;
            *)    warn "Please choose P or M."; sleep 1 ;;
        esac
    done
}

# ---------- create menu (A/B/C) ----------
create_menu() {
    while true; do
        screen "Create a simulation"
        say "  ${BOLD}A)${NC} AI tool — describe in English (slow, ~5 min)"
        say "  ${BOLD}B)${NC} Edit a scenario template (compact; auto-expand)"
        say "  ${BOLD}C)${NC} Edit a config template (one entry per agent)"
        say "  ${BOLD}M)${NC} Back to main menu"
        say ""
        read -r -p "Choose [A/B/C/M]: " choice
        case "${choice^^}" in
            A) run_ai_config ;;
            B) run_scenario_template ;;
            C) run_config_template ;;
            M|"") return ;;
            *)   warn "Please choose A, B, C, or M."; sleep 1 ;;
        esac
    done
}

# ---------- top menu ----------
top_menu() {
    while true; do
        screen "Monerosim"
        say "Run Monero networks inside a discrete-event simulator."
        say ""
        say "  ${BOLD}L)${NC} Learn how it works (~2 min walkthrough)"
        say "  ${BOLD}C)${NC} Create a simulation now"
        say "  ${BOLD}A)${NC} Advanced tools (prune archives, etc.)"
        say "  ${BOLD}Q)${NC} Quit"
        say ""
        say "${DIM}Skip-the-docs wizard. Power users: see QUICKSTART.md, or call"
        say "./run_sim.sh / scenario_parser.py / generate_config.py direct.${NC}"
        say ""
        read -r -p "Choose [L/C/A/Q]: " choice
        case "${choice^^}" in
            L) learn_walkthrough ;;
            C) create_menu ;;
            A) advanced_menu ;;
            Q|"") say "OK, exiting. Run ./start_here.sh anytime."; return ;;
            *)   warn "Please choose L, C, A, or Q."; sleep 1 ;;
        esac
    done
}

# ---------- entry point ----------
if ! is_installed; then
    prompt_run_setup
fi

top_menu
