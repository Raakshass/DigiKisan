"""KisanMitra AI — Live Endpoint Test"""
import httpx
import json

base = "http://localhost:8000/api"

# 1. Health
print("=== HEALTH CHECK ===")
r = httpx.get(f"{base}/health", timeout=10)
print(f"Status: {r.status_code} | {r.json()}")

# 2. Start session
print("\n=== START SESSION ===")
r = httpx.post(f"{base}/chat/start-session", json={}, timeout=10)
data = r.json()
sid = data.get("session_id", "test-fallback")
print(f"OK: {data.get('ok')} | Session: {sid[:12]}...")

# 3. Chat WITH location (UP/Lucknow)
print("\n=== CHAT: Location = UP, Lucknow ===")
r = httpx.post(f"{base}/chat/message", json={
    "message": "What crops should I plant this kharif season?",
    "session_id": sid,
    "location": {"state": "UP", "district": "Lucknow"},
    "language": "en",
}, timeout=30)
result = r.json()
print(f"OK: {result.get('ok')}")
print(f"Completed: {result.get('completed')}")
# Response is in 'message' key per _chat_response()
msg = result.get("message", "")
print(f"Message ({len(msg)} chars): {msg[:400]}")
print(f"All keys: {list(result.keys())}")

# 4. Chat WITHOUT location (backward compat)
print("\n=== CHAT: No location (backward compat) ===")
r = httpx.post(f"{base}/chat/message", json={
    "message": "Tell me about PM-Kisan yojana",
    "session_id": sid,
}, timeout=30)
result = r.json()
print(f"OK: {result.get('ok')}")
msg = result.get("message", "")
print(f"Message ({len(msg)} chars): {msg[:400]}")

print("\n=== ALL ENDPOINTS RESPONDING ===")
