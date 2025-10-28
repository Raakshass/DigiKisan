import requests
import json

BASE_URL = "http://localhost:8000/api"

def test_all_endpoints():
    """Test all DigiKisan backend endpoints"""
    
    print("🧪 Testing DigiKisan Backend API\n" + "="*50)
    
    # 1. Health check
    print("1️⃣ Testing Health Check...")
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Error: {e}")
    print()
    
    # 2. Text classification
    print("2️⃣ Testing Text Classification...")
    try:
        response = requests.post(
            f"{BASE_URL}/classify",
            headers={"Content-Type": "application/json"},
            json={"text": "rice price in agra today"}
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Error: {e}")
    print()
    
    # 3. Multi-turn chat with slot filling
    print("3️⃣ Testing Multi-turn Chat (Slot Filling)...")
    
    # First message
    print("   🗣️ User: 'rice price'")
    try:
        response = requests.post(
            f"{BASE_URL}/chat/slots",
            headers={"Content-Type": "application/json"},
            json={
                "message": "rice price",
                "session_state": {}
            }
        )
        print(f"   🤖 Bot: {response.json().get('response', 'No response')}")
        session_state = response.json().get('session_state', {})
        print(f"   📋 Session: {session_state}")
    except Exception as e:
        print(f"   Error: {e}")
    print()
    
    # Follow-up message (if you want to continue the conversation)
    print("   🗣️ User: 'agra'")
    try:
        response = requests.post(
            f"{BASE_URL}/chat/slots",
            headers={"Content-Type": "application/json"},
            json={
                "message": "agra", 
                "session_state": session_state  # Use session from previous response
            }
        )
        print(f"   🤖 Bot: {response.json().get('response', 'No response')}")
        session_state = response.json().get('session_state', {})
        print(f"   📋 Session: {session_state}")
    except Exception as e:
        print(f"   Error: {e}")
    print()
    
    # Final message (complete the conversation)
    print("   🗣️ User: 'today'")
    try:
        response = requests.post(
            f"{BASE_URL}/chat/slots",
            headers={"Content-Type": "application/json"},
            json={
                "message": "today",
                "session_state": session_state
            }
        )
        print(f"   🤖 Bot: {response.json().get('response', 'No response')}")
        if response.json().get('completed'):
            print(f"   ✅ Slots filled: {response.json().get('slots', {})}")
    except Exception as e:
        print(f"   Error: {e}")
    print()
    
    # 4. Image classification (uncomment when you have an image)
    print("4️⃣ Testing Image Disease Prediction...")
    print("   📝 Uncomment and modify the path below to test:")
    print("""
    # Example usage:
    # with open("path/to/crop_image.jpg", "rb") as f:
    #     response = requests.post(
    #         f"{BASE_URL}/disease/predict",
    #         files={"file": ("image.jpg", f, "image/jpeg")}
    #     )
    #     print(f"Disease prediction: {response.json()}")
    """)
    
    # 5. API Info
    print("5️⃣ Getting API Info...")
    try:
        response = requests.get(f"{BASE_URL}/info")
        print(f"Status: {response.status_code}")
        print(f"Available endpoints: {list(response.json().get('endpoints', {}).keys())}")
    except Exception as e:
        print(f"Error: {e}")
    print()

if __name__ == "__main__":
    test_all_endpoints()
