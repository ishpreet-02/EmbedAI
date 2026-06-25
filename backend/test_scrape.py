"""
Test the full scraping flow:
1. Login with existing user
2. Create a chatbot with a real website URL
3. Poll status until it changes from 'pending' → 'processing' → 'ready'
"""

import httpx
import json
import time

base = "http://localhost:8000"

# 1. Login
print("=== LOGIN ===")
r = httpx.post(f"{base}/api/auth/login", json={
    "email": "ishpreet@test.com",
    "password": "test123456"
}, timeout=30)

if r.status_code != 200:
    print("Login failed! Creating new user...")
    r = httpx.post(f"{base}/api/auth/signup", json={
        "email": "ishpreet@test.com",
        "password": "test123456"
    }, timeout=30)

data = r.json()
token = data["access_token"]
headers = {"Authorization": f"Bearer {token}"}
print(f"Logged in as: {data['user']['email']}")

# 2. Create chatbot with a real website
print("\n=== CREATE CHATBOT (scraping https://books.toscrape.com) ===")
r = httpx.post(f"{base}/api/chatbots/", json={
    "name": "Books Store Bot",
    "website_url": "https://books.toscrape.com"
}, headers=headers, timeout=30)
print(f"Status: {r.status_code}")
bot = r.json()
print(json.dumps(bot, indent=2))
bot_id = bot["id"]

# 3. Poll status every 3 seconds
print("\n=== POLLING STATUS (scraping in background...) ===")
for i in range(60):  # max 180 seconds
    time.sleep(3)
    r = httpx.get(f"{base}/api/chatbots/{bot_id}/status", headers=headers, timeout=30)
    status_data = r.json()
    current_status = status_data["status"]
    pages = status_data.get("pages_indexed") or 0
    print(f"  [{i*3}s] Status: {current_status} | Pages indexed: {pages}")

    if current_status in ("ready", "failed"):
        break

# 4. Final result
print("\n=== FINAL RESULT ===")
r = httpx.get(f"{base}/api/chatbots/{bot_id}", headers=headers, timeout=30)
print(json.dumps(r.json(), indent=2))

if status_data["status"] == "ready":
    print("\n SCRAPING COMPLETE!")
else:
    print(f"\n Scraping ended with status: {status_data['status']}")
