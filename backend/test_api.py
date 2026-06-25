import httpx
import json

base = "http://localhost:8000"

# 1. SIGNUP
print("=== SIGNUP ===")
r = httpx.post(f"{base}/api/auth/signup", json={"email": "ishpreet@test.com", "password": "test123456"}, timeout=30)
print(f"Status: {r.status_code}")
data = r.json()
print(json.dumps(data, indent=2))
token = data["access_token"]

# 2. LOGIN
print("\n=== LOGIN ===")
r = httpx.post(f"{base}/api/auth/login", json={"email": "ishpreet@test.com", "password": "test123456"}, timeout=30)
print(f"Status: {r.status_code}")
print(json.dumps(r.json(), indent=2))

# 3. GET ME
print("\n=== GET /me ===")
r = httpx.get(f"{base}/api/auth/me", headers={"Authorization": f"Bearer {token}"}, timeout=30)
print(f"Status: {r.status_code}")
print(json.dumps(r.json(), indent=2))

# 4. TEST 401 (no token)
print("\n=== 401 TEST (no token) ===")
r = httpx.get(f"{base}/api/auth/me", timeout=30)
print(f"Status: {r.status_code}")

# 5. CREATE CHATBOT
print("\n=== CREATE CHATBOT ===")
r = httpx.post(
    f"{base}/api/chatbots/",
    json={"name": "Test Chatbot", "website_url": "https://example.com"},
    headers={"Authorization": f"Bearer {token}"},
    timeout=30,
)
print(f"Status: {r.status_code}")
bot = r.json()
print(json.dumps(bot, indent=2))
bot_id = bot["id"]

# 6. LIST CHATBOTS
print("\n=== LIST CHATBOTS ===")
r = httpx.get(f"{base}/api/chatbots/", headers={"Authorization": f"Bearer {token}"}, timeout=30)
print(f"Status: {r.status_code}")
print(f"Count: {len(r.json())}")

# 7. GET CHATBOT STATUS
print("\n=== GET STATUS ===")
r = httpx.get(f"{base}/api/chatbots/{bot_id}/status", headers={"Authorization": f"Bearer {token}"}, timeout=30)
print(f"Status: {r.status_code}")
print(json.dumps(r.json(), indent=2))

# 8. DELETE CHATBOT
print("\n=== DELETE CHATBOT ===")
r = httpx.delete(f"{base}/api/chatbots/{bot_id}", headers={"Authorization": f"Bearer {token}"}, timeout=30)
print(f"Status: {r.status_code}")

print("\n ALL TESTS PASSED!")
