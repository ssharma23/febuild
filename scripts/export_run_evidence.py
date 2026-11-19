"""Convert Databricks job-run exports (jobs export-run JSON) into .ipynb (with outputs) + .md text evidence."""
import json, re, base64, urllib.parse, sys, os, html as H
def strip_ansi(s): return re.sub(r"\x1b\[[0-9;]*m", "", s or "")
def result_text(r):
    if not r: return ""
    t = r.get("type")
    if t == "listResults": return "\n".join(result_text(x) for x in r.get("data", []))
    if t in ("raw", "ansi", "text"): return strip_ansi(r.get("data") if isinstance(r.get("data"), str) else json.dumps(r.get("data")))
    if t == "table":
        cols = [c.get("name") for c in r.get("schema", [])]; rows = r.get("data", [])[:50]
        out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)] + ["| " + " | ".join(str(v) for v in row) + " |" for row in rows]
        if len(r.get("data", [])) > 50: out.append(f"... ({len(r['data'])} rows shown 50)")
        return "\n".join(out)
    if t == "html": return re.sub(r"<[^>]+>", " ", H.unescape(str(r.get("data"))))[:4000]
    if t == "error": return "ERROR: " + strip_ansi(str(r.get("summary") or r.get("data")))[:3000]
    return strip_ansi(str(r.get("data")))[:3000]
def convert(src, name, run_id, task_run_id, out_dir):
    d = json.load(open(src)); content = d["views"][0]["content"]
    m = re.search(r"__DATABRICKS_NOTEBOOK_MODEL = '([^']+)'", content)
    model = json.loads(urllib.parse.unquote(base64.b64decode(m.group(1)).decode()))
    cells, md = [], [f"# Run evidence: `{name}`\n", f"- Job run id: `{run_id}` · task run id: `{task_run_id}` · exported from Databricks job run (serverless)\n"]
    for c in sorted(model["commands"], key=lambda c: c.get("position", 0)):
        code = c.get("command", ""); out = result_text(c.get("results"))
        if c.get("error"): out += "\nERROR: " + strip_ansi(str(c.get("error")))[:3000]
        if code.startswith("%md"):
            cells.append({"cell_type": "markdown", "metadata": {}, "source": code[3:].lstrip("\n")}); md.append(code[3:].strip() + "\n")
            continue
        cells.append({"cell_type": "code", "metadata": {}, "execution_count": None, "source": code,
                      "outputs": ([{"output_type": "stream", "name": "stdout", "text": out}] if out.strip() else [])})
        md.append("```python\n" + code.strip() + "\n```\n")
        if out.strip(): md.append("**Output:**\n```text\n" + out.strip()[:6000] + "\n```\n")
    nb = {"nbformat": 4, "nbformat_minor": 5, "metadata": {"language_info": {"name": "python"}, "databricks_run": {"job_run_id": run_id, "task_run_id": task_run_id}}, "cells": cells}
    json.dump(nb, open(os.path.join(out_dir, f"{name}.ipynb"), "w"), indent=1)
    open(os.path.join(out_dir, f"{name}.md"), "w").write("\n".join(md))
if __name__ == "__main__":
    convert(*sys.argv[1:6])
