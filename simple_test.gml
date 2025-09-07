graph [
  directed 0
  node [
    id 0
    label "Node0"
  ]
  node [
    id 1
    label "Node1"
  ]
  node [
    id 2
    label "Node2"
  ]
  node [
    id 3
    label "Node3"
  ]
  edge [
    source 0
    target 1
    latency "10ms"
    bandwidth "1Gbit"
  ]
  edge [
    source 1
    target 2
    latency "10ms"
    bandwidth "1Gbit"
  ]
  edge [
    source 2
    target 3
    latency "10ms"
    bandwidth "1Gbit"
  ]
  edge [
    source 3
    target 0
    latency "10ms"
    bandwidth "1Gbit"
  ]
]