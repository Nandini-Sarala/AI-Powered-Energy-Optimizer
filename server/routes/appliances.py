"""
Appliances Routes — Flask Blueprint
  GET    /api/appliances          → Get all appliances for user
  POST   /api/appliances          → Add new appliance
  PUT    /api/appliances/<id>     → Update appliance
  DELETE /api/appliances/<id>     → Delete appliance
"""

from datetime import datetime, timezone, date
from flask import Blueprint, request, jsonify, current_app, g
from bson import ObjectId
from routes.middleware import protect

def parse_iso_utc(iso_str):
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None

appliances_bp = Blueprint("appliances", __name__)


def _serialize(doc):
    """Convert a MongoDB document to a JSON-serializable dict."""
    doc["_id"] = str(doc["_id"])
    if "userId" in doc:
        doc["userId"] = str(doc["userId"])
    return doc


# ── GET /api/appliances ────────────────────────────────────────────────────────
@appliances_bp.route("", methods=["GET"], strict_slashes=False)
@protect
def get_appliances():
    db = current_app.config["DB"]
    appliances = list(db.appliances.find({"userId": ObjectId(g.user_id)}))
    return jsonify([_serialize(a) for a in appliances]), 200


# ── POST /api/appliances ───────────────────────────────────────────────────────
@appliances_bp.route("", methods=["POST"], strict_slashes=False)
@protect
def add_appliance():
    data = request.get_json()
    name         = (data.get("name") or "").strip()
    power        = data.get("power")
    quantity     = data.get("quantity", 1)
    priority     = data.get("priority", "Medium")
    active       = data.get("active", 0)
    status       = data.get("status", False)
    timer_raw    = data.get("timerMinutes")  # optional — real minutes
    timer_mins   = int(timer_raw) if timer_raw is not None and str(timer_raw).strip() != "" else None

    if not name or not power:
        return jsonify({"message": "Name and power are required"}), 400

    now_iso = datetime.now(timezone.utc).isoformat() if status else None

    db = current_app.config["DB"]
    result = db.appliances.insert_one({
        "userId":        ObjectId(g.user_id),
        "name":          name,
        "power":         int(power),
        "quantity":      int(quantity),
        "priority":      priority,
        "active":        int(active),
        "status":        bool(status),
        "timerMinutes":  timer_mins,
        "turnedOnAt":    now_iso,
        "lastActiveAt":  now_iso,
        "lastSeenAt":    now_iso,
    })

    new_doc = db.appliances.find_one({"_id": result.inserted_id})
    return jsonify(_serialize(new_doc)), 201


# ── PUT /api/appliances/<id> ───────────────────────────────────────────────────
@appliances_bp.route("/<app_id>", methods=["PUT"])
@protect
def update_appliance(app_id):
    data = request.get_json()
    db   = current_app.config["DB"]

    # Fetch existing to check old status
    existing = db.appliances.find_one({"_id": ObjectId(app_id), "userId": ObjectId(g.user_id)})
    if not existing:
        return jsonify({"message": "Appliance not found or unauthorized"}), 404

    update_fields = {}
    if "name"     in data: update_fields["name"]     = data["name"].strip()
    if "power"    in data: update_fields["power"]    = int(data["power"])
    if "quantity" in data: update_fields["quantity"] = int(data["quantity"])
    if "priority" in data: update_fields["priority"] = data["priority"]
    if "active"   in data: update_fields["active"]   = int(data["active"])

    # ── Timer: accept timerMinutes (real minutes, None = no timer) ─
    if "timerMinutes" in data:
        timer_raw = data["timerMinutes"]
        update_fields["timerMinutes"] = (
            int(timer_raw)
            if timer_raw is not None and str(timer_raw).strip() != ""
            else None
        )

    if "status" in data:
        new_status = bool(data["status"])
        old_status = existing.get("status", False)
        is_locked  = existing.get("lockedBySystem", False)
        override   = bool(data.get("override", False))

        # ── Lock guard: system auto-turned this off ────────────────
        if new_status and is_locked and not override:
            return jsonify({
                "locked":     True,
                "lockReason": existing.get("lockReason", "This appliance was turned off by the system."),
                "message":    "Appliance is locked by system. Send override=true to force enable."
            }), 409

        now_utc = datetime.now(timezone.utc).isoformat()
        update_fields["status"] = new_status
        update_fields["lastToggledAt"] = now_utc

        if new_status and not old_status:
            update_fields["turnedOnAt"]   = now_utc
            update_fields["lastActiveAt"] = now_utc
            update_fields["lastSeenAt"]   = now_utc

        elif not new_status:
            update_fields["turnedOnAt"]   = None
            update_fields["lastActiveAt"] = None

        # If turning ON with override → clear the lock
        if new_status and override:
            update_fields["lockedBySystem"] = False
            update_fields["lockReason"]     = None
            update_fields["lockDate"]       = None
            update_fields["turnedOnAt"]   = now_utc
            update_fields["lastActiveAt"] = now_utc
            update_fields["lastSeenAt"]   = now_utc

    result = db.appliances.update_one(
        {"_id": ObjectId(app_id), "userId": ObjectId(g.user_id)},
        {"$set": update_fields}
    )

    updated = db.appliances.find_one({"_id": ObjectId(app_id)})
    return jsonify(_serialize(updated)), 200


