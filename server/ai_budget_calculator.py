import os
import csv
from datetime import date
from pymongo import MongoClient

def calculate_limits():
    # 1. Connect to Database
    client = MongoClient("mongodb://localhost:27017/")
    db = client["energy_optimizer"]
    
    # 2. Get the current simulated month (e.g., October)
    # For demo purposes, we look for October 2025 in the dataset to predict October 2026 budget
    current_month_name = date.today().strftime("%B")
    target_year_in_dataset = "2025" # Previous year
    
    csv_path = os.path.join(os.path.dirname(__file__), "ml", "dataset", "monthly_units_consumed.csv")
    
    monthly_budget = 700 # Default fallback
    try:
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['year'] == target_year_in_dataset and row['month'] == current_month_name:
                    monthly_budget = float(row['units_consumed'])
                    break
    except Exception as e:
        print(f"[Warning] Could not read CSV perfectly, using default {monthly_budget} kWh: {e}")

    # 3. Calculate Daily Budget
    # Assume 30 days for simplicity
    daily_house_budget = monthly_budget / 30.0
    print(f"\n--- AI BUDGET CALCULATOR ---")
    print(f"Targeting previous year: {current_month_name} {target_year_in_dataset}")
    print(f"Monthly Target: {monthly_budget:.2f} kWh")
    print(f"Daily House Budget: {daily_house_budget:.2f} kWh")

    # 4. Fetch all appliances
    apps = list(db.appliances.find())
    
    # 5. Calculate Essential Reserve
    essential_kwh_needed = 0
    for app in apps:
        if app.get("priority") == "Essential":
            # Assume 24 hours running time for essentials
            essential_kwh_needed += (app["power"] / 1000.0) * 24.0
            
    print(f"Reserved for Essentials: {essential_kwh_needed:.2f} kWh")
    
    # 6. Calculate Remaining Budget
    remaining_budget = daily_house_budget - essential_kwh_needed
    
    # 7. Calculate total shares for Medium and Non-essential
    total_shares = 0
    non_essentials = []
    
    for app in apps:
        priority = app.get("priority", "Non-essential")
        if priority == "Essential":
            # Essentials do not get a daily limit! They run infinitely.
            db.appliances.update_one({"_id": app["_id"]}, {"$unset": {"dailyLimitKwh": ""}})
            continue
            
        multiplier = 2 if priority == "Medium" else 1
        shares = app["power"] * multiplier
        total_shares += shares
        non_essentials.append({
            "doc": app,
            "shares": shares,
            "priority": priority
        })

    print(f"Budget remaining for others: {remaining_budget:.2f} kWh")
    
    # 8. Distribute and Save Limits
    for item in non_essentials:
        app_doc = item["doc"]
        shares = item["shares"]
        
        # Calculate limit based on mathematical share
        if total_shares > 0 and remaining_budget > 0:
            limit = (shares / total_shares) * remaining_budget
        else:
            limit = 0.0
            
        # Enforce Minimum Grace Allowance (1.0 kWh)
        if limit < 1.0:
            limit = 1.0
            
        # Save to database
        db.appliances.update_one(
            {"_id": app_doc["_id"]},
            {"$set": {"dailyLimitKwh": round(limit, 2)}}
        )
        print(f"-> Assigned {round(limit, 2)} kWh to '{app_doc['name']}' ({item['priority']})")
        
    print("---------------------------------")
    print("Successfully balanced budget and assigned dynamic AI limits!")

if __name__ == "__main__":
    calculate_limits()
