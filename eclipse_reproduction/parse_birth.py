#!/usr/bin/env python3
import json
t = open("/tmp/claude-1006/-home-lever65-monerosim-work-monerosim/e9d9c24f-f881-46d0-9095-c61aabf017f3/scratchpad/chartdata_birth.txt").read()
d = json.loads(t.split("CHARTDATA=")[1])
c = d["capstone"]  # chartdata puts the extra run under "capstone"
# keep only points from when the target exists (ctr entries begin then)
print("CTR_JSON=" + json.dumps(c["ctr"]))
print("final_ctr=%s npts=%d" % (c["final_ctr"], len(c["ctr"])))
