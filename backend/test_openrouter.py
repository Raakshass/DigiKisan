"""Verify OpenRouter API key from .env is working."""
import os, httpx, json

# Parse .env
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
api_key = ""
model = "google/gemma-4-31b-it:free"
with open(env_path) as f:
    for line in f:
        line = line.strip()
        if line.startswith("OPENROUTER_API_KEY="):
            api_key = line.split("=", 1)[1].strip()
        if line.startswith("OPENROUTER_MODEL="):
            model = line.split("=", 1)[1].strip()

if not api_key:
    print("FAIL: OPENROUTER_API_KEY not found in .env")
    exit(1)

print(f"Key found: {api_key[:12]}...{api_key[-4:]}")
print(f"Model: {model}")
print()

# Test API
print("Sending test request to OpenRouter...")
try:
    resp = httpx.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://kisanmitra.ai",
            "X-Title": "KisanMitra AI",
        },
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": "You are an agricultural advisor. Reply in 1 sentence."},
                {"role": "user", "content": "What is the best kharif crop for UP?"},
            ],
            "max_tokens": 100,
            "temperature": 0.3,
        },
        timeout=25.0,
    )
    print(f"HTTP Status: {resp.status_code}")
    
    if resp.status_code == 200:
        data = resp.json()
        reply = data["choices"][0]["message"]["content"]
        model_used = data.get("model", "unknown")
        print(f"Model used: {model_used}")
        print(f"Response: {reply}")
        print()
        print("RESULT: OPENROUTER API KEY IS VALID AND WORKING")
    else:
        print(f"Error body: {resp.text[:500]}")
        print()
        print("RESULT: API KEY FAILED - check the error above")
        exit(1)
except Exception as e:
    print(f"Error: {e}")
    print("RESULT: CONNECTION FAILED")
    exit(1)
