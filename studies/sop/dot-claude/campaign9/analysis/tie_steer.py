import re,glob,os,sys,statistics as st
from datetime import datetime
R="/mnt/remote_spinny/20261024_monerosim_research_effort"
cells=["es_stock_a030_f6_s1","es_stock_a035_f6_s1","es_stock_a045_f6_s1","es_stock_a045_f3_s1","share_sop_a045_f6_s1"]
ts=lambda l:datetime.strptime(l[:23],"%Y-%m-%d %H:%M:%S.%f")
def log(d,h):
    fs=sorted(glob.glob(f"{d}/shadow.data/hosts/{h}/monerod*.stdout"),key=os.path.getsize); return fs[-1] if fs else None
def parse(d,h):
    F={};Rc={};f=log(d,h)
    if not f: return F,Rc
    for l in open(f,errors="replace"):
        if "Found block" in l:
            m=re.search(r"<([0-9a-f]{64})> at height (\d+)",l)
            if m:
                try:F[m.group(1)]=(ts(l),int(m.group(2)))
                except ValueError:pass
        if "<" in l:
            m=re.search(r"<([0-9a-f]{64})>",l)
            if m and m.group(1) not in Rc:
                try:Rc[m.group(1)]=ts(l)
                except ValueError:pass
    return F,Rc
def pct(v,p):
    v=sorted(v);return v[min(len(v)-1,int(round(p*(len(v)-1))))]
def med(v):return f"{st.median(v):.2f}" if v else "-"
print("| cell | contested | neg-react | ties(react>=0) | react med/p90 s | n r<=10s | steer_far r<=10s | steer_far | steer_near | atk@far med s | hon@far med s |")
print("|---|---|---|---|---|---|---|---|---|---|---|")
for c in cells:
    ds=sorted(glob.glob(f"{R}/*/archived_runs/*_sop_v4_gamma_72h__{c}"),key=lambda p:os.path.basename(p)[:15])
    d=ds[-1]
    A,_=parse(d,"attacker-miner"); H={h:parse(d,h) for h in("honest-001","honest-002")}
    B={h:parse(d,h)[1] for h in("attacker-bridge","attacker-bridge-2")}
    atk={}
    for b,(t,h) in A.items():
        if h>994 and (h not in atk or t<atk[h][0]): atk[h]=(t,b)
    hon={}
    for n,(F,_) in H.items():
        for b,(t,h) in F.items():
            if h>994 and (h not in hon or t<hon[h][0]): hon[h]=(t,b,n)
    cont=[h for h in hon if h in atk]
    neg=0;sub=[];react=[];sf=[];sn=[];af=[];hf=[]
    def first(n,b,h):  # receipt time at n of block b
        F,Rc=H[n]
        if b in F: return F[b][0]
        return Rc.get(b)
    for h in cont:
        th,hb,fn=hon[h];ta,ab=atk[h]
        rb=[B[x][ab] for x in B if ab in B[x]]
        if not rb: continue
        r=(min(rb)-th).total_seconds()
        if r<0: neg+=1;continue
        react.append(r)
        cur=len(sf)
        far="honest-002" if fn=="honest-001" else "honest-001"
        for who,lst in((far,sf),(fn,sn)):
            a=first(who,ab,h);o=first(who,hb,h)
            if who==far:
                if a is not None:af.append((a-th).total_seconds())
                if o is not None:hf.append((o-th).total_seconds())
            if a is not None and o is not None: lst.append(a<o)
            elif a is not None: lst.append(True)
            elif o is not None: lst.append(False)
        if r<=10 and len(sf)>cur: sub.append((sf[-1],r))
    fr=lambda l:f"{sum(l)/len(l):.3f} (n={len(l)})" if l else "-"
    print(f"| {c} | {len(cont)} | {neg} | {len(react)} | {med(react)}/{pct(react,.9):.2f} | {len(sub)} | {sum(x for x,_ in sub)/max(1,len(sub)):.3f} | {fr(sf)} | {fr(sn)} | {med(af)} | {med(hf)} |" if react else f"| {c} | {len(cont)} | {neg} | 0 |")
    print(f"<!-- {d} -->",file=sys.stderr)
