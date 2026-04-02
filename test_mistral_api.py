import os
import requests

# Get API key from environment
MISTRAL_API_KEY = os.getenv('MISTRAL_API_KEY')

print(f"MISTRAL_API_KEY exists: {bool(MISTRAL_API_KEY)}")

if MISTRAL_API_KEY:
    print(f"API Key starts with: {MISTRAL_API_KEY[:10]}...")
    
    # Test API connection
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # List available models
    response = requests.get("https://api.mistral.ai/v1/models", headers=headers)
    print(f"Models API status: {response.status_code}")
    
    if response.status_code == 200:
        models = response.json()
        print(f"✅ Mistral API is working!")
        print(f"Available models: {[m['id'] for m in models.get('data', [])[:3]]}")
    else:
        print(f"❌ Error: {response.text}")
else:
    print("❌ MISTRAL_API_KEY not found in environment")
