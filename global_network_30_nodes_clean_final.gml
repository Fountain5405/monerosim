graph [
  comment "Comprehensive Global Network Topology - 30 Nodes Across 6 Continents for 30-Agent Simulation"
  directed 0

  node [
    id 0
    label "NA-NYC-Core-Router-1"
    AS "65001"
    ip "10.0.0.1"
    bandwidth 1000000000
    packet_loss 0.05
    location "New_York"
  ]

  node [
    id 1
    label "NA-NYC-Core-Router-2"
    AS "65001"
    ip "10.0.0.2"
    bandwidth 1000000000
    packet_loss 0.05
    location "New_York"
  ]

  node [
    id 2
    label "NA-Chicago-Edge-Router"
    AS "65001"
    ip "10.0.0.3"
    bandwidth 500000000
    packet_loss 0.08
    location "Chicago"
  ]

  node [
    id 3
    label "NA-LA-Edge-Router"
    AS "65001"
    ip "10.0.0.4"
    bandwidth 500000000
    packet_loss 0.08
    location "Los_Angeles"
  ]

  node [
    id 4
    label "NA-Toronto-Core-Router"
    AS "65002"
    ip "192.168.0.1"
    bandwidth 1000000000
    packet_loss 0.06
    location "Toronto"
  ]

  node [
    id 5
    label "NA-Vancouver-Core-Router"
    AS "65002"
    ip "192.168.0.2"
    bandwidth 1000000000
    packet_loss 0.06
    location "Vancouver"
  ]

  node [
    id 6
    label "NA-Seattle-Edge-Router"
    AS "65002"
    ip "192.168.0.3"
    bandwidth 500000000
    packet_loss 0.1
    location "Seattle"
  ]

  node [
    id 7
    label "NA-Miami-Edge-Router"
    AS "65002"
    ip "192.168.0.4"
    bandwidth 500000000
    packet_loss 0.1
    location "Miami"
  ]

  node [
    id 8
    label "EU-London-Core-Router"
    AS "65003"
    ip "172.16.0.1"
    bandwidth 1000000000
    packet_loss 0.04
    location "London"
  ]

  node [
    id 9
    label "EU-Frankfurt-Core-Router"
    AS "65003"
    ip "172.16.0.2"
    bandwidth 1000000000
    packet_loss 0.04
    location "Frankfurt"
  ]

  node [
    id 10
    label "EU-Paris-Edge-Router"
    AS "65003"
    ip "172.16.0.3"
    bandwidth 500000000
    packet_loss 0.07
    location "Paris"
  ]

  node [
    id 11
    label "EU-Amsterdam-Research-Core"
    AS "65004"
    ip "203.0.113.1"
    bandwidth 10000000000
    packet_loss 0.02
    location "Amsterdam"
  ]

  node [
    id 12
    label "EU-Zurich-Research-Core"
    AS "65004"
    ip "203.0.113.2"
    bandwidth 10000000000
    packet_loss 0.02
    location "Zurich"
  ]

  node [
    id 13
    label "EU-Stockholm-Research-Edge"
    AS "65004"
    ip "203.0.113.3"
    bandwidth 1000000000
    packet_loss 0.05
    location "Stockholm"
  ]

  node [
    id 14
    label "AS-Tokyo-Core-Router"
    AS "65005"
    ip "198.51.100.1"
    bandwidth 1000000000
    packet_loss 0.06
    location "Tokyo"
  ]

  node [
    id 15
    label "AS-Seoul-Core-Router"
    AS "65005"
    ip "198.51.100.2"
    bandwidth 1000000000
    packet_loss 0.06
    location "Seoul"
  ]

  node [
    id 16
    label "AS-HongKong-Edge-Router"
    AS "65005"
    ip "198.51.100.3"
    bandwidth 500000000
    packet_loss 0.1
    location "Hong_Kong"
  ]

  node [
    id 17
    label "AS-Singapore-Edge-Router"
    AS "65005"
    ip "198.51.100.4"
    bandwidth 500000000
    packet_loss 0.1
    location "Singapore"
  ]

  node [
    id 18
    label "AS-Mumbai-Cloud-Core"
    AS "65006"
    ip "10.1.0.1"
    bandwidth 10000000000
    packet_loss 0.03
    location "Mumbai"
  ]

  node [
    id 19
    label "AS-Bangalore-Cloud-Core"
    AS "65006"
    ip "10.1.0.2"
    bandwidth 10000000000
    packet_loss 0.03
    location "Bangalore"
  ]

  node [
    id 20
    label "AS-Delhi-Cloud-Edge"
    AS "65006"
    ip "10.1.0.3"
    bandwidth 1000000000
    packet_loss 0.08
    location "Delhi"
  ]

  node [
    id 21
    label "AS-Chennai-Cloud-Edge"
    AS "65006"
    ip "10.1.0.4"
    bandwidth 1000000000
    packet_loss 0.08
    location "Chennai"
  ]

  node [
    id 22
    label "SA-SaoPaulo-Core-Router"
    AS "65007"
    ip "10.2.0.1"
    bandwidth 500000000
    packet_loss 0.12
    location "Sao_Paulo"
  ]

  node [
    id 23
    label "SA-BuenosAires-Core-Router"
    AS "65007"
    ip "10.2.0.2"
    bandwidth 500000000
    packet_loss 0.12
    location "Buenos_Aires"
  ]

  node [
    id 24
    label "SA-Santiago-Edge-Router"
    AS "65007"
    ip "10.2.0.3"
    bandwidth 200000000
    packet_loss 0.15
    location "Santiago"
  ]

  node [
    id 25
    label "AF-Johannesburg-Core-Router"
    AS "65008"
    ip "10.3.0.1"
    bandwidth 500000000
    packet_loss 0.15
    location "Johannesburg"
  ]

  node [
    id 26
    label "AF-Cairo-Core-Router"
    AS "65008"
    ip "10.3.0.2"
    bandwidth 500000000
    packet_loss 0.15
    location "Cairo"
  ]

  node [
    id 27
    label "AF-Lagos-Edge-Router"
    AS "65008"
    ip "10.3.0.3"
    bandwidth 200000000
    packet_loss 0.2
    location "Lagos"
  ]

  node [
    id 28
    label "OC-Sydney-Core-Router"
    AS "65009"
    ip "10.4.0.1"
    bandwidth 500000000
    packet_loss 0.08
    location "Sydney"
  ]

  node [
    id 29
    label "OC-Auckland-Edge-Router"
    AS "65009"
    ip "10.4.0.2"
    bandwidth 200000000
    packet_loss 0.12
    location "Auckland"
  ]


  edge [
    source 0
    target 1
    latency "2ms"
    bandwidth 1000000000
    packet_loss 0.05
  ]

  edge [
    source 0
    target 2
    latency "12ms"
    bandwidth 500000000
    packet_loss 0.08
  ]

  edge [
    source 1
    target 3
    latency "35ms"
    bandwidth 500000000
    packet_loss 0.08
  ]

  edge [
    source 2
    target 3
    latency "25ms"
    bandwidth 500000000
    packet_loss 0.08
  ]

  edge [
    source 4
    target 5
    latency "25ms"
    bandwidth 1000000000
    packet_loss 0.06
  ]

  edge [
    source 4
    target 6
    latency "15ms"
    bandwidth 500000000
    packet_loss 0.1
  ]

  edge [
    source 5
    target 7
    latency "35ms"
    bandwidth 500000000
    packet_loss 0.1
  ]

  edge [
    source 6
    target 7
    latency "20ms"
    bandwidth 500000000
    packet_loss 0.1
  ]

  edge [
    source 8
    target 9
    latency "8ms"
    bandwidth 1000000000
    packet_loss 0.04
  ]

  edge [
    source 8
    target 10
    latency "5ms"
    bandwidth 500000000
    packet_loss 0.07
  ]

  edge [
    source 9
    target 10
    latency "6ms"
    bandwidth 500000000
    packet_loss 0.07
  ]

  edge [
    source 11
    target 12
    latency "10ms"
    bandwidth 10000000000
    packet_loss 0.02
  ]

  edge [
    source 11
    target 13
    latency "15ms"
    bandwidth 1000000000
    packet_loss 0.05
  ]

  edge [
    source 12
    target 13
    latency "12ms"
    bandwidth 1000000000
    packet_loss 0.05
  ]

  edge [
    source 14
    target 15
    latency "20ms"
    bandwidth 1000000000
    packet_loss 0.06
  ]

  edge [
    source 14
    target 16
    latency "25ms"
    bandwidth 500000000
    packet_loss 0.1
  ]

  edge [
    source 15
    target 17
    latency "40ms"
    bandwidth 500000000
    packet_loss 0.1
  ]

  edge [
    source 16
    target 17
    latency "30ms"
    bandwidth 500000000
    packet_loss 0.1
  ]

  edge [
    source 18
    target 19
    latency "15ms"
    bandwidth 10000000000
    packet_loss 0.03
  ]

  edge [
    source 18
    target 20
    latency "8ms"
    bandwidth 1000000000
    packet_loss 0.08
  ]

  edge [
    source 19
    target 21
    latency "6ms"
    bandwidth 1000000000
    packet_loss 0.08
  ]

  edge [
    source 20
    target 21
    latency "12ms"
    bandwidth 1000000000
    packet_loss 0.08
  ]

  edge [
    source 22
    target 23
    latency "20ms"
    bandwidth 500000000
    packet_loss 0.12
  ]

  edge [
    source 22
    target 24
    latency "25ms"
    bandwidth 200000000
    packet_loss 0.15
  ]

  edge [
    source 23
    target 24
    latency "15ms"
    bandwidth 200000000
    packet_loss 0.15
  ]

  edge [
    source 25
    target 26
    latency "80ms"
    bandwidth 500000000
    packet_loss 0.15
  ]

  edge [
    source 25
    target 27
    latency "45ms"
    bandwidth 200000000
    packet_loss 0.2
  ]

  edge [
    source 26
    target 27
    latency "60ms"
    bandwidth 200000000
    packet_loss 0.2
  ]

  edge [
    source 28
    target 29
    latency "20ms"
    bandwidth 200000000
    packet_loss 0.12
  ]


  edge [
    source 0
    target 4
    latency "8ms"
    bandwidth 1000000000
    packet_loss 0.05
  ]

  edge [
    source 1
    target 5
    latency "30ms"
    bandwidth 500000000
    packet_loss 0.08
  ]

  edge [
    source 2
    target 6
    latency "12ms"
    bandwidth 500000000
    packet_loss 0.1
  ]

  edge [
    source 3
    target 7
    latency "40ms"
    bandwidth 200000000
    packet_loss 0.12
  ]

  edge [
    source 0
    target 8
    latency "75ms"
    bandwidth 200000000
    packet_loss 0.3
  ]

  edge [
    source 1
    target 9
    latency "80ms"
    bandwidth 200000000
    packet_loss 0.3
  ]

  edge [
    source 4
    target 10
    latency "70ms"
    bandwidth 150000000
    packet_loss 0.35
  ]

  edge [
    source 7
    target 8
    latency "85ms"
    bandwidth 100000000
    packet_loss 0.4
  ]

  edge [
    source 8
    target 11
    latency "5ms"
    bandwidth 10000000000
    packet_loss 0.02
  ]

  edge [
    source 9
    target 12
    latency "8ms"
    bandwidth 10000000000
    packet_loss 0.02
  ]

  edge [
    source 10
    target 13
    latency "12ms"
    bandwidth 1000000000
    packet_loss 0.05
  ]

  edge [
    source 3
    target 14
    latency "120ms"
    bandwidth 150000000
    packet_loss 0.5
  ]

  edge [
    source 3
    target 15
    latency "125ms"
    bandwidth 150000000
    packet_loss 0.5
  ]

  edge [
    source 7
    target 16
    latency "140ms"
    bandwidth 100000000
    packet_loss 0.6
  ]

  edge [
    source 9
    target 14
    latency "180ms"
    bandwidth 100000000
    packet_loss 0.7
  ]

  edge [
    source 10
    target 15
    latency "200ms"
    bandwidth 80000000
    packet_loss 0.8
  ]

  edge [
    source 13
    target 16
    latency "220ms"
    bandwidth 50000000
    packet_loss 0.9
  ]

  edge [
    source 14
    target 18
    latency "25ms"
    bandwidth 1000000000
    packet_loss 0.06
  ]

  edge [
    source 15
    target 19
    latency "30ms"
    bandwidth 1000000000
    packet_loss 0.06
  ]

  edge [
    source 16
    target 20
    latency "15ms"
    bandwidth 500000000
    packet_loss 0.1
  ]

  edge [
    source 17
    target 21
    latency "20ms"
    bandwidth 500000000
    packet_loss 0.1
  ]

  edge [
    source 3
    target 22
    latency "150ms"
    bandwidth 100000000
    packet_loss 0.8
  ]

  edge [
    source 7
    target 23
    latency "160ms"
    bandwidth 80000000
    packet_loss 0.9
  ]

  edge [
    source 7
    target 24
    latency "140ms"
    bandwidth 50000000
    packet_loss 0.10
  ]

  edge [
    source 10
    target 25
    latency "130ms"
    bandwidth 80000000
    packet_loss 0.9
  ]

  edge [
    source 13
    target 26
    latency "140ms"
    bandwidth 50000000
    packet_loss 0.10
  ]

  edge [
    source 13
    target 27
    latency "160ms"
    bandwidth 30000000
    packet_loss 0.12
  ]

  edge [
    source 17
    target 25
    latency "250ms"
    bandwidth 50000000
    packet_loss 0.12
  ]

  edge [
    source 17
    target 26
    latency "220ms"
    bandwidth 30000000
    packet_loss 0.14
  ]

  edge [
    source 21
    target 27
    latency "280ms"
    bandwidth 20000000
    packet_loss 0.16
  ]

  edge [
    source 24
    target 27
    latency "200ms"
    bandwidth 20000000
    packet_loss 0.15
  ]

  edge [
    source 17
    target 28
    latency "80ms"
    bandwidth 100000000
    packet_loss 0.4
  ]

  edge [
    source 17
    target 29
    latency "90ms"
    bandwidth 50000000
    packet_loss 0.5
  ]

  edge [
    source 3
    target 28
    latency "160ms"
    bandwidth 50000000
    packet_loss 0.7
  ]

  edge [
    source 3
    target 29
    latency "170ms"
    bandwidth 30000000
    packet_loss 0.8
  ]

  edge [
    source 10
    target 28
    latency "220ms"
    bandwidth 30000000
    packet_loss 0.10
  ]

  edge [
    source 13
    target 29
    latency "240ms"
    bandwidth 20000000
    packet_loss 0.12
  ]


  edge [
    source 2
    target 10
    latency "85ms"
    bandwidth 50000000
    packet_loss 0.6
    comment "Backup transatlantic route"
  ]

  edge [
    source 6
    target 13
    latency "75ms"
    bandwidth 80000000
    packet_loss 0.5
    comment "Backup transatlantic route"
  ]

  edge [
    source 2
    target 16
    latency "135ms"
    bandwidth 80000000
    packet_loss 0.8
    comment "Backup transpacific route"
  ]

  edge [
    source 6
    target 17
    latency "145ms"
    bandwidth 50000000
    packet_loss 0.9
    comment "Backup transpacific route"
  ]

  edge [
    source 24
    target 25
    latency "280ms"
    bandwidth 10000000
    packet_loss 0.20
    comment "Backup intercontinental route"
  ]

  edge [
    source 22
    target 27
    latency "260ms"
    bandwidth 15000000
    packet_loss 0.18
    comment "Backup intercontinental route"
  ]

  edge [
    source 26
    target 28
    latency "300ms"
    bandwidth 10000000
    packet_loss 0.22
    comment "Backup intercontinental route"
  ]

  edge [
    source 18
    target 22
    latency "200ms"
    bandwidth 50000000
    packet_loss 0.15
    comment "Connect Asia to South America"
  ]

  edge [
    source 19
    target 25
    latency "180ms"
    bandwidth 50000000
    packet_loss 0.15
    comment "Connect Asia to Africa"
  ]

  edge [
    source 21
    target 28
    latency "250ms"
    bandwidth 30000000
    packet_loss 0.18
    comment "Connect Asia to Oceania"
  ]

  edge [
    source 24
    target 26
    latency "220ms"
    bandwidth 20000000
    packet_loss 0.16
    comment "Connect South America to Africa"
  ]
]
