"""
Energy Routes — Flask Blueprint
  GET   /api/energy/weather          → Real-time weather from OpenWeatherMap
  GET   /api/energy/logs             → Last 7 days energy logs
  POST  /api/energy/logs             → Add/update today's log
  GET   /api/energy/dashboard        → Aggregated dashboard stats
  POST  /api/energy/recommendations  → Run ML predictions (native Python)
"""

import os
import sys
import joblib
import pandas as pd
import requests as http_requests
from datetime import datetime, date, timedelta
from flask import Blueprint, request, jsonify, current_app, g
from bson import ObjectId
from routes.middleware import protect

energy_bp = Blueprint("energy", __name__)

# ── Load ML models once at startup ─────────────────────────────────────────────
_script_dir  = os.path.dirname(os.path.abspath(__file__))
_models_dir  = os.path.join(_script_dir, "..", "ml", "models")

try:
    _rf_model       = joblib.load(os.path.join(_models_dir, "random_forest_model.pkl"))
    _feature_cols   = joblib.load(os.path.join(_models_dir, "model_feature_columns.pkl"))
    print("[OK] ML models loaded successfully")
except Exception as e:
    _rf_model = None
    _feature_cols = None
    print(f"[WARN] ML models could not be loaded: {e}")

# ── Name mapping: frontend names → dataset names ───────────────────────────────
_NAME_MAP = {
    "wifi router":    "WiFi",
    "wifi":           "WiFi",
    "iron box":       "Iron Box",
    "washing machine":"Washing Machine",
    "water purifier": "Water Purifier",
    "room heater":    "Room Heater",
    "ac":             "AC",
    "fridge":         "Fridge",
    "geyser":         "Geyser",
    "cooler":         "Cooler",
    "mixer":          "Mixer",
    "lights":         "Lights",
    "tv":             "TV",
    "fans":           "Fans",
    "oven":           "Oven",
}


def _serialize(doc):
    doc["_id"] = str(doc["_id"])
    if "userId" in doc:
        doc["userId"] = str(doc["userId"])
    return doc


# ── GET /api/energy/weather ────────────────────────────────────────────────────
@energy_bp.route("/weather", methods=["GET"])
@protect
def get_weather():
    city    = g.user.get("city", "Bangalore")
    api_key = os.getenv("OPENWEATHER_API_KEY", "")

    try:
        lat, lon, geo_name = None, None, city

        # Step 1: Geocode city name → exact lat/lon for accuracy
        geo_resp = http_requests.get(
            "http://api.openweathermap.org/geo/1.0/direct",
            params={"q": city, "limit": 1, "appid": api_key},
            timeout=8
        )
        if geo_resp.ok:
            geo_data = geo_resp.json()
            if geo_data:
                lat      = geo_data[0]["lat"]
                lon      = geo_data[0]["lon"]
                geo_name = geo_data[0].get("name", city)

        # Step 2: Fetch weather by coordinates (or fall back to city name)
        if lat is not None and lon is not None:
            resp = http_requests.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={"lat": lat, "lon": lon, "appid": api_key, "units": "metric"},
                timeout=8
            )
        else:
            resp = http_requests.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={"q": city, "appid": api_key, "units": "metric"},
                timeout=8
            )
        resp.raise_for_status()
        d = resp.json()
        return jsonify({
            "city":        geo_name,
            "country":     d["sys"]["country"],
            "temp":        round(d["main"]["temp"]),
            "feelsLike":   round(d["main"]["feels_like"]),
            "humidity":    d["main"]["humidity"],
            "wind":        round(d["wind"]["speed"] * 3.6, 1),
            "description": d["weather"][0]["description"],
            "icon":        d["weather"][0]["icon"],
            "main":        d["weather"][0]["main"],
        }), 200
    except Exception as e:
        return jsonify({"message": "Failed to fetch weather", "error": str(e)}), 500


