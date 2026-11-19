#!/usr/bin/env python3
"""Run SQL on the demo warehouse. Usage: q.py "SQL" | q.py -f file.sql (statements split on ;\n)"""
import json, subprocess, sys, time
WH="6ea47fe72fea6233"; CLI=["/opt/homebrew/bin/databricks","-p","fevm-demo-dnb"]
def run(sql):
    body={"statement":sql,"warehouse_id":WH,"wait_timeout":"50s","on_wait_timeout":"CONTINUE","format":"JSON_ARRAY","disposition":"INLINE"}
    r=json.loads(subprocess.run(CLI+["api","post","/api/2.0/sql/statements","--json",json.dumps(body)],capture_output=True,text=True).stdout or "{}")
    while r.get("status",{}).get("state") in ("PENDING","RUNNING"):
        time.sleep(3); r=json.loads(subprocess.run(CLI+["api","get",f"/api/2.0/sql/statements/{r['statement_id']}"],capture_output=True,text=True).stdout)
    st=r.get("status",{})
    if st.get("state")!="SUCCEEDED":
        print("ERROR:",st.get("error",{}).get("message",r)[:1500]); return False
    cols=[c["name"] for c in r.get("manifest",{}).get("schema",{}).get("columns",[])]
    rows=r.get("result",{}).get("data_array",[]) or []
    if cols: print(" | ".join(cols))
    for row in rows[:200]: print(" | ".join("" if v is None else str(v) for v in row))
    return True
if __name__=="__main__":
    if sys.argv[1]=="-f":
        stmts=[s.strip() for s in open(sys.argv[2]).read().split(";\n") if s.strip() and not all(l.strip().startswith("--") or not l.strip() for l in s.splitlines())]
    else: stmts=[sys.argv[1]]
    for s in stmts:
        print(">>",s.splitlines()[0][:100]); 
        if not run(s) and "--keep-going" not in sys.argv: sys.exit(1)
