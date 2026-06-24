#!/usr/bin/env Rscript
# Churn-capable runner for Rucknium's ruck_analysis.r.
#
# Run from inside an archive dir (it reads ./daemon_logs and writes PNGs/tables
# to the current working directory):
#   ( cd archived_runs/<run> && Rscript /abs/path/analysis/ruck_analysis_churn.r )
#
# It loads the churn-robust parser (get_p2p_log_robust.R) and overrides
# xmrpeers::get.p2p.log with it, then sources the UNMODIFIED ruck_analysis.r so
# every metric (conn-duration, >6h shares, clumping, one-second cycle, Skellam)
# is computed exactly as upstream — the only difference is a tx-count repair that
# survives monerod restarts (peer churn). See get_p2p_log_robust.R for the why.
suppressMessages({ library(data.table); library(xmrpeers) })
.churn.dir <- "/home/lever65/monerosim_scale/monerosim/analysis"
source(file.path(.churn.dir, "get_p2p_log_robust.R"))
assignInNamespace("get.p2p.log", get.p2p.log.robust, ns = "xmrpeers")
source(file.path(.churn.dir, "ruck_analysis.r"), echo = TRUE)