# ── GET /api/energy/points ────────────────────────────────────────────────────
@energy_bp.route("/points", methods=["GET"])
@protect
def get_energy_points():
    import csv, math, calendar

    db = current_app.config["DB"]

    # ── Find the last fully completed month ────────────────────────────────────
    today = date.today()
    # Go back to the 1st of current month, then subtract 1 day → last day of prev month
    first_of_current = today.replace(day=1)
    last_completed   = first_of_current - timedelta(days=1)  # e.g. 2026-08-31
    comp_year        = last_completed.year                    # 2026
    comp_month       = last_completed.month                   # 8  (August)
    comp_month_name  = last_completed.strftime("%B")          # "August"

    # Date range for that completed month in MongoDB
    month_start = f"{comp_year}-{comp_month:02d}-01"
    month_end   = f"{comp_year}-{comp_month:02d}-{calendar.monthrange(comp_year, comp_month)[1]:02d}"

    # ── Sum MongoDB logs for completed month ───────────────────────────────────
    logs = list(db.energylogs.find({
        "userId": ObjectId(g.user_id),
        "date": {"$gte": month_start, "$lte": month_end}
    }))
    this_year_units = sum(float(l.get("unitsConsumed", 0)) for l in logs)

    # ── Read previous year's value from CSV ───────────────────────────────────
    csv_path = os.path.join(_script_dir, "..", "ml", "dataset", "monthly_units_consumed.csv")
    prev_year        = comp_year - 1      # 2025
    prev_year_units  = None
    month_names      = {
        "January": 1, "February": 2, "March": 3, "April": 4,
        "May": 5, "June": 6, "July": 7, "August": 8,
        "September": 9, "October": 10, "November": 11, "December": 12
    }
    try:
        with open(csv_path, newline="") as f:
            reader = csv.reader(f)
            next(reader, None)  # skip header
            for row in reader:
                if len(row) < 3:
                    continue
                try:
                    r_year  = int(row[0].strip())
                    r_month = month_names.get(row[1].strip(), -1)
                    r_units = float(row[2].strip())
                    if r_year == prev_year and r_month == comp_month:
                        prev_year_units = r_units
                        break
                except (ValueError, IndexError):
                    continue
    except Exception as e:
        return jsonify({"message": f"Could not read CSV: {e}"}), 500

    # ── Calculate points ───────────────────────────────────────────────────────
    if prev_year_units is None:
        return jsonify({
            "points":          0,
            "comparedMonth":   f"{comp_month_name} {comp_year}",
            "prevYearUnits":   None,
            "thisYearUnits":   round(this_year_units, 2),
            "savedUnits":      0,
            "noData":          True,
            "message":         f"No CSV data for {comp_month_name} {prev_year}"
        }), 200

    saved_units = prev_year_units - this_year_units
    points      = math.floor(saved_units / 10) if saved_units > 0 else 0

    return jsonify({
        "points":         points,
        "comparedMonth":  f"{comp_month_name} {comp_year}",
        "prevYear":       prev_year,
        "prevYearUnits":  round(prev_year_units, 2),
        "thisYearUnits":  round(this_year_units, 2),
        "savedUnits":     round(saved_units, 2),
        "noData":         False,
    }), 200


# ── GET /api/energy/logs ───────────────────────────────────────────────────────
@energy_bp.route("/logs", methods=["GET"])
@protect
def get_logs():
    db   = current_app.config["DB"]
    logs = list(db.energylogs.find({"userId": ObjectId(g.user_id)})
                              .sort("date", -1).limit(365))
    logs.reverse()   # chronological order for charts
    return jsonify([_serialize(l) for l in logs]), 200


# ── POST /api/energy/logs ──────────────────────────────────────────────────────
@energy_bp.route("/logs", methods=["POST"])
@protect
def add_log():
    data          = request.get_json()
    units         = float(data.get("unitsConsumed", 0))
    cost_per_unit = float(data.get("costPerUnit", 5))
    today         = str(date.today())    # "YYYY-MM-DD"

    db = current_app.config["DB"]
    db.energylogs.update_one(
        {"userId": ObjectId(g.user_id), "date": today},
        {"$set": {"unitsConsumed": units, "costPerUnit": cost_per_unit, "date": today,
                  "userId": ObjectId(g.user_id)}},
        upsert=True
    )
    log = db.energylogs.find_one({"userId": ObjectId(g.user_id), "date": today})
    return jsonify(_serialize(log)), 200


