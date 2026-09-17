#!/usr/bin/env python3
import json
t = open("/tmp/claude-1006/-home-lever65-monerosim-work-monerosim/e9d9c24f-f881-46d0-9095-c61aabf017f3/scratchpad/chartdata_full.txt").read()
d = json.loads(t.split("CHARTDATA=")[1])
c = d["capstone"]
print("final_ctr=%s final_bor=%.3f max_ctr=%d bor_max=%.3f npts=%d"
      % (c["final_ctr"], c["final_bor"], max(p[1] for p in c["ctr"]),
         max(p[1] for p in c["bor"]), len(c["ctr"])))
print("CAP_CTR_JSON=" + json.dumps(c["ctr"]))
