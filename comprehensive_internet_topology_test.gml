graph [
  comment "Comprehensive Internet Topology Test - Multi-AS Network with Complex Structure"
  directed 0

  # AS 65001 - Large ISP Network (10.0.0.0/24)
  node [
    id 0
    label "ISP_A_Core_Router_1"
    AS "65001"
    ip "10.0.0.1"
    bandwidth 1000000000
    packet_loss 0.05
    location "New_York"
  ]

  node [
    id 1
    label "ISP_A_Core_Router_2"
    AS "65001"
    ip "10.0.0.2"
    bandwidth 1000000000
    packet_loss 0.05
    location "New_York"
  ]

  node [
    id 2
    label "ISP_A_Edge_Router_NYC"
    AS "65001"
    ip "10.0.0.3"
    bandwidth 100000000
    packet_loss 0.1
    location "New_York"
  ]

  node [
    id 3
    label "ISP_A_Edge_Router_LAX"
    AS "65001"
    ip "10.0.0.4"
    bandwidth 100000000
    packet_loss 0.1
    location "Los_Angeles"
  ]

  # AS 65002 - Regional ISP Network (192.168.0.0/24)
  node [
    id 4
    label "ISP_B_Core_Router_1"
    AS "65002"
    ip "192.168.0.1"
    bandwidth 500000000
    packet_loss 0.08
    location "Chicago"
  ]

  node [
    id 5
    label "ISP_B_Core_Router_2"
    AS "65002"
    ip "192.168.0.2"
    bandwidth 500000000
    packet_loss 0.08
    location "Chicago"
  ]

  node [
    id 6
    label "ISP_B_Edge_Router_CHI"
    AS "65002"
    ip "192.168.0.3"
    bandwidth 100000000
    packet_loss 0.15
    location "Chicago"
  ]

  node [
    id 7
    label "ISP_B_Edge_Router_SEA"
    AS "65002"
    ip "192.168.0.4"
    bandwidth 100000000
    packet_loss 0.15
    location "Seattle"
  ]

  # AS 65003 - Data Center Network (172.16.0.0/24)
  node [
    id 8
    label "DC_A_Router_1"
    AS "65003"
    ip "172.16.0.1"
    bandwidth 10000000000
    packet_loss 0.01
    location "Ashburn"
  ]

  node [
    id 9
    label "DC_A_Router_2"
    AS "65003"
    ip "172.16.0.2"
    bandwidth 10000000000
    packet_loss 0.01
    location "Ashburn"
  ]

  node [
    id 10
    label "DC_A_Load_Balancer"
    AS "65003"
    ip "172.16.0.3"
    bandwidth 40000000000
    packet_loss 0.005
    location "Ashburn"
  ]

  # AS 65004 - International Network (203.0.113.0/24)
  node [
    id 11
    label "INT_Gateway_Europe"
    AS "65004"
    ip "203.0.113.1"
    bandwidth 200000000
    packet_loss 0.2
    location "London"
  ]

  node [
    id 12
    label "INT_Gateway_Asia"
    AS "65004"
    ip "203.0.113.2"
    bandwidth 200000000
    packet_loss 0.2
    location "Singapore"
  ]

  # AS 65005 - University Network (198.51.100.0/24)
  node [
    id 13
    label "UNI_Campus_Core"
    AS "65005"
    ip "198.51.100.1"
    bandwidth 1000000000
    packet_loss 0.02
    location "Cambridge"
  ]

  node [
    id 14
    label "UNI_Research_Network"
    AS "65005"
    ip "198.51.100.2"
    bandwidth 10000000000
    packet_loss 0.01
    location "Cambridge"
  ]

  # Intra-AS Connections (High-speed, low-latency)

  # AS 65001 Internal Network
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
    latency "5ms"
    bandwidth 100000000
    packet_loss 0.1
  ]

  edge [
    source 1
    target 3
    latency "5ms"
    bandwidth 100000000
    packet_loss 0.1
  ]

  # AS 65002 Internal Network
  edge [
    source 4
    target 5
    latency "3ms"
    bandwidth 500000000
    packet_loss 0.08
  ]

  edge [
    source 4
    target 6
    latency "8ms"
    bandwidth 100000000
    packet_loss 0.15
  ]

  edge [
    source 5
    target 7
    latency "8ms"
    bandwidth 100000000
    packet_loss 0.15
  ]

  # AS 65003 Internal Network (Data Center)
  edge [
    source 8
    target 9
    latency "1ms"
    bandwidth 10000000000
    packet_loss 0.01
  ]

  edge [
    source 8
    target 10
    latency "2ms"
    bandwidth 40000000000
    packet_loss 0.005
  ]

  edge [
    source 9
    target 10
    latency "2ms"
    bandwidth 40000000000
    packet_loss 0.005
  ]

  # AS 65004 Internal Network (International)
  edge [
    source 11
    target 12
    latency "200ms"
    bandwidth 200000000
    packet_loss 0.2
  ]

  # AS 65005 Internal Network (University)
  edge [
    source 13
    target 14
    latency "1ms"
    bandwidth 10000000000
    packet_loss 0.01
  ]

  # Inter-AS Connections (Variable latency and bandwidth)

  # ISP A to ISP B (Cross-country backbone)
  edge [
    source 2
    target 6
    latency "25ms"
    bandwidth 100000000
    packet_loss 0.3
  ]

  edge [
    source 3
    target 7
    latency "30ms"
    bandwidth 100000000
    packet_loss 0.3
  ]

  # ISP A to Data Center (High-speed internet exchange)
  edge [
    source 0
    target 8
    latency "15ms"
    bandwidth 500000000
    packet_loss 0.1
  ]

  edge [
    source 1
    target 9
    latency "18ms"
    bandwidth 500000000
    packet_loss 0.1
  ]

  # ISP B to Data Center (Regional connection)
  edge [
    source 4
    target 8
    latency "20ms"
    bandwidth 200000000
    packet_loss 0.2
  ]

  edge [
    source 5
    target 9
    latency "22ms"
    bandwidth 200000000
    packet_loss 0.2
  ]

  # International Connections (High latency, lower bandwidth)
  edge [
    source 0
    target 11
    latency "80ms"
    bandwidth 50000000
    packet_loss 0.5
  ]

  edge [
    source 1
    target 12
    latency "150ms"
    bandwidth 50000000
    packet_loss 0.5
  ]

  edge [
    source 4
    target 11
    latency "75ms"
    bandwidth 50000000
    packet_loss 0.5
  ]

  edge [
    source 5
    target 12
    latency "140ms"
    bandwidth 50000000
    packet_loss 0.5
  ]

  # University to ISP A (Research network connection)
  edge [
    source 13
    target 0
    latency "10ms"
    bandwidth 1000000000
    packet_loss 0.05
  ]

  edge [
    source 14
    target 1
    latency "12ms"
    bandwidth 1000000000
    packet_loss 0.05
  ]

  # University to Data Center (High-speed research connection)
  edge [
    source 13
    target 10
    latency "8ms"
    bandwidth 10000000000
    packet_loss 0.02
  ]

  edge [
    source 14
    target 10
    latency "8ms"
    bandwidth 10000000000
    packet_loss 0.02
  ]

  # International to University (Research collaboration)
  edge [
    source 11
    target 13
    latency "15ms"
    bandwidth 100000000
    packet_loss 0.1
  ]

  edge [
    source 12
    target 14
    latency "180ms"
    bandwidth 50000000
    packet_loss 0.3
  ]
]