# ── GET /api/energy/dashboard ──────────────────────────────────────────────────
@energy_bp.route("/dashboard", methods=["GET"])
@protect
def get_dashboard():
    db   = current_app.config["DB"]
    logs = list(db.energylogs.find({"userId": ObjectId(g.user_id)})
                              .sort("date", -1).limit(30))

    user = db.users.find_one({"_id": ObjectId(g.user_id)}) or {}

    # Extract user system settings (DB > query params > defaults)
    sanctioned_load_watts = float(user.get("sanctionedLoad") or request.args.get("sanctionedLoad") or 4000)
    tariff_rate = float(user.get("tariffRate") or request.args.get("tariffRate") or 5.80)
    historical_avg_units = float(user.get("historicalAvg") or request.args.get("historicalAvg") or 113.53)

    sanctioned_load_kw = sanctioned_load_watts / 1000.0
    FIXED_CHARGE_PER_KW = 150
    GRUHA_JYOTHI_MAX_LIMIT = 200.0

    # Calculate dynamic Gruha Jyothi Entitlement: average + 10% buffer, capped at 200 units maximum
    entitlement_units = min(GRUHA_JYOTHI_MAX_LIMIT, round(historical_avg_units * 1.10, 2))

    today_str       = str(date.today())
    today_log       = logs[0] if logs and logs[0]["date"] == today_str else None
    today_units     = today_log["unitsConsumed"] if today_log else 0
    today_cost      = round(today_units * tariff_rate, 2)

    total_units     = sum(l["unitsConsumed"] for l in logs)
    avg_daily       = (total_units / len(logs)) if logs else today_units
    total_units_this_month = avg_daily * 30

    # 3-Tier Gruha Jyothi calculation:
    # Tier 1: Below entitlement (<= entitlement_units): 100% free (Net Bill = ₹0.00, Fixed Charge & Energy Charge waived)
    # Tier 2: Entitlement < units <= 200: Pay excess above entitlement + Fixed Charge
    # Tier 3: Units > 200: Entire subsidy forfeited, 100% units billable + Fixed Charge
    if total_units_this_month <= GRUHA_JYOTHI_MAX_LIMIT:
        free_units = min(total_units_this_month, entitlement_units)
        billable_units = max(0.0, total_units_this_month - entitlement_units)
        subsidy_forfeited = False

        if billable_units == 0.0:
            # Under official Gruha Jyothi scheme, if usage is within entitlement, Govt of Karnataka
            # waives both Energy Charge and Fixed Charge -> Total Bill = ₹0.00
            energy_charge = 0.0
            fixed_charge = 0.0
            predicted_bill = 0.0
        else:
            energy_charge = billable_units * tariff_rate
            fixed_charge = sanctioned_load_kw * FIXED_CHARGE_PER_KW
            predicted_bill = round(energy_charge + fixed_charge, 2)
    else:
        free_units = 0.0
        billable_units = total_units_this_month
        subsidy_forfeited = True
        energy_charge = billable_units * tariff_rate
        fixed_charge = sanctioned_load_kw * FIXED_CHARGE_PER_KW
        predicted_bill = round(energy_charge + fixed_charge, 2)

    yesterday_units = logs[1]["unitsConsumed"] if len(logs) > 1 else 0
    saved_today     = round(yesterday_units - today_units, 2)

    # ── Rewards & Discount Calculation ──
    import csv
    csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ml", "dataset", "monthly_units_consumed.csv")
    prev_year_units = 776.589 # Fallback for July 2025
    try:
        with open(csv_path, newline="") as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                if len(row) >= 3 and row[0].strip() == "2025" and row[1].strip() == "July":
                    prev_year_units = float(row[2].strip())
                    break
    except Exception:
        pass

    saved_units = prev_year_units - total_units_this_month
    if saved_units > 0:
        reward_points = int(saved_units // 10)
        discount = float(reward_points)
    else:
        reward_points = 0
        discount = 0.0

    discount = min(discount, predicted_bill)
    final_bill = predicted_bill - discount

    return jsonify({
        "todayUnits":          today_units,
        "todayCost":           str(today_cost),
        "predictedMonthlyBill":str(predicted_bill),
        "savedToday":          str(max(saved_today, 0)),
        "logsCount":           len(logs),
        "totalUnitsMonth":     round(total_units_this_month, 2),
        "historicalAvg":       historical_avg_units,
        "entitlementUnits":    entitlement_units,
        "maxLimit":            GRUHA_JYOTHI_MAX_LIMIT,
        "freeUnits":           round(free_units, 2),
        "billableUnits":       round(billable_units, 2),
        "subsidyForfeited":    subsidy_forfeited,
        "tariffRate":          tariff_rate,
        "sanctionedLoadKw":    sanctioned_load_kw,
        "energyCharge":        round(energy_charge, 2),
        "fixedCharge":         round(fixed_charge, 2),
        "rewardPoints":        reward_points,
        "discountApplied":     round(discount, 2),
        "finalBill":           round(final_bill, 2),
        "prevYearUnits":       round(prev_year_units, 2)
    }), 200


# ── POST /api/energy/recommendations ──────────────────────────────────────────
@energy_bp.route("/recommendations", methods=["POST"])
@protect
def get_recommendations():
    if _rf_model is None or _feature_cols is None:
        return jsonify({"message": "ML models not loaded. Run predict.py first."}), 500

    data                = request.get_json() or {}
    sanctioned_load_w   = float(data.get("sanctionedLoadWatts", 4000))
    db                  = current_app.config["DB"]

    # ── Fetch live weather ──────────────────────────────────────────────────
    city    = g.user.get("city", "Bangalore")
    api_key = os.getenv("OPENWEATHER_API_KEY", "")
    temp, humidity = 25.0, 60
    try:
        wr = http_requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={"q": city, "appid": api_key, "units": "metric"},
            timeout=8
        )
        if wr.ok:
            wd       = wr.json()
            temp     = round(wd["main"]["temp"])
            humidity = wd["main"]["humidity"]
    except Exception:
        pass

    # ── Determine season & time slot ───────────────────────────────────────
    month = datetime.now().month
    if month in (12, 1, 2):
        season = "Winter"
    elif month in (7, 8, 9, 10, 11):
        season = "Rainy"
    else:
        season = "Summer"

    hour = datetime.now().hour
    if 6 <= hour < 12:
        time_slot = "Morning"
    elif 12 <= hour < 17:
        time_slot = "Afternoon"
    elif 17 <= hour < 21:
        time_slot = "Evening"
    else:
        time_slot = "Night"

    # ── Fetch appliances from DB ───────────────────────────────────────────
    appliances_input = data.get("appliances")
    if not appliances_input:
        raw = list(db.appliances.find({"userId": ObjectId(g.user_id)}))
        appliances_input = [
            {
                "id":          str(a["_id"]),
                "name":        a["name"],
                "priority":    a.get("priority", "Medium"),
                "power":       a["power"],
                "quantity":    a.get("quantity", 1),
                "active":      a.get("active", 0),
                "status":      a.get("status", False),
                "usage_hours": 1.0 if a.get("status") else 0.0,
            }
            for a in raw
        ]

    # ── Compute simultaneous load ──────────────────────────────────────────
    simultaneous_kw = sum(
        a["power"] * a.get("active", 0)
        for a in appliances_input
        if a.get("status") and a.get("active", 0) > 0
    ) / 1000.0
    simultaneous_kw = max(simultaneous_kw, 0.1)
    load_ratio      = (simultaneous_kw * 1000) / sanctioned_load_w

    # ── Run ML inference for each appliance ────────────────────────────────
    recommendations = []
    for app in appliances_input:
        app_name    = app["name"]
        mapped_name = _NAME_MAP.get(app_name.lower(), app_name)
        priority    = app.get("priority", "Medium")
        usage_hrs   = float(app.get("usage_hours", 1.0 if app.get("status") else 0.0))

        row = {
            "temperature_c":       float(temp),
            "humidity_pct":        float(humidity),
            "simultaneous_load_kw":simultaneous_kw,
            "sanctioned_load_watts":sanctioned_load_w,
            "load_ratio":          load_ratio,
            "usage_hours":         usage_hrs,
        }
        # Set all feature columns to 0
        for col in _feature_cols:
            if col not in row:
                row[col] = 0

        # One-hot encode
        for col, val in [
            (f"appliance_name_{mapped_name}", 1),
            (f"priority_{priority}", 1),
            (f"time_slot_{time_slot}", 1),
            (f"season_{season}", 1),
        ]:
            if col in row:
                row[col] = val

        df_input   = pd.DataFrame([row])[_feature_cols]
        prediction = _rf_model.predict(df_input)[0]

        # ── Demo Flow Override ──
        if mapped_name == "AC" and temp < 24:
            prediction = "Suggest_OFF"

        # Custom human-readable reason
        if prediction == "Suggest_OFF":
            if mapped_name == "AC" and temp < 24:
                reason = f"Ambient temperature is cool ({temp}°C). AC is unnecessary."
            elif priority == "Non-essential":
                reason = "Non-essential appliance — consider turning off during peak load."
            else:
                reason = "Turning off this appliance will reduce power consumption."
        elif prediction == "Delay_Load":
            if load_ratio > 0.8:
                reason = (f"System load is at {(load_ratio*100):.1f}% of sanctioned limit "
                          f"({sanctioned_load_w:.0f} W). Avoid heavy appliances now.")
            else:
                reason = "Postpone this high-wattage appliance during peak tariff hours."
        else:
            reason = "Running efficiently under current conditions."

        recommendations.append({
            "id":     app.get("id") or app.get("_id"),
            "name":   app_name,
            "action": prediction,
            "reason": reason,
        })

    return jsonify({
        "season":              season,
        "timeSlot":            time_slot,
        "sanctionedLoadWatts": sanctioned_load_w,
        "simultaneousLoadKw":  simultaneous_kw,
        "temp":                temp,
        "humidity":            humidity,
        "recommendations":     recommendations,
    }), 200


