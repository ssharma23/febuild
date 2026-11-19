#!/bin/zsh
# Sync Workbench app source to the workspace and deploy.
export DATABRICKS_CONFIG_PROFILE=fevm-demo-dnb
D=/opt/homebrew/bin/databricks
SRC=/Users/sonam.s/meridianlink_lending_story/app
DST=/Workspace/Users/sonam.s@databricks.com/meridianlink_lending/app
$D sync $SRC $DST --full >/dev/null 2>&1
$D apps deploy meridianlink-lending-workbench --source-code-path $DST --timeout 20m -o json | python3 -c "import json,sys;d=json.load(sys.stdin);print(d.get('status'))"
