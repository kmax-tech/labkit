import re, pathlib, subprocess
roots = ["/Users/max/projects/counterfactual-worlds","/Users/max/projects/fallacy-datasets","/Users/max/projects/fallacy-detection","/Users/max/projects/paper-organization","/Users/max/projects/thesis-nair","/Users/max/projects/uniagent"]
files=[]
for root in roots:
    out = subprocess.run(["find",root,"-name",".venv","-prune","-o","-name","PROTOCOL-*.md","-print"],capture_output=True,text=True).stdout
    files += [l for l in out.splitlines() if l.strip()]
AUDIT = ("preflight audit","preflight-audit","analysis audit","auswertungs-audit","analyse-audit")
OTHER = ("changed","clarified terms","geklärte begriffe","frozen before run","resolution check","auflösungsprobe")
for f in sorted(files):
    p = pathlib.Path(f)
    lines = p.read_text(encoding="utf-8").splitlines()
    hits=[]; i=0
    while i < len(lines):
        l = lines[i]
        m = re.match(r'^\s*[-*]\s+\*\*(.+?)(?::|†|\*\*)', l)
        name = m.group(1).strip().lower().rstrip(':').rstrip('†').strip() if m else None
        kind = None
        if name:
            if any(name.startswith(x) for x in AUDIT): kind="AUDIT"
            elif any(name.startswith(x) for x in OTHER): kind="OTHER"
        if kind:
            block=[l]; j=i+1
            while j < len(lines) and not re.match(r'^\s*[-*]\s+\*\*', lines[j]) and not lines[j].startswith('#'):
                block.append(lines[j]); j+=1
            hits.append((kind,i+1,"\n".join(block).rstrip())); i=j
        else: i+=1
    if any(k=="AUDIT" for k,_,_ in hits):
        print("="*100); print("FILE:", f)
        for k,ln,b in hits:
            print(f"--- [{k}] line {ln} ---"); print(b)
