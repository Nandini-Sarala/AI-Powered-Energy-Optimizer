import requests
import time
import json
import sys
import threading
from datetime import datetime

# Change this to match the JWT token of a logged-in user if you added authentication
BASE_URL = "http://localhost:5000/api"
TOKEN = ""

# --- SCENARIO VARIABLES ---
WIFI_CONNECTED = True
OFFLINE_EVENTS = {}  # Store offline timestamps
LOCAL_APPS = []      # Cache of apps when offline

def login():
    global TOKEN
    print("Logging into simulator...")
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
    if not WIFI_CONNECTED:
        return LOCAL_APPS
    headers = {"Authorization": f"Bearer {TOKEN}"}
    try:
        res = requests.get(f"{BASE_URL}/appliances", headers=headers)
        return res.json()
    except Exception as e:
        print(f"Network error: {e}")
        return []

def toggle_physical_switch(idx):
    global LOCAL_APPS
    app = LOCAL_APPS[idx]
    app_id = app["_id"]
    
    print(f"\n[Hardware] Flipping physical switch for appliance {app_id}...")
    
    # ── SCENARIO B: OFFLINE CACHING ──
    if not WIFI_CONNECTED:
        new_state = not app.get("status", False)
        app["status"] = new_state
        print(f"[Hardware] Wi-Fi is DOWN. Physically turned {'ON' if new_state else 'OFF'}.")
        print(f"[Hardware] Event cached. Will sync when Wi-Fi returns.")
        OFFLINE_EVENTS[app_id] = {
            "toggle_time": datetime.now().isoformat(),
            "final_state": new_state
        }
        return

    # ── NORMAL OPERATION ──
    headers = {"Authorization": f"Bearer {TOKEN}"}
    res = requests.post(f"{BASE_URL}/appliances/{app_id}/physical-toggle", headers=headers)
    
    if res.status_code == 200:
        data = res.json()
        print(f"[Hardware] Success! Appliance '{data['name']}' is now {'ON' if data['status'] else 'OFF'}.")
    elif res.status_code == 403:
        print(f"[Hardware] REJECTED BY AI: {res.json().get('message')}")
    else:
        print(f"[Hardware] Error: {res.text}")

# ── SCENARIO A: HEARTBEAT THREAD ──
def heartbeat_loop():
    global LOCAL_APPS
    while True:
        if WIFI_CONNECTED and TOKEN:
            # 1. Fetch fresh state from server so terminal stays in sync with Dashboard!
            try:
                fresh_apps = get_appliances()
                if fresh_apps:
                    LOCAL_APPS = fresh_apps
            except:
                pass
                
            # 2. Send Heartbeats
            if LOCAL_APPS:
                headers = {"Authorization": f"Bearer {TOKEN}"}
                for app in LOCAL_APPS:
                    try:
                        requests.post(f"{BASE_URL}/appliances/{app['_id']}/heartbeat", headers=headers)
                    except:
                        pass
        time.sleep(10)

def main():
    global WIFI_CONNECTED, LOCAL_APPS, OFFLINE_EVENTS
    print("=========================================")
    print(" PHYSICAL SWITCH SIMULATOR (ESP32 MOCK)  ")
    print("=========================================")
    login()
    LOCAL_APPS = get_appliances()
    
    # Start heartbeat in background
    t = threading.Thread(target=heartbeat_loop, daemon=True)
    t.start()
    
    while True:
        if WIFI_CONNECTED:
            LOCAL_APPS = get_appliances()
            
        if not LOCAL_APPS:
            print("No appliances found in your account.")
            time.sleep(5)
            continue
            
        print("\n--- Your Wall Switches ---")
        for i, app in enumerate(LOCAL_APPS):
            state = "ON" if app.get("status") else "OFF"
            locked = " (LOCKED BY AI BUDGET)" if app.get("lockedBySystem") else ""
            print(f"[{i}] {app['name']} - ID: {app['_id']} (Currently {state}){locked}")
            
        print("\n--- Network Controls ---")
        if WIFI_CONNECTED:
            print("[d] Drop Wi-Fi (Simulate Disconnect)")
        else:
            print("[c] Reconnect Wi-Fi (Simulate Reconnect & Sync)")
        print("[q] Quit")
        
        choice = input("\nEnter choice (number or letter): ")
        if choice.lower() == 'q':
            break
        elif choice.lower() == 'd' and WIFI_CONNECTED:
            print("\n🚨 WI-FI DROPPED! The hardware is now offline. Server is blind.")
            WIFI_CONNECTED = False
            continue
        elif choice.lower() == 'c' and not WIFI_CONNECTED:
            print("\n🌐 WI-FI RESTORED! Syncing cached events to server...")
            WIFI_CONNECTED = True
            headers = {"Authorization": f"Bearer {TOKEN}"}
            for app_id, data in OFFLINE_EVENTS.items():
                print(f"[Hardware] Syncing app {app_id}...")
                requests.post(f"{BASE_URL}/appliances/{app_id}/offline-sync", json={
                    "toggleTime": data["toggle_time"],
                    "finalState": data["final_state"]
                }, headers=headers)
            OFFLINE_EVENTS.clear()
            print("[Hardware] Sync complete.")
            continue
            
        try:
            idx = int(choice)
            if 0 <= idx < len(LOCAL_APPS):
                toggle_physical_switch(idx)
            else:
                print("Invalid number.")
        except ValueError:
            pass
            
if __name__ == "__main__":
    main()
