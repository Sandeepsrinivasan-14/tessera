import requests
import json

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

    # 4. Simulation: Define the Route Parameter
    # For testing, we are requesting ID 201.
    route_param_id = "201" 

    # --- REQUIREMENT: ID MUST BE VALIDATED & SERVER MUST NOT CRASH ---
    try:
        # Attempt to convert the input to an integer
        target_id = int(route_param_id)
        
        # --- REQUIREMENT: FIND PATIENT ---
        # Search the list for the matching ID
        found_patient = None
        for p in patient_list:
            if p.get('id') == target_id:
                found_patient = p
                break

        # --- REQUIREMENT: IF NOT FOUND RETURN 404 ---
        if found_patient:
            print(f"\n--- SUCCESS: GET /patients/{target_id} ---")
            print(json.dumps(found_patient, indent=4))
        else:
            error_404 = {"message": "patient not found"}
            print(f"\n--- ERROR 404: GET /patients/{target_id} ---")
            print(json.dumps(error_404, indent=4))

    except (ValueError, TypeError):
        # This prevents the server from crashing if route_param_id is "abc"
        error_invalid = {"message": "Invalid ID format. ID must be a number."}
        print("\n--- ERROR: INVALID INPUT ---")
        print(json.dumps(error_invalid, indent=4))

else:
    print(f"Auth Failed: {token_res.text}")