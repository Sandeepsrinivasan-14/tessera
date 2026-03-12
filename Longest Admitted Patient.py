import requests
import json
from functools import reduce

# 1. Official Configuration
BASE_URL = "https://t4e-testserver.onrender.com/api"
TOKEN_URL = f"{BASE_URL}/public/token"

MY_ID = "REDACTED"
MY_SET = "setA"
MY_PASSWORD = "REDACTED"

# 2. Step 1: Generate Token
auth_payload = {
    "studentId": MY_ID,
    "set": MY_SET,
    "password": MY_PASSWORD
}

print(f"Step 1: Authenticating for {MY_ID}...")
token_res = requests.post(TOKEN_URL, json=auth_payload)

if token_res.status_code in [200, 201]:
    res_data = token_res.json()
    token = res_data.get("token")
    data_path = res_data.get("dataUrl") 
    
    data_url = f"https://t4e-testserver.onrender.com/api{data_path}"
    print(f"Step 2: Fetching dataset from {data_url}...")
    
    # 3. Step 2: Access the Dataset
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(data_url, headers=headers)
    full_response = response.json()
    patient_list = full_response.get('data', {}).get('patients', [])

    if patient_list:
        # --- REQUIREMENT: MUST USE REDUCE ---
        # We compare two patients at a time and return the one with the larger 'daysAdmitted'
        longest_stay_record = reduce(
            lambda a, b: a if a.get('daysAdmitted', 0) > b.get('daysAdmitted', 0) else b, 
            patient_list
        )

        # --- REQUIREMENT: DO NOT MODIFY ORIGINAL DATASET ---
        # Create a new dictionary for the response containing only requested fields
        response_data = {
            "id": longest_stay_record.get('id'),
            "name": longest_stay_record.get('name'),
            "department": longest_stay_record.get('department'),
            "daysAdmitted": longest_stay_record.get('daysAdmitted')
        }

        print("\n--- GET /patient/longest-stay ---")
        print(json.dumps(response_data, indent=4))
    else:
        print("Error: Patient list is empty.")
else:
    print(f"Auth Failed: {token_res.text}")