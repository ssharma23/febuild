import sys, json, time, subprocess, os
SP = "01f1e3d666d91574bd4ffb20588c2ed6"
env = {**os.environ, "DATABRICKS_CONFIG_PROFILE": "fevm-demo-dnb"}
def api(m, p, body=None):
    cmd = ["/opt/homebrew/bin/databricks", "api", m, p] + (["--json", json.dumps(body)] if body else [])
    return json.loads(subprocess.run(cmd, capture_output=True, text=True, env=env).stdout or "{}")
def ask(q):
    r = api("post", f"/api/2.0/genie/spaces/{SP}/start-conversation", {"content": q})
    cid, mid = r["conversation_id"], r["message_id"]
    for _ in range(60):
        m = api("get", f"/api/2.0/genie/spaces/{SP}/conversations/{cid}/messages/{mid}")
        if m.get("status") in ("COMPLETED", "FAILED", "CANCELLED"): break
        time.sleep(3)
    out = [f"Q: {q}  [{m.get('status')}]"]
    for a in m.get("attachments", []):
        if "text" in a: out.append("TEXT: " + a["text"]["content"][:600])
        if "query" in a:
            out.append("SQL: " + a["query"]["query"].replace("\n", " ")[:400])
            qr = api("get", f"/api/2.0/genie/spaces/{SP}/conversations/{cid}/messages/{mid}/attachments/{a['attachment_id']}/query-result")
            rows = qr.get("statement_response", {}).get("result", {}).get("data_array", [])
            out.append("ROWS: " + json.dumps(rows[:8]))
    return "\n".join(out)
for q in sys.argv[1:]:
    print(ask(q)); print("-" * 80)
