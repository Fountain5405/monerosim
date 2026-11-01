# shellcheck shell=bash
#
# patch_series.sh - read patches/series, the one ordered list of the patches
# built into monerod-sim. Sourced by setup.sh and update.sh; the Python reader
# is read_patch_series() in scripts/run_sim_helpers.py.
#
# Each non-comment line of patches/series is TAB-separated:
#   path  owner  flags  summary
# (see the header of patches/series).

# patch_series_rows ROOT: print the series' data lines, in apply order.
patch_series_rows() {
    local root="$1" line
    while IFS= read -r line || [[ -n "$line" ]]; do
        [[ -z "${line//[[:space:]]/}" || "$line" == \#* ]] && continue
        printf '%s\n' "$line"
    done < "$root/patches/series"
}

# patch_series_paths ROOT: print each patch's absolute path, in apply order.
patch_series_paths() {
    local root="$1" path owner flags summary
    patch_series_rows "$root" | while IFS=$'\t' read -r path owner flags summary; do
        printf '%s/%s\n' "$root" "$path"
    done
}

# patch_series_help ROOT: one --help line per patch: file, owner, flags, summary.
patch_series_help() {
    local root="$1" path owner flags summary
    patch_series_rows "$root" | while IFS=$'\t' read -r path owner flags summary; do
        printf '                         %s [%s] %s\n' "$(basename "$path")" "$owner" "${flags//,/ }"
        printf '                             %s\n' "$summary"
    done
}
