"""Script to cleanly rewrite the simulation section of energy.py"""

NEW_SIMULATION = '''# \u2500\u2500 Simulation Engine Background Thread \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
import threading
import time
from routes.stream import notify_clients

def init_simulation(app):
    def run_simulation():
        with app.app_context():
            db = app.config["DB"]
            TARIFF_RATE_RS = 5.80
            SHED_ORDER = ["Non-essential", "Medium"]  # Essential is NEVER auto-turned off

            while True:
                time.sleep(5)
                try:
                    now       = datetime.now()
                    today_str = str(date.today())

                    # \u2500\u2500 STEP 0: Daily lock reset \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
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

                    # \u2500\u2500 STEP 1: Energy accumulation + per-appliance timer \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
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

                        # \u2500\u2500 Timer expiry: normal shutdown, NO lock \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
                        if timer_mins and turned_on_str:
                            turned_on        = datetime.fromisoformat(turned_on_str)
                            elapsed_real_min = (now - turned_on).total_seconds() / 60.0

                            if elapsed_real_min >= timer_mins:
                                # Clean shutdown \u2014 no lockedBySystem
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
                                    "title":     f"\\u23f1\\ufe0f Timer Expired: {app_doc[\'name\']}",
                                    "message":   (
                                        f"Your {app_doc[\'name\']} timer of {timer_mins} min(s) has expired "
                                        f"and was turned off normally. "
                                        f"Energy used: {used_kwh} kWh (\\u20b9{used_cost})."
                                    ),
                                    "type":      "timer",
                                    "read":      False,
                                    "createdAt": now.isoformat()
                                })
                                notify_clients("update", {"type": "timer_expiry", "app_id": str(app_id)})

                    # \u2500\u2500 STEP 2: Overload check \u2014 priority cascade \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
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
                            continue   # Load fine \u2014 nothing to do

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
                                f"\'{target[\'name\']}\' ({target[\'priority\']} priority) was shut off "
                                f"to protect your connection. Essential appliances were NOT affected."
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
                                "title":     "\\U0001f6a8 Overload \\u2014 Auto-Off Activated",
                                "message":   (
                                    f"Load reached {round(load_pct)}% of your {int(sanctioned_w)}W limit. "
                                    f"\'{target[\'name\']}\' ({target[\'priority\']} priority) was automatically "
                                    f"turned off. Essential appliances were NOT affected. "
                                    f"Lock resets tomorrow or override in the Appliances page."
                                ),
                                "type":      "overload",
                                "read":      False,
                                "createdAt": now.isoformat()
                            })
                            notify_clients("update", {"type": "overload_shed", "app_id": str(target["_id"])})
                            shed_done = True
                            break   # One per tick \u2014 re-check next cycle

                        if not shed_done:
                            # Only Essential appliances running \u2014 warn, never touch them
                            db.notifications.insert_one({
                                "userId":    uid,
                                "title":     "\\u26a1 High Load Warning",
                                "message":   (
                                    f"Load at {round(load_pct)}% of your {int(sanctioned_w)}W limit. "
                                    f"All active appliances are Essential \u2014 none were auto-turned off. "
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
'''

with open('routes/energy.py', 'r', encoding='utf-8') as f:
    content = f.read()

cut = content.find('# \u2500\u2500 Simulation Engine Background Thread')
if cut == -1:
    print("ERROR: marker not found")
else:
    new_content = content[:cut] + NEW_SIMULATION + '\n'
    with open('routes/energy.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print(f"Done. File is now {len(new_content)} chars, {new_content.count(chr(10))} lines")
