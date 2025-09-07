graph [
  comment "Global Network Topology - 20 Nodes Across 5 Continents"
  directed 0

  node [
    id 0
    label "NA-NewYork-Router"
    AS "65001"
    ip "10.0.0.1"
    bandwidth 1000000000
    packet_loss 0.1
  ]

  node [
    id 1
    label "NA-Chicago-Router"
    AS "65001"
    ip "10.0.0.2"
    bandwidth 1000000000
    packet_loss 0.1
  ]

  node [
    id 2
    label "NA-LosAngeles-Router"
    AS "65001"
    ip "10.0.0.3"
    bandwidth 1000000000
    packet_loss 0.1
  ]

  node [
    id 3
    label "NA-Toronto-Router"
    AS "65001"
    ip "10.0.0.4"
    bandwidth 1000000000
    packet_loss 0.1
  ]

  node [
    id 4
    label "NA-Miami-Router"
    AS "65001"
    ip "10.0.0.5"
    bandwidth 1000000000
    packet_loss 0.1
  ]

  node [
    id 5
    label "EU-London-Router"
    AS "65002"
    ip "172.16.0.1"
    bandwidth 1000000000
    packet_loss 0.1
  ]

  node [
    id 6
    label "EU-Frankfurt-Router"
    AS "65002"
    ip "172.16.0.2"
    bandwidth 1000000000
    packet_loss 0.1
  ]

  node [
    id 7
    label "EU-Paris-Router"
    AS "65002"
    ip "172.16.0.3"
    bandwidth 1000000000
    packet_loss 0.1
  ]

  node [
    id 8
    label "EU-Amsterdam-Router"
    AS "65002"
    ip "172.16.0.4"
    bandwidth 1000000000
    packet_loss 0.1
  ]

  node [
    id 9
    label "AS-Tokyo-Router"
    AS "65003"
    ip "192.168.0.1"
    bandwidth 1000000000
    packet_loss 0.1
  ]

  node [
    id 10
    label "AS-HongKong-Router"
    AS "65003"
    ip "192.168.0.2"
    bandwidth 1000000000
    packet_loss 0.1
  ]

  node [
    id 11
    label "AS-Singapore-Router"
    AS "65003"
    ip "192.168.0.3"
    bandwidth 1000000000
    packet_loss 0.1
  ]

  node [
    id 12
    label "AS-Seoul-Router"
    AS "65003"
    ip "192.168.0.4"
    bandwidth 1000000000
    packet_loss 0.1
  ]

  node [
    id 13
    label "AS-Mumbai-Router"
    AS "65003"
    ip "192.168.0.5"
    bandwidth 1000000000
    packet_loss 0.1
  ]

  node [
    id 14
    label "SA-SaoPaulo-Router"
    AS "65004"
    ip "10.1.0.1"
    bandwidth 500000000
    packet_loss 0.2
  ]

  node [
    id 15
    label "SA-BuenosAires-Router"
    AS "65004"
    ip "10.1.0.2"
    bandwidth 500000000
    packet_loss 0.2
  ]

  node [
    id 16
    label "SA-Santiago-Router"
    AS "65004"
    ip "10.1.0.3"
    bandwidth 500000000
    packet_loss 0.2
  ]

  node [
    id 17
    label "AF-Johannesburg-Router"
    AS "65005"
    ip "10.2.0.1"
    bandwidth 500000000
    packet_loss 0.3
  ]

  node [
    id 18
    label "AF-Cairo-Router"
    AS "65005"
    ip "10.2.0.2"
    bandwidth 500000000
    packet_loss 0.3
  ]

  node [
    id 19
    label "AF-Lagos-Router"
    AS "65005"
    ip "10.2.0.3"
    bandwidth 500000000
    packet_loss 0.3
  ]

  edge [
    source 0
    target 1
    latency "20ms"
    bandwidth 1000000000
    packet_loss 0.1
  ]

  edge [
    source 1
    target 2
    latency "50ms"
    bandwidth 1000000000
    packet_loss 0.1
  ]

  edge [
    source 2
    target 3
    latency "40ms"
    bandwidth 1000000000
    packet_loss 0.1
  ]

  edge [
    source 3
    target 4
    latency "25ms"
    bandwidth 1000000000
    packet_loss 0.1
  ]

  edge [
    source 0
    target 4
    latency "35ms"
    bandwidth 1000000000
    packet_loss 0.1
  ]

  edge [
    source 5
    target 6
    latency "15ms"
    bandwidth 1000000000
    packet_loss 0.1
  ]

  edge [
    source 6
    target 7
    latency "10ms"
    bandwidth 1000000000
    packet_loss 0.1
  ]

  edge [
    source 7
    target 8
    latency "12ms"
    bandwidth 1000000000
    packet_loss 0.1
  ]

  edge [
    source 5
    target 8
    latency "8ms"
    bandwidth 1000000000
    packet_loss 0.1
  ]

  edge [
    source 9
    target 10
    latency "25ms"
    bandwidth 1000000000
    packet_loss 0.1
  ]

  edge [
    source 10
    target 11
    latency "30ms"
    bandwidth 1000000000
    packet_loss 0.1
  ]

  edge [
    source 11
    target 12
    latency "35ms"
    bandwidth 1000000000
    packet_loss 0.1
  ]

  edge [
    source 12
    target 13
    latency "20ms"
    bandwidth 1000000000
    packet_loss 0.1
  ]

  edge [
    source 9
    target 13
    latency "40ms"
    bandwidth 1000000000
    packet_loss 0.1
  ]

  edge [
    source 14
    target 15
    latency "50ms"
    bandwidth 500000000
    packet_loss 0.2
  ]

  edge [
    source 15
    target 16
    latency "45ms"
    bandwidth 500000000
    packet_loss 0.2
  ]

  edge [
    source 14
    target 16
    latency "60ms"
    bandwidth 500000000
    packet_loss 0.2
  ]

  edge [
    source 17
    target 18
    latency "80ms"
    bandwidth 500000000
    packet_loss 0.3
  ]

  edge [
    source 18
    target 19
    latency "75ms"
    bandwidth 500000000
    packet_loss 0.3
  ]

  edge [
    source 17
    target 19
    latency "90ms"
    bandwidth 500000000
    packet_loss 0.3
  ]

  edge [
    source 0
    target 5
    latency "80ms"
    bandwidth 200000000
    packet_loss 0.5
  ]

  edge [
    source 1
    target 6
    latency "75ms"
    bandwidth 200000000
    packet_loss 0.5
  ]

  edge [
    source 4
    target 8
    latency "85ms"
    bandwidth 200000000
    packet_loss 0.5
  ]

  edge [
    source 2
    target 9
    latency "120ms"
    bandwidth 150000000
    packet_loss 0.7
  ]

  edge [
    source 2
    target 10
    latency "125ms"
    bandwidth 150000000
    packet_loss 0.7
  ]

  edge [
    source 6
    target 12
    latency "200ms"
    bandwidth 100000000
    packet_loss 1.0
  ]

  edge [
    source 7
    target 11
    latency "180ms"
    bandwidth 100000000
    packet_loss 1.0
  ]

  edge [
    source 4
    target 14
    latency "150ms"
    bandwidth 100000000
    packet_loss 0.8
  ]

  edge [
    source 4
    target 15
    latency "160ms"
    bandwidth 100000000
    packet_loss 0.8
  ]

  edge [
    source 8
    target 18
    latency "130ms"
    bandwidth 80000000
    packet_loss 0.9
  ]

  edge [
    source 7
    target 17
    latency "140ms"
    bandwidth 80000000
    packet_loss 0.9
  ]

  edge [
    source 13
    target 19
    latency "250ms"
    bandwidth 50000000
    packet_loss 1.0
  ]

  edge [
    source 16
    target 19
    latency "220ms"
    bandwidth 30000000
    packet_loss 1.0
  ]

  edge [
    source 0
    target 7
    latency "90ms"
    bandwidth 50000000
    packet_loss 1.0
    comment "Backup transatlantic"
  ]

  edge [
    source 2
    target 12
    latency "140ms"
    bandwidth 80000000
    packet_loss 1.0
    comment "Backup transpacific"
  ]

  edge [
    source 14
    target 17
    latency "280ms"
    bandwidth 20000000
    packet_loss 1.0
    comment "Backup intercontinental"
  ]

  edge [
    source 0
    target 0
    latency "1ms"
    bandwidth 1000000000
    packet_loss 0.0
  ]

  edge [
    source 1
    target 1
    latency "1ms"
    bandwidth 1000000000
    packet_loss 0.0
  ]

  edge [
    source 2
    target 2
    latency "1ms"
    bandwidth 1000000000
    packet_loss 0.0
  ]

  edge [
    source 3
    target 3
    latency "1ms"
    bandwidth 1000000000
    packet_loss 0.0
  ]

  edge [
    source 4
    target 4
    latency "1ms"
    bandwidth 1000000000
    packet_loss 0.0
  ]

  edge [
    source 5
    target 5
    latency "1ms"
    bandwidth 1000000000
    packet_loss 0.0
  ]

  edge [
    source 6
    target 6
    latency "1ms"
    bandwidth 1000000000
    packet_loss 0.0
  ]

  edge [
    source 7
    target 7
    latency "1ms"
    bandwidth 1000000000
    packet_loss 0.0
  ]

  edge [
    source 8
    target 8
    latency "1ms"
    bandwidth 1000000000
    packet_loss 0.0
  ]

  edge [
    source 9
    target 9
    latency "1ms"
    bandwidth 1000000000
    packet_loss 0.0
  ]

  edge [
    source 10
    target 10
    latency "1ms"
    bandwidth 1000000000
    packet_loss 0.0
  ]

  edge [
    source 11
    target 11
    latency "1ms"
    bandwidth 1000000000
    packet_loss 0.0
  ]

  edge [
    source 12
    target 12
    latency "1ms"
    bandwidth 1000000000
    packet_loss 0.0
  ]

  edge [
    source 13
    target 13
    latency "1ms"
    bandwidth 1000000000
    packet_loss 0.0
  ]

  edge [
    source 14
    target 14
    latency "1ms"
    bandwidth 500000000
    packet_loss 0.0
  ]

  edge [
    source 15
    target 15
    latency "1ms"
    bandwidth 500000000
    packet_loss 0.0
  ]

  edge [
    source 16
    target 16
    latency "1ms"
    bandwidth 500000000
    packet_loss 0.0
  ]

  edge [
    source 17
    target 17
    latency "1ms"
    bandwidth 500000000
    packet_loss 0.0
  ]

  edge [
    source 18
    target 18
    latency "1ms"
    bandwidth 500000000
    packet_loss 0.0
  ]

  edge [
    source 19
    target 19
    latency "1ms"
    bandwidth 500000000
    packet_loss 0.0
  ]
]