# ── GET /api/appliances/<id>/status (Lightweight for ESP32) ────────────────
@appliances_bp.route("/<app_id>/status", methods=["GET"])
@protect
def get_appliance_status(app_id):
    db = current_app.config["DB"]
    app_doc = db.appliances.find_one({"_id": ObjectId(app_id), "userId": ObjectId(g.user_id)})
    if not app_doc:
        return jsonify({"message": "Not found"}), 404
    return jsonify({"status": app_doc.get("status", False)}), 200

# ── DELETE /api/appliances/<id> ────────────────────────────────────────────────
@appliances_bp.route("/<app_id>", methods=["DELETE"])
@protect
def delete_appliance(app_id):
    db     = current_app.config["DB"]
    result = db.appliances.delete_one(
        {"_id": ObjectId(app_id), "userId": ObjectId(g.user_id)}
    )

    if result.deleted_count == 0:
        return jsonify({"message": "Appliance not found or unauthorized"}), 404

    return jsonify({"message": "Appliance deleted successfully"}), 200

# ── POST /api/appliances/<id>/physical-toggle ──────────────────────────────────
@appliances_bp.route("/<app_id>/physical-toggle", methods=["POST"])
@protect
def physical_toggle(app_id):
    db = current_app.config["DB"]
    app_doc = db.appliances.find_one({"_id": ObjectId(app_id), "userId": ObjectId(g.user_id)})
    if not app_doc:
        return jsonify({"message": "Not found"}), 404

    from routes.stream import notify_clients

    # If the system locked it, reject the physical switch!
    now_utc = datetime.now(timezone.utc).isoformat()
    if app_doc.get("lockedBySystem"):
        db.notifications.insert_one({
            "userId": ObjectId(g.user_id),
            "title": "🛡️ Physical Switch Blocked",
            "message": f"Someone physically tried to turn on '{app_doc['name']}', but it was blocked because it's locked by the system (Overload).",
            "type": "warning",
            "read": False,
            "createdAt": now_utc
        })
        notify_clients("update", {"type": "physical_blocked", "app_id": str(app_id)})
        return jsonify({"message": "Blocked by system lock"}), 403

    # Toggle status
    new_status = not app_doc.get("status", False)
    update_fields = {"status": new_status, "active": 1 if new_status else 0, "lastToggledAt": now_utc}
    
    if new_status:
        update_fields["turnedOnAt"] = now_utc
        update_fields["lastActiveAt"] = now_utc
        update_fields["lastSeenAt"] = now_utc  # ← Stamp heartbeat NOW so watchdog doesn't fire immediately
    else:
        update_fields["turnedOnAt"] = None
        update_fields["lastActiveAt"] = None

    db.appliances.update_one({"_id": ObjectId(app_id)}, {"$set": update_fields})
    updated = db.appliances.find_one({"_id": ObjectId(app_id)})
    
    notify_clients("update", {"type": "physical_toggle", "app_id": str(app_id)})
    
    return jsonify(_serialize(updated)), 200

# ── POST /api/appliances/<id>/heartbeat ───────────────────────────────────────
@appliances_bp.route("/<app_id>/heartbeat", methods=["POST"])
@protect
def heartbeat(app_id):
    db = current_app.config["DB"]
    db.appliances.update_one(
        {"_id": ObjectId(app_id), "userId": ObjectId(g.user_id)},
        {"$set": {"lastSeenAt": datetime.now(timezone.utc).isoformat()}}
    )
    return jsonify({"message": "Heartbeat received"}), 200