# ── GET /api/energy/notifications ──────────────────────────────────────────────
@energy_bp.route("/notifications", methods=["GET"])
@protect
def get_notifications():
    db = current_app.config["DB"]
    notifications = list(db.notifications.find({"userId": ObjectId(g.user_id), "read": False}).sort("createdAt", -1))
    
    for n in notifications:
        n["_id"] = str(n["_id"])
        n["userId"] = str(n["userId"])
        
    return jsonify(notifications), 200


# ── POST /api/energy/notifications/dismiss ──────────────────────────────────────
@energy_bp.route("/notifications/dismiss", methods=["POST"])
@protect
def dismiss_notification():
    data = request.get_json() or {}
    nid = data.get("notificationId")
    db = current_app.config["DB"]
    
    if nid:
        db.notifications.update_one(
            {"_id": ObjectId(nid), "userId": ObjectId(g.user_id)},
            {"$set": {"read": True}}
        )
    else:
        # Dismiss all
        db.notifications.update_many(
            {"userId": ObjectId(g.user_id)},
            {"$set": {"read": True}}
        )
        
    return jsonify({"message": "Notifications dismissed"}), 200


# ── Simulation Engine Background Thread ───────────────────────────────────────────────────────────────────────────────────
import threading
import time
from routes.stream import notify_clients

