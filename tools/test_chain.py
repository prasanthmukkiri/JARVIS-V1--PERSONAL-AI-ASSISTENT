import requests
import time

BASE = "http://127.0.0.1:5555"

# 1. Send a chain
goal = "open chrome then search weather in hyderabad"
r = requests.post(f"{BASE}/api/chain", json={"goal": goal}, timeout=30)
resp = r.json()
print("POST /api/chain:", resp)
chain_id = resp.get("chain_id")

if not chain_id:
    print("No chain_id returned — aborting")
    exit(1)

# 2. Poll until done (max 30s)
for i in range(15):
    time.sleep(2)
    r2 = requests.get(f"{BASE}/api/chain/{chain_id}", timeout=10)
    chain = r2.json().get("chain", {})
    status = chain.get("status", "?")
    steps = chain.get("steps", [])
    print(f"\n[Poll {i+1}] Chain status: {status.upper()}")
    for s in steps:
        st = s.get("status", "?").upper()
        tool = s.get("tool", "")
        desc = s.get("description", "")
        result = (s.get("result") or "")[:80]
        error  = (s.get("error")  or "")[:80]
        print(f"  [{st}] {tool} — {desc}")
        if result: print(f"    => {result}")
        if error:  print(f"    !! {error}")
    if status in ("done", "failed", "cancelled"):
        print("\nChain finished.")
        break
