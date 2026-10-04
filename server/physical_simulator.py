import requests
import time
import json
import sys

# Change this to match the JWT token of a logged-in user if you added authentication
# For this simulator, you need to grab the JWT token from the browser console (localStorage.getItem('token'))
# and paste it here, OR we can write a quick login wrapper.
BASE_URL = "http://localhost:5000/api"
TOKEN = ""

def login():
    global TOKEN
    print("Logging into simulator...")
    # Using the default user or ask for credentials
    res = requests.post(f"{BASE_URL}/auth/login", json={
        "email": "test@gmail.com",
        "password": "testing"
    })
    if res.status_code == 200:
        TOKEN = res.json().get("token")
        print("Login successful! Token acquired.")
    else:
        print("Login failed! Please make sure test@example.com exists or change the credentials in the script.")
        print(res.json())
        sys.exit(1)

def get_appliances():
    headers = {"Authorization": f"Bearer {TOKEN}"}
    res = requests.get(f"{BASE_URL}/appliances", headers=headers)
    return res.json()

def toggle_physical_switch(app_id):
    print(f"\n[Hardware] Flipping physical switch for appliance {app_id}...")
    headers = {"Authorization": f"Bearer {TOKEN}"}
    res = requests.post(f"{BASE_URL}/appliances/{app_id}/physical-toggle", headers=headers)
    
    if res.status_code == 200:
        data = res.json()
        print(f"[Hardware] Success! Appliance '{data['name']}' is now {'ON' if data['status'] else 'OFF'}.")
    elif res.status_code == 403:
        print(f"[Hardware] REJECTED BY AI: {res.json().get('message')}")
        print("[Hardware] The wall switch failed to turn on the appliance. Check the virtual dashboard for warnings.")
    else:
        print(f"[Hardware] Error: {res.text}")

def main():
    print("=========================================")
    print(" PHYSICAL SWITCH SIMULATOR (ESP32 MOCK)  ")
    print("=========================================")
    login()
    
    while True:
        print("\nFetching your appliances...")
        apps = get_appliances()
        if not apps:
            print("No appliances found in your account.")
            break
            
        print("--- Your Wall Switches ---")
        for i, app in enumerate(apps):
            state = "ON" if app.get("status") else "OFF"
            locked = " (LOCKED BY GRID)" if app.get("lockedBySystem") else ""
            print(f"[{i}] {app['name']} - ID: {app['_id']} (Currently {state}){locked}")
            
        print("[q] Quit")
        
        choice = input("\nWhich physical switch do you want to flip? (Enter number): ")
        if choice.lower() == 'q':
            break
            
        try:
            idx = int(choice)
            if 0 <= idx < len(apps):
                toggle_physical_switch(apps[idx]["_id"])
            else:
                print("Invalid number.")
        except ValueError:
            print("Please enter a valid number.")
            
if __name__ == "__main__":
    main()