def init_simulation(app):
    def run_simulation():
        with app.app_context():
            db = app.config["DB"]
            TARIFF_RATE_RS = 5.80
            SHED_ORDER = ["Non-essential", "Medium", "Essential"]  # Essential is shed only as a last resort

            while True:
                time.sleep(5)
                try:
                    now       = datetime.now()
                    today_str = str(date.today())

                    # ── STEP 0: Daily lock reset ────────────────────────────────────────
                    # Clear locks set on a PREVIOUS day so every day starts fresh
                    db.appliances.update_many(
                        {
                            "lockedBySystem": True,
                            "lockDate": {"$exists": True, "$ne": None, "$lt": today_str}
                        },
                        {
                            "$set": {
                                "lockedBySystem": False,
                                "lockReason":     None,
                                "lockDate":       None
                            }
                        }
                    )

                    # ── STEP 1: Energy accumulation + per-appliance timer ────────────────────
                    active_apps = list(db.appliances.find({"status": True}))
                    if not active_apps:
                        continue

                    for app_doc in active_apps:
                        user_id         = app_doc["userId"]
                        app_id          = app_doc["_id"]
                        power           = app_doc["power"]
                        active_count    = app_doc.get("active", 1)
                        timer_mins      = app_doc.get("timerMinutes")   # real minutes set by user
                        turned_on_str   = app_doc.get("turnedOnAt")
                        last_active_str = app_doc.get("lastActiveAt")

                        if not last_active_str:
                            continue

                        last_active = datetime.fromisoformat(last_active_str)
                        elapsed_sec = (now - last_active).total_seconds()
                        if elapsed_sec <= 0:
                            continue

                        # Accumulate kWh in real-time
                        delta_kwh = (power * active_count * (elapsed_sec / 3600.0)) / 1000.0
                        db.appliances.update_one(
                            {"_id": app_id},
                            {
                                "$inc": {"accumulatedKwhToday": delta_kwh},
                                "$set": {"lastActiveAt": now.isoformat()}
                            }
                        )
                        db.energylogs.update_one(
                            {"userId": user_id, "date": today_str},
                            {
                                "$inc": {"unitsConsumed": delta_kwh},
                                "$set": {"costPerUnit": TARIFF_RATE_RS},
                                "$setOnInsert": {"userId": user_id, "date": today_str}
                            },
                            upsert=True
                        )

                        # ── Timer expiry: normal shutdown, NO lock ─────────────────────
                        if timer_mins and turned_on_str:
                            turned_on        = datetime.fromisoformat(turned_on_str)
                            elapsed_real_min = (now - turned_on).total_seconds() / 60.0

                            if elapsed_real_min >= timer_mins:
                                # Clean shutdown — no lockedBySystem
                                db.appliances.update_one(
                                    {"_id": app_id},
                                    {
                                        "$set": {
                                            "status":       False,
                                            "active":       0,
                                            "turnedOnAt":   None,
                                            "lastActiveAt": None
                                        }
                                    }
                                )
                                used_kwh  = round((power * active_count * (timer_mins / 60.0)) / 1000.0, 3)
                                used_cost = round(used_kwh * TARIFF_RATE_RS, 2)
                                db.notifications.insert_one({
                                    "userId":    user_id,
                                    "title":     f"\u23f1\ufe0f Timer Expired: {app_doc['name']}",
                                    "message":   (
                                        f"Your {app_doc['name']} timer of {timer_mins} min(s) has expired "
                                        f"and was turned off normally. "
                                        f"Energy used: {used_kwh} kWh (\u20b9{used_cost})."
                                    ),
                                    "type":      "timer",
                                    "read":      False,
                                    "createdAt": now.isoformat()
                                })
                                notify_clients("update", {"type": "timer_expiry", "app_id": str(app_id)})

                    # ── STEP 2: Overload check — priority cascade ───────────────────────
                    # Re-fetch after timer shutoffs
                    active_apps = list(db.appliances.find({"status": True}))
                    user_loads = {}
                    for app_doc in active_apps:
                        uid = app_doc["userId"]
                        user_loads.setdefault(uid, []).append(app_doc)

                    for uid, apps in user_loads.items():
                        user_doc     = db.users.find_one({"_id": uid})
                        sanctioned_w = float((user_doc or {}).get("sanctionedLoad", 4000))
                        simultaneous_w = sum(a["power"] * a.get("active", 1) for a in apps)
                        load_pct = (simultaneous_w / sanctioned_w) * 100

                        if simultaneous_w <= sanctioned_w * 0.90:
                            continue   # Load fine — nothing to do

                        shed_done = False
                        for priority_level in SHED_ORDER:
                            candidates = [a for a in apps if a.get("priority") == priority_level]
                            if not candidates:
                                continue

                            # Shed highest-wattage appliance of this priority first
                            target = max(candidates, key=lambda a: a["power"] * a.get("active", 1))
                            lock_reason = (
                                f"Overload: total load was {round(load_pct)}% of your "
                                f"{int(sanctioned_w)}W sanctioned limit. "
                                f"'{target['name']}' ({target['priority']} priority) was shut off "
                                f"to protect your connection."
                            )
                            db.appliances.update_one(
                                {"_id": target["_id"]},
                                {
                                    "$set": {
                                        "status":         False,
                                        "active":         0,
                                        "turnedOnAt":     None,
                                        "lastActiveAt":   None,
                                        "lockedBySystem": True,
                                        "lockReason":     lock_reason,
                                        "lockDate":       today_str
                                    }
                                }
                            )
                            db.notifications.insert_one({
                                "userId":    uid,
                                "title":     "\U0001f6a8 Overload \u2014 Auto-Off Activated",
                                "message":   (
                                    f"Load reached {round(load_pct)}% of your {int(sanctioned_w)}W limit. "
                                    f"'{target['name']}' ({target['priority']} priority) was automatically "
                                    f"turned off. Lock resets tomorrow or override in the Appliances page."
                                ),
                                "type":      "overload",
                                "read":      False,
                                "createdAt": now.isoformat()
                            })
                            notify_clients("update", {"type": "overload_shed", "app_id": str(target["_id"])})
                            shed_done = True
                            break   # One per tick — re-check next cycle

                        if not shed_done:
                            # Only Essential appliances running — warn, never touch them
                            db.notifications.insert_one({
                                "userId":    uid,
                                "title":     "\u26a1 High Load Warning",
                                "message":   (
                                    f"Load at {round(load_pct)}% of your {int(sanctioned_w)}W limit. "
                                    f"All active appliances are Essential — none were auto-turned off. "
                                    f"Please reduce usage manually."
                                ),
                                "type":      "warning",
                                "read":      False,
                                "createdAt": now.isoformat()
                            })

                except Exception as e:
                    print(f"[WARN] Simulation error: {e}")

    t = threading.Thread(target=run_simulation, daemon=True)
    t.start()

