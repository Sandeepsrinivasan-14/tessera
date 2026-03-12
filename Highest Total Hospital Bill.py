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
    
    # Construct official authorized Data URL
    data_url = f"https://t4e-testserver.onrender.com/api{data_path}"
    print(f"Step 2: Fetching dataset from {data_url}...")
    
    # 3. Step 2: Access the Dataset
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(data_url, headers=headers)
    full_response = response.json()

    # 4. Navigate the Nested Structure: ['data']['patients']
    # Based on your previous output, the list is inside 'data' -> 'patients'
    patient_list = full_response.get('data', {}).get('patients', [])

    if patient_list:
        processed_data = []
        
        for p in patient_list:
            # Navigate nested bill dictionary
            bill = p.get('bill', {})
            
            # Dynamic Calculation: consultation + medicine + lab
            total = (bill.get('consultation', 0) + 
                     bill.get('medicine', 0) + 
                     bill.get('lab', 0))
            
            # Create response object (Requirement: do not modify original)
            processed_data.append({
                "id": p.get('id'),
                "name": p.get('name'),
                "department": p.get('department'),
                "totalBill": total
            })

        # 5. Sorting (Requirement: Use sorting to find the highest)
        processed_data.sort(key=lambda x: x['totalBill'], reverse=True)

        # 6. Final Result
        if processed_data:
            highest_patient = processed_data[0]
            print("\n--- GET /patients/highest-bill ---")
            print(json.dumps(highest_patient, indent=4))
    else:
        print("Error: Could not find patient list in the response.")
        print(f"Server Response: {full_response}")

else:
    print(f"Auth Failed: {token_res.text}")