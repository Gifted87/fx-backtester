import json

log_file = r"C:\Users\hp\.gemini\antigravity-ide\brain\a3a415ef-706a-4778-a3b8-181157ce9b05\.system_generated\logs\transcript.jsonl"
with open(log_file, "r", encoding="utf-8") as f:
    for i, line in enumerate(f):
        if i >= 1175:
            d = json.loads(line)
            if d.get("source") == "USER_EXPLICIT":
                print(f"=== USER at {i}: {d.get('content')[:120]}")
            elif d.get("tool_calls"):
                for tc in d["tool_calls"]:
                    name = tc.get("name")
                    args = str(tc.get("args"))[:100]
                    print(f"[{i}] TOOL: {name} -> {args}")
            elif d.get("type") == "PLANNER_RESPONSE":
                print(f"[{i}] PLANNER: {str(d.get('content'))[:100]}")
