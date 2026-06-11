# NOTE: Need to install these packages:
# install.packages(c("data.table", "knitr", "remotes", "skellam", "circlize"))
# install.packages("https://cran.r-project.org/src/contrib/Archive/IP/IP_0.1.6.tar.gz")
# Need to install IP package from archive until it gets back into CRAN compliance
# remotes::install_github("Rucknium/xmrpeers", upgrade = FALSE)

library(data.table)

n.node.sample <- 10
# NOTE: Change this to 5 if running small-scale test

daemon_logs.dir <- "daemon_logs"
# NOTE: Input directory relative to current working directory

nodes <- list.dirs(daemon_logs.dir, full.names = FALSE, recursive = FALSE)

nodes <- nodes[grepl("monero-user", nodes)]

set.seed(314)

nodes <- sort(sample(nodes, n.node.sample))

p2p.gossip <- list()

for (i in nodes) {
  p2p.gossip[[i]] <-
    xmrpeers::get.p2p.log(paste(daemon_logs.dir, i, sep = "/"))
}



table(lengths(p2p.gossip))

p2p.gossip.saved <- copy(p2p.gossip)

p2p.gossip <- data.table::rbindlist(p2p.gossip, idcol = "file")



setnames(p2p.gossip, "time", "time.p2p")


hour.seq <- seq(as.POSIXct("2000-01-01"), as.POSIXct("2000-02-01"), by = "1 hour")

p2p.gossip[, hour := cut(time.p2p, hour.seq)]

p2p.gossip.hour <- p2p.gossip[, .(n.hours = uniqueN(hour)), by = c("file", "ip", "direction")]

summary(p2p.gossip.hour$n.hours)




p2p.gossip.hour[, as.list(summary(n.hours)), by = "direction"]

setorder(p2p.gossip, time.p2p)

diff.hour <- p2p.gossip[, .(diff.hour = diff(as.numeric(hour))), by = c("file", "ip", "direction")]

diff.hour.summary <- diff.hour[, .(diff.hour = 1 + sum(diff.hour > 1)), by = c("file", "ip", "direction")]
diff.hour.summary[is.na(diff.hour), diff.hour := 1] # Because if there was a missing for diff(), then it only appeared once.

diff.hour.summary[, as.list(summary(diff.hour)), by = "direction"]
# ^ Number of distinct intervals it appears in the data



conn.period <- function(x) {
  # https://stats.stackexchange.com/questions/107515/grouping-sequential-values-in-r
  y <- sort(x)
  conn.period <- cumsum(c(1, abs(y[-length(y)] - y[-1]) > 1))
  conn.period[match(y, x)]
}


p2p.gossip[, conn.period := conn.period(as.integer(hour)), by = c("file", "ip", "direction")]

diff.time <- p2p.gossip[, .(diff.time = diff(range(as.numeric(time.p2p)))), by = c("file", "ip", "direction", "conn.period")]

files.for.duration <- unique(p2p.gossip$file)

diff.time[file %in% files.for.duration, as.list(summary(as.numeric(diff.time)/ 60))]

diff.time[file %in% files.for.duration, as.list(summary(as.numeric(diff.time)/ 60)), by = "direction"]
# ^ Median duration of connections


diff.time[file %in% files.for.duration & direction == "OUT", 100 * prop.table(table(as.numeric(diff.time)/ 60 > 6*60))]
# ^ Share of outgoing connections lasting longer than 6 hours

diff.time[file %in% files.for.duration & direction == "OUT", 100 * prop.table(table(as.numeric(diff.time)/ 60 > 24*60))]
# ^ Share of outgoing connections lasting longer than 24 hours

diff.time[file %in% files.for.duration & direction == "INC", 100 * prop.table(table(as.numeric(diff.time)/ 60 > 6*60))]
# ^ Share of incoming connections lasting longer than 6 hours

diff.time[file %in% files.for.duration & direction == "INC", 100 * prop.table(table(as.numeric(diff.time)/ 60 > 24*60))]
# ^ Share of incoming connections lasting longer than 24 hours

summary(diff.time[file %in% files.for.duration & as.numeric(diff.time)/ 60 <= 200, diff.time/60])

knitr::kable(as.matrix(summary(diff.time[file %in% files.for.duration, diff.time/60])),
  col.names = "Minutes")

library(ggplot2)

png("p2p-connection-duration.png")

ggplot(diff.time[file %in% files.for.duration & as.numeric(diff.time)/ 60 <= 200, ],
  aes(as.numeric(diff.time)/ 60, color = direction)) +
  labs(title = "Kernel density estimate of peer connection duration", x = "Connection duration (minutes)") +
  geom_density(bw = 1) +
  theme(legend.position = "top", legend.text = element_text(size = 12), legend.title = element_text(size = 15),
    plot.title = element_text(size = 16),
    plot.subtitle = element_text(size = 15),
    axis.text = element_text(size = 15),
    axis.title.x = element_text(size = 15, margin = margin(t = 10)),
    axis.title.y = element_text(size = 15), strip.text = element_text(size = 15)) +
  guides(colour = guide_legend(nrow = 1, byrow = FALSE, override.aes = list(linewidth = 5)))

dev.off()




# ****************************
# Clumping
# ****************************


