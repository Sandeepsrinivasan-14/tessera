import requests

# Exact URL from your email instructions
BASE_URL = "https://t4e-demotestserver.onrender.com"
TOKEN_URL = f"{BASE_URL}/public/token"
MY_ID = "REDACTED"

payload = {
    "studentId": MY_ID,
    "set": "setA"
}

print(f"Connecting to: {TOKEN_URL}...")

try:
    # STEP 1: Get Token
    response = requests.post(TOKEN_URL, json=payload)
    res_data = response.json()
    
    print("\n--- SERVER RESPONSE ---")
    print(res_data) # This tells us what the server actually sent
    print("-----------------------\n")

    # STEP 2: Extract Token and Endpoint
    # We use .get() to avoid the 'NoneType' crash
    token = res_data.get("token") or res_data.get("accessToken")
    endpoint = res_data.get("endpoint") or res_data.get("path")

    if token:
        # If endpoint is relative (like "/dataset"), add the Base URL
        if endpoint and not endpoint.startswith("http"):
            endpoint = f"https://t4e-demotestserver.onrender.com{endpoint}"
        elif not endpoint:
            # Fallback if endpoint is missing from response
            endpoint = f"{BASE_URL}/patient/all" 

        print(f"✔ Using Token: {token[:8]}...")
        print(f"✔ Fetching from: {endpoint}")

        # STEP 3: Get Data
        headers = {"Authorization": f"Bearer {token}"}
        data_res = requests.get(endpoint, headers=headers)
        
        if data_res.status_code == 200:
            dataset = data_res.json()
            print("\n--- DATA RECEIVED ---")
            print(dataset[:2]) # Print first two items to check format
        else:
            print(f"❌ Data Fetch Error {data_res.status_code}: {data_res.text}")
    else:
        print("❌ No token found. Check 'SERVER RESPONSE' above.")

except Exception as e:
    print(f"Critical Error: {e}")
