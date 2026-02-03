# TODO: Multi-Cohort Activity Batching

## Problem

`generate_config.py` computes `activity_start_time` staggering for a single flat
list of users relative to one base time (`activity_start_time_s`). If a second
cohort of agents is added mid-simulation (e.g., new users joining after an
upgrade, or a partition/rejoin scenario), their activity start times need
separate staggering relative to their own base time.

Currently, `calculate_activity_start_times()` is called once per config
generation for all users. There is no concept of cohorts.

## What's Needed

1. **Cohort definition in CLI/YAML** — a way to specify multiple groups of users
   with different spawn windows and activity start times (e.g.,
   `--cohort 500:spawn=3h:activity=5h --cohort 200:spawn=20h:activity=22h`)

2. **Per-cohort activity batching** — call `calculate_activity_start_times()`
   separately for each cohort with its own `base_activity_start_s`, so each
   wave gets properly staggered independently

3. **Per-cohort bootstrap/funding** — each cohort may need its own funding
   period from the miner distributor before activity starts

## Current Workaround

Manually set per-agent `activity_start_time` values in the YAML config, or
generate two configs and merge them by hand.

## Priority

Low — current single-cohort design covers the main scaling and upgrade test
scenarios. Multi-cohort would be needed for partition/rejoin or phased rollout
simulations.
