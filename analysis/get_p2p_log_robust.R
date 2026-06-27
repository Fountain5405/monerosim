# Turnover-robust drop-in replacement for xmrpeers::get.p2p.log.
#
# WHY: xmrpeers::get.p2p.log infers the tx count of each NOTIFY_NEW_TRANSACTIONS
# message from runs of "Including transaction" lines via rle(). When a monerod is
# restarted mid-simulation (peer turnover), a NOTIFY can be logged with its
# "Including transaction" lines truncated by the shutdown, so the rle run-lengths
# stop matching the notify count -> a negative / mismatched `number.of.txs.corrected`
# -> rep(times = ...) aborts with "invalid 'times' argument", killing the whole
# analysis. ~40% of nodes that cycle hit this.
#
# FIX: compute the per-notify tx count directly. After the log is filtered to ONLY
# notify + "Including transaction" lines, the includes belonging to notify[i] are
# exactly the lines strictly between notify[i] and notify[i+1]. That count is
# always non-negative and has exactly length(notify.lines) entries, so it never
# crashes. Conn-duration (our headline metric) ignores the count entirely; clumping
# uses it and is now correct-by-construction even across restart boundaries.
#
# Output columns are identical to xmrpeers::get.p2p.log, so this is a true drop-in.
# Everything except the tx-count repair block is verbatim from upstream.

get.p2p.log.robust <- function(bitmonero.dir = "~/.bitmonero", output.file = NULL) {
    bitmonero.dir <- path.expand(bitmonero.dir)
    bitmonero.dir <- gsub("/+$", "", bitmonero.dir)
    files.in.dir <- list.files(bitmonero.dir)
    bitmonero.files <- files.in.dir[grepl("(^bitmonero[.]log)|(^monero[.]log)",
        files.in.dir, ignore.case = TRUE)]
    get.time <- function(x) {
        x <- stringr::str_extract(x, "^[0-9]{4}-[0-9]{2}-[0-9]{2}\\s[0-9]{2}:[0-9]{2}:[0-9]{2}\\S*")
        as.POSIXct(strptime(x, format = "%Y-%m-%d %H:%M:%OS"))
    }
    cat(base::date(), " Reading ", length(bitmonero.files), " log files...\n", sep = "")
    monero.log <- lapply(bitmonero.files, function(x) {
        x <- data.table::fread(paste0(bitmonero.dir, "/", x),
            header = FALSE, sep = NULL, blank.lines.skip = FALSE)[[1]]
        times <- get.time(x)
        x[!is.na(times)]
    })
    monero.log.timing <- lapply(seq_along(monero.log), function(x) {
        suppressWarnings(readr::read_tsv(I(monero.log[[x]]),
            col_names = c("time", "thread"), col_types = c("T", "c"),
            col_select = 1:2, skip_empty_rows = FALSE))
    })
    beginning.log.times <- vector("numeric", length(monero.log))
    for (i in seq_along(beginning.log.times)) {
        if (grepl("^[0-9]{4}-", monero.log[[i]][1])) {
            first.date.line <- 1
        } else {
            first.date.line <- grep("^[0-9]{4}-", monero.log[[i]])[1]
        }
        beginning.log.times[i] <- get.time(monero.log[[i]][first.date.line])
    }
    monero.log <- unlist(monero.log[order(beginning.log.times)])
    monero.log.timing <- as.data.frame(do.call(rbind, monero.log.timing[order(beginning.log.times)]))
    keep.rows <- (!duplicated(monero.log)) & complete.cases(monero.log.timing)
    monero.log <- monero.log[keep.rows]
    monero.log.timing <- monero.log.timing[keep.rows, ]
    monero.log <- monero.log[order(monero.log.timing$thread, monero.log.timing$time)]
    rm(monero.log.timing, keep.rows)
    cat(base::date(), " Finished reading ", length(bitmonero.files), " log files.\n", sep = "")
    monero.log <- monero.log[grepl("net.p2p.msg", monero.log, fixed = TRUE)]
    monero.log <- monero.log[grepl("Received NOTIFY_NEW_TRANSACTIONS", monero.log, fixed = TRUE) |
        grepl("Including transaction", monero.log, fixed = TRUE)]
    notify.lines <- grep("Received NOTIFY_NEW_TRANSACTIONS", monero.log, fixed = TRUE)
    get.number.of.txs <- function(x) {
        x <- stringr::str_extract(x, "([0-9]+) txes[)]", group = 1)
        as.numeric(x)
    }
    number.of.txs <- get.number.of.txs(monero.log[notify.lines])
    get.tx.hash <- function(x) {
        stringr::str_extract(x, "Including transaction <([:xdigit:]{64})>", group = 1)
    }
    if (length(notify.lines) == 0L) {
        return(data.frame(time = as.POSIXct(character(0)), gossip.msg.id = integer(0),
            tx.hash = character(0), ip = character(0), port = character(0),
            direction = character(0), stringsAsFactors = FALSE))
    }
    # ---- ROBUST per-notify tx count (the ONLY change vs upstream) ----
    # includes for notify[i] = lines strictly between notify[i] and notify[i+1].
    ends <- c(notify.lines[-1], length(monero.log) + 1L)
    number.of.txs.corrected <- ends - notify.lines - 1L
    cat(base::date(), " ", sum(number.of.txs.corrected != number.of.txs, na.rm = TRUE),
        " notify/tx-count mismatches (robustly repaired).\n", sep = "")
    peer_ip_port <- xmrpeers:::get.peer.ip.port.direction(monero.log[notify.lines],
        "Received NOTIFY_NEW_TRANSACTIONS")
    tx.data <- data.frame(
        time = rep(get.time(monero.log[notify.lines]), times = number.of.txs.corrected + 1),
        gossip.msg.id = rep(seq_along(notify.lines), times = number.of.txs.corrected + 1),
        tx.hash = get.tx.hash(monero.log),
        stringsAsFactors = FALSE)
    tx.data <- cbind(tx.data, peer_ip_port[tx.data$gossip.msg.id, ])
    tx.data <- tx.data[!is.na(tx.data$tx.hash), ]
    rownames(tx.data) <- NULL
    if (!is.null(output.file)) {
        cat(base::date(), " Writing data to ", output.file, "...\n", sep = "")
        qs2::qs_save(tx.data, output.file, preset = "custom",
            algorithm = "zstd_stream", compress_level = 22, shuffle_control = 15)
    }
    tx.data
}
