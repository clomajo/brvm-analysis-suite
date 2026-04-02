import os
import requests

MISTRAL_API_KEY = os.getenv('MISTRAL_API_KEY')
print(f"MISTRAL_API_KEY exists: {bool(MISTRAL_API_KEY)}")

if MISTRAL_API_KEY:
    # Test a simple API call
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }
    response = requests.get("https://api.mistral.ai/v1/models", headers=headers)
    print(f"API test status: {response.status_code}")
    if response.status_code == 200:
        print("✅ Mistral API is working!")
    else:
        print(f"❌ Mistral API error: {response.text}")