# ── POST /api/appliances/<id>/offline-sync ────────────────────────────────────
@appliances_bp.route("/<app_id>/offline-sync", methods=["POST"])
@protect
def offline_sync(app_id):
    data = request.get_json() or {}
    toggle_time_str = data.get("toggleTime")
    final_state = bool(data.get("finalState", False))
    
    db = current_app.config["DB"]
    app_doc = db.appliances.find_one({"_id": ObjectId(app_id), "userId": ObjectId(g.user_id)})
    if not app_doc:
        return jsonify({"message": "Not found"}), 404
        
    last_db_active_str = app_doc.get("lastToggledAt")
    previous_status = app_doc.get("status", False)
    
    # ── 1. Resolve Timestamp Race Condition ──
    # If the user toggled the virtual dashboard *after* the hardware went offline, the virtual board wins!
    if last_db_active_str and toggle_time_str:
        if last_db_active_str > toggle_time_str:
            final_state = previous_status
            
    now_dt = datetime.now(timezone.utc)
    now_utc = now_dt.isoformat()
    today_str = str(date.today())
    TARIFF_RATE_RS = 5.80

    # ── 2. False Data & Billing Correction ──
    correction_msg = ""
    toggle_dt = parse_iso_utc(toggle_time_str)
    current_accum = float(app_doc.get("accumulatedKwhToday", 0.0))
    power = float(app_doc.get("power", 0))
    active_count = int(app_doc.get("active", 1) or 1)

    if toggle_dt and previous_status != final_state:
        elapsed_sec = (now_dt - toggle_dt).total_seconds()
        if 0 < elapsed_sec < 86400:  # Only reconcile if toggled within the last 24h
            delta_kwh = round((power * active_count * (elapsed_sec / 3600.0)) / 1000.0, 4)
            delta_rs = round(delta_kwh * TARIFF_RATE_RS, 2)
            today_log = db.energylogs.find_one({"userId": ObjectId(g.user_id), "date": today_str})

            if previous_status and not final_state:
                # Appliance was turned OFF offline, but server ran it: REFUND phantom kWh
                current_accum = max(0.0, current_accum - delta_kwh)
                if today_log:
                    new_units = max(0.0, float(today_log.get("unitsConsumed", 0.0)) - delta_kwh)
                    cur_bd = float((today_log.get("breakdown") or {}).get(app_doc['name'], 0.0))
                    new_bd = max(0.0, cur_bd - delta_kwh)
                    db.energylogs.update_one(
                        {"_id": today_log["_id"]},
                        {"$set": {"unitsConsumed": round(new_units, 4), f"breakdown.{app_doc['name']}": round(new_bd, 4)}}
                    )
                correction_msg = f" Refunded {round(delta_kwh, 3)} kWh (~₹{delta_rs}) billed while Wi-Fi was down."

            elif not previous_status and final_state:
                # Appliance was turned ON offline, but server had it off: BACKFILL true kWh
                current_accum = current_accum + delta_kwh
                db.energylogs.update_one(
                    {"userId": ObjectId(g.user_id), "date": today_str},
                    {
                        "$inc": {
                            "unitsConsumed": delta_kwh,
                            f"breakdown.{app_doc['name']}": delta_kwh
                        },
                        "$setOnInsert": {"costPerUnit": TARIFF_RATE_RS}
                    },
                    upsert=True
                )
                correction_msg = f" Backfilled {round(delta_kwh, 3)} kWh (~₹{delta_rs}) consumed while Wi-Fi was down."

    # ── 3. Log Notification ──
    db.notifications.insert_one({
        "userId": ObjectId(g.user_id),
        "title": "🔄 Offline Sync Complete",
        "message": f"'{app_doc['name']}' reconnected! Final state synced to {'ON' if final_state else 'OFF'}.{correction_msg}",
        "type": "success",
        "read": False,
        "createdAt": now_utc
    })
    
    # ── 4. Set final state ──
    update_fields = {
        "status": bool(final_state),
        "active": 1 if final_state else 0,
        "lastToggledAt": now_utc,
        "accumulatedKwhToday": round(current_accum, 4)
    }
    if final_state:
        update_fields["turnedOnAt"] = now_utc
        update_fields["lastActiveAt"] = now_utc
        update_fields["lastSeenAt"] = now_utc
    else:
        update_fields["turnedOnAt"] = None
        update_fields["lastActiveAt"] = None
        
    db.appliances.update_one({"_id": ObjectId(app_id)}, {"$set": update_fields})
        
    from routes.stream import notify_clients
    notify_clients("update", {"type": "offline_sync_complete", "app_id": str(app_id)})
        
    return jsonify({"message": "Sync complete"}), 200
