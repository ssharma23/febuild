#!/bin/bash
# Usage: pstatus.sh [update_id]  -- shows pipeline update state + recent errors
D=/opt/homebrew/bin/databricks; P=$(cat /Users/sonam.s/meridianlink_lending_story/.pipeline_id)
$D pipelines list-updates $P -p fevm-demo-dnb --max-results 1 -o json | python3 -c "import json,sys;u=json.load(sys.stdin)['updates'][0];print(u['update_id'],u['state'])"
$D pipelines list-pipeline-events $P -p fevm-demo-dnb --max-results 60 -o json | python3 -c "
import json,sys
ev=json.load(sys.stdin); ev=ev if isinstance(ev,list) else ev.get('events',[])
for e in ev:
  if e.get('level') in ('ERROR','WARN') or e.get('event_type') in ('update_progress',):
    m=e.get('message','')
    err=e.get('error',{}).get('exceptions',[{}])
    print(e['timestamp'][11:19],e.get('level'),e.get('event_type'),m[:200])
    if e.get('level')=='ERROR' and err: print('   ',(err[0].get('message') or '')[:900])
" | head -40
