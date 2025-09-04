graph [
  comment "Realistic Internet Topology with Multiple ASes"
  directed 0
  
  node [
    id 0
    label "ISP_A_Router_1"
    AS "65001"
    ip "10.0.0.1"
    bandwidth 100000000
    packet_loss 0.1
  ]
  
  node [
    id 1
    label "ISP_A_Router_2"
    AS "65001"
    ip "10.0.0.2"
    bandwidth 100000000
    packet_loss 0.1
  ]
  
  node [
    id 2
    label "ISP_B_Router_1"
    AS "65002"
    ip "192.168.0.1"
    bandwidth 100000000
    packet_loss 0.2
  ]
  
  node [
    id 3
    label "ISP_B_Router_2"
    AS "65002"
    ip "192.168.0.2"
    bandwidth 100000000
    packet_loss 0.2
  ]
  
  node [
    id 4
    label "DataCenter_Router_1"
    AS "65003"
    ip "172.16.0.1"
    bandwidth 1000000000
    packet_loss 0.05
  ]
  
  node [
    id 5
    label "DataCenter_Router_2"
    AS "65003"
    ip "172.16.0.2"
    bandwidth 1000000000
    packet_loss 0.05
  ]
  
  edge [
    source 0
    target 1
    latency "5ms"
    bandwidth 100000000
    packet_loss 0.1
  ]
  
  edge [
    source 2
    target 3
    latency "8ms"
    bandwidth 100000000
    packet_loss 0.2
  ]
  
  edge [
    source 4
    target 5
    latency "2ms"
    bandwidth 1000000000
    packet_loss 0.05
  ]
  
  edge [
    source 0
    target 2
    latency "50ms"
    bandwidth 50000000
    packet_loss 0.5
  ]
  
  edge [
    source 1
    target 3
    latency "45ms"
    bandwidth 50000000
    packet_loss 0.5
  ]
  
  edge [
    source 0
    target 4
    latency "20ms"
    bandwidth 200000000
    packet_loss 0.3
  ]
  
  edge [
    source 1
    target 5
    latency "25ms"
    bandwidth 200000000
    packet_loss 0.3
  ]
  
  edge [
    source 2
    target 4
    latency "30ms"
    bandwidth 150000000
    packet_loss 0.4
  ]
  
  edge [
    source 3
    target 5
    latency "35ms"
    bandwidth 150000000
    packet_loss 0.4
  ]
  
  edge [
    source 0
    target 3
    latency "100ms"
    bandwidth 20000000
    packet_loss 1.0
    comment "Backup connection"
  ]
  
  edge [
    source 1
    target 2
    latency "95ms"
    bandwidth 20000000
    packet_loss 1.0
    comment "Backup connection"
  ]
]