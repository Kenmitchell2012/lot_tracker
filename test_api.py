# test_api.py

import requests
import json

# --- Configuration ---
API_TOKEN = "eyJhbGciOiJIUzI1NiJ9.eyJ0aWQiOjQ4MjkwODg4OSwiYWFpIjoxMSwidWlkIjo0NTM0MDAzMiwiaWFkIjoiMjAyNS0wMy0wOVQxODozNjoyNC4wMDBaIiwicGVyIjoibWU6d3JpdGUiLCJhY3RpZCI6MTU0ODA4NzIsInJnbiI6InVzZTEifQ.gxtLagJmw5gcZ9r43N1N7yIerEpu0zPNP1jF6VTX31g"
API_URL = "https://api.monday.com/v2"

# --- Headers for Authentication ---
headers = {
    "Authorization": API_TOKEN,
    "Content-Type": "application/json",
}

# --- A simple GraphQL query to get the names of your boards ---
query = '{ boards { id name } }'
data = {'query': query}

# --- Make the API Request ---
print("Querying Monday.com API...")
try:
    response = requests.post(API_URL, headers=headers, json=data)
    response.raise_for_status() # Raises an error for bad responses (4xx or 5xx)

    # --- Print the results ---
    print("\nSuccess! API Response:")
    pretty_response = json.dumps(response.json(), indent=2)
    print(pretty_response)

except requests.exceptions.HTTPError as err:
    print(f"\nHTTP Error: {err}")
    print(f"Response Body: {response.text}")
except Exception as e:
    print(f"\nAn unexpected error occurred: {e}")