clumping <- p2p.gossip[, .(temp = .N), by = c("file", "gossip.msg.id")][, round(100 * prop.table(table(temp)), 2)]

clumping <- c(clumping) # Convert from table to vector
clumping <- c(clumping[as.numeric(names(clumping)) <= 10], `> 10` = sum(clumping[as.numeric(names(clumping)) > 10]))

knitr::kable(clumping, col.names = c("Number of txs in message", "Share of messages (percentage)"))




unique.conn.hours <- unique(p2p.gossip[, .(file, ip, port, direction, hour)])
our.nodes.connected <- unique.conn.hours[, .(n.our.nodes.connected = .N), by = c("ip", "port", "hour")]
our.nodes.connected <- merge(our.nodes.connected[n.our.nodes.connected == 2, .(ip, hour)], unique.conn.hours)
# A few have our.nodes.connected == 3, but it is very rare and harder to analyze, so skip
our.nodes.connected <- merge(our.nodes.connected, p2p.gossip, by = c("ip", "hour", "file", "port"))

setorder(our.nodes.connected, file, time.p2p)
# Set order by file so the "first" and "second" nodes are in consistent order.
# Set next order priority by time.p2p so that the next step works properly

our.nodes.connected <- unique(our.nodes.connected, by = c("file", "ip", "port", "tx.hash"))
# Sometimes a peer sends the same transaction more than once, so eliminate the later duplicate

our.nodes.connected <- our.nodes.connected[, .(tx.hash.time.diff = diff(time.p2p),
  gossip.msg.id.1 = gossip.msg.id[1], gossip.msg.id.2 = gossip.msg.id[2],
  file.1 = file[1], file.2 = file[2]), by = c("ip", "port", "hour", "tx.hash")]


our.nodes.connected[, tx.hash.time.diff := as.numeric(tx.hash.time.diff)]

most.common.connections <- our.nodes.connected[ ! is.na(file.1) & ! is.na(file.2), table(paste0(file.1, "$", file.2))]

pair.in.time.sync <- strsplit(names(sort(most.common.connections, decreasing = TRUE))[1], split = "$", fixed = TRUE)[[1]]



library(circlize)

# Circular density


simul.connection.data <- our.nodes.connected[tx.hash.time.diff <= 60 &
    (file.1 %in% pair.in.time.sync & file.2 %in% pair.in.time.sync),
  tx.hash.time.diff]

stopifnot(length(simul.connection.data) > 0)
# pair.in.time.sync must be chosen manualy.
# sort(table(our.nodes.connected[, paste(file.1, file.2, sep = "-")]), decreasing = TRUE)


circ.data <- ifelse(simul.connection.data >= 0, simul.connection.data %% 1,
  abs(simul.connection.data %% -1))
# Compute modulo

circ.data <- c(circ.data - 1, circ.data, circ.data + 1)
# This gives us a "circular" support so we do not have the
# kernel density boundary issue

density.data <- density(circ.data, bw = 0.01, n = 512 * 3)

density.data$y <- density.data$y[density.data$x %between% c(-0.005, 1.005) ]
density.data$x <- density.data$x[density.data$x %between% c(-0.005, 1.005) ]


png("one-second-period-tx-p2p-msg.png")

circos.par(start.degree = 90, gap.degree = 0, circle.margin = 0.15)

circos.initialize(sectors = rep("A", length(circ.data)), x = circ.data, xlim = c(0, 1))

circos.trackPlotRegion(ylim = c(0, max(density.data$y)), track.height = .9)

circos.trackLines(sectors = rep("A", length(density.data$x)), density.data$x, density.data$y,
  track.index = 1, area = TRUE, col = "#999999", border = "black" )

circos.xaxis(major.at = c(0, 0.25, 0.50, 0.75),
  labels = c(0, expression(frac(1, 4)), expression(1/2), expression(frac(3, 4))),
  labels.facing = "downward",  labels.col = "darkred", labels.pos.adjust = FALSE)

axis.marks <- c(0.5, 1, 1.5)

circos.yaxis(at = axis.marks)

for (i in axis.marks) {
  circos.trackLines(sectors = rep("A", 2), c(0, 1), rep(i, 2), lty = 2,
    track.index = 1 )
}



circos.clear()

title(main = "One-second cycle of time difference between same\ntx received from two different nodes")
title(sub = "Fractional seconds")

dev.off()



# Histogram

n.subsecond.intervals <- 8
hist.range <- c(-5 - (1/2)/n.subsecond.intervals, 5 + (1/2)/n.subsecond.intervals)

skellam.points <- n.subsecond.intervals * skellam::dskellam(-20:20, lambda1 = 20, lambda2 = 20)

png("skellam-histogram-tx-p2p-msg.png")

hist(simul.connection.data[simul.connection.data %between% hist.range],
  breaks = seq(hist.range[1], hist.range[2], by = 1/n.subsecond.intervals), probability = TRUE,
  main = "Time difference between same tx received from two different nodes",
  xlab = "Time difference (seconds)")

points(-20:20/4, skellam.points, col = "red")
segments(-20:20/4, 0, -20:20/4, skellam.points, col = "red")
legend("topleft", legend = c("Histogram", "Theoretical Skellam\ndistribution"),
  fill = c("lightgray", NA), border = c("black", NA), pch = c(NA, 21),
  col = c(NA, "red"), bty = "n")

dev.off()

