graph [
  directed 0
  edge [
    source 0
    target 0
    latency "10 ms"
    packet_loss 0.0
  ]

  edge [
    source 1
    target 1
    latency "10 ms"
    packet_loss 0.0
  ]

  node [
    id 0
    ip "192.168.1.10"
    host_bandwidth_down "1 Gbit"
    host_bandwidth_up "1 Gbit"
  ]
  node [
    id 1
    ip_addr "192.168.1.20"
    host_bandwidth_down "1 Gbit"
    host_bandwidth_up "1 Gbit"
  ]

  edge [
    source 0
    target 1
    latency "50 ms"
    packet_loss 0.0
  ]
  edge [
    source 1
    target 0
    latency "50 ms"
    packet_loss 0.0
  ]
]