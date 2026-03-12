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

    # 4. Simulation: Define the Query Parameter
    # For testing, we are using 'cardiology'. 
    # In a real server, this would come from request.args.get('department')
    query_param_dept = "cardiology" 

    # --- REQUIREMENT: IF QUERY PARAMETER MISSING RETURN 400 ---
    if not query_param_dept:
        error_response = {"message": "department query parameter is required"}
        print("\n--- ERROR 400 ---")
        print(json.dumps(error_response, indent=4))
    else:
        # --- REQUIREMENT: CASE-INSENSITIVE COMPARISON ---
        filtered_patients = []
        target_dept = query_param_dept.strip().lower()

        for p in patient_list:
            current_dept = p.get('department', '').strip().lower()
            
            if current_dept == target_dept:
                # --- REQUIREMENT: RETURN ONLY MATCHING PATIENTS WITH SPECIFIC FIELDS ---
                filtered_patients.append({
                    "id": p.get('id'),
                    "name": p.get('name'),
                    "department": p.get('department'),
                    "doctor": p.get('doctor')
                })

        print(f"\n--- GET /patients/filter?department={query_param_dept} ---")
        print(json.dumps(filtered_patients, indent=4))

else:
    print(f"Auth Failed: {token_res.text}")