# find_columns.py

import requests
import json

# --- Configuration ---
API_TOKEN = "eyJhbGciOiJIUzI1NiJ9.eyJ0aWQiOjQ4MjkwODg4OSwiYWFpIjoxMSwidWlkIjo0NTM0MDAzMiwiaWFkIjoiMjAyNS0wMy0wOVQxODozNjoyNC4wMDBaIiwicGVyIjoibWU6d3JpdGUiLCJhY3RpZCI6MTU0ODA4NzIsInJnbiI6InVzZTEifQ.gxtLagJmw5gcZ9r43N1N7yIerEpu0zPNP1jF6VTX31g" # <--- PASTE YOUR TOKEN HERE
API_URL = "https://api.monday.com/v2"
BOARD_ID = 8120988708 # The ID for the "2025 Lot Tracker" board
# BOARD_ID = 9440164519 # The ID for the "July 2025 Chart/Labeling Tracking" board
# ---------------------

headers = {"Authorization": API_TOKEN}

# GraphQL query to get all columns for a specific board
query = f'''
    query {{
        boards(ids: {BOARD_ID}) {{
            columns {{
                id
                title
                type
            }}
        }}
    }}
'''
data = {'query': query}

print(f"Finding columns for board {BOARD_ID}...")
try:
    response = requests.post(API_URL, headers=headers, json=data)
    response.raise_for_status()
    results = response.json()
    
    columns = results['data']['boards'][0]['columns']

    print("\n--- Columns Found ---")
    for column in columns:
        print(f"- Title: '{column['title']}', ID: '{column['id']}'")
    print("---------------------")

except Exception as e:
    print(f"\nAn error occurred: {e}")