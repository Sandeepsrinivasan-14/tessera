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
        
        # 1. Count Admitted Patients
        admitted_count = reduce(
            lambda count, p: count + 1 if p.get('status') == 'Admitted' else count, 
            patient_list, 
            0
        )

        # 2. Count Discharged Patients
        discharged_count = reduce(
            lambda count, p: count + 1 if p.get('status') == 'Discharged' else count, 
            patient_list, 
            0
        )

        # 3. Sum total age for average calculation
        total_age = reduce(
            lambda total, p: total + p.get('age', 0), 
            patient_list, 
            0
        )

        # Calculate Average Age (Rounded to 2 decimal places as per requirement)
        average_age = round(total_age / len(patient_list), 2)

        # 4. Build Final Structured JSON Response
        summary_response = {
            "admittedCount": admitted_count,
            "dischargedCount": discharged_count,
            "averageAge": average_age
        }

        print("\n--- GET /patient/admission/summary ---")
        print(json.dumps(summary_response, indent=4))
    else:
        print("Error: Patient list is empty.")
else:
    print(f"Auth Failed: {token_res.text}")