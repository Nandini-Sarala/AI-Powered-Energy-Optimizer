"""
Auth Routes — Flask Blueprint
  POST  /api/auth/register   → Register new user
  POST  /api/auth/login      → Login & get JWT
  PUT   /api/auth/profile    → Update profile (protected)
"""

import bcrypt
from flask import Blueprint, request, jsonify, current_app, g
from flask_jwt_extended import create_access_token
from bson import ObjectId
from datetime import timedelta
from routes.middleware import protect

auth_bp = Blueprint("auth", __name__)


def _user_response(user, token):
    """Helper: build the standard user JSON response."""
    return {
        "_id":            str(user["_id"]),
        "name":           user["name"],
        "email":          user["email"],
        "city":           user.get("city", "Bangalore"),
        "sanctionedLoad": user.get("sanctionedLoad", 4000),
        "tariffRate":     user.get("tariffRate", 5.80),
        "historicalAvg":  user.get("historicalAvg", 113.53),
        "token":          token,
    }


# ── POST /api/auth/register ────────────────────────────────────────────────────
@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    name     = (data.get("name") or "").strip()
    email    = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    city     = (data.get("city") or "Bangalore").strip()

    if not name or not email or not password:
        return jsonify({"message": "Name, email and password are required"}), 400

    db = current_app.config["DB"]

    # Check if email already exists
    if db.users.find_one({"email": email}):
        return jsonify({"message": "Email already registered"}), 400

    # Hash password with bcrypt and store as string (Node.js compatible)
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    result = db.users.insert_one({
        "name":           name,
        "email":          email,
        "password":       hashed,
        "city":           city,
        "sanctionedLoad": 4000,
        "tariffRate":     5.80,
        "historicalAvg":  113.53
    })

    user = db.users.find_one({"_id": result.inserted_id})
    token = create_access_token(identity=str(user["_id"]),
                                expires_delta=timedelta(days=7))
    return jsonify(_user_response(user, token)), 201


# ── POST /api/auth/login ───────────────────────────────────────────────────────
@auth_bp.route("/login", methods=["POST"])
def login():
    data     = request.get_json()
    email    = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    db = current_app.config["DB"]
    user = db.users.find_one({"email": email})

    if not user:
        return jsonify({"message": "Invalid email or password"}), 401

    stored_password = user.get("password", "")
    if isinstance(stored_password, str):
        stored_password = stored_password.encode("utf-8")

    if not bcrypt.checkpw(password.encode("utf-8"), stored_password):
        return jsonify({"message": "Invalid email or password"}), 401

    token = create_access_token(identity=str(user["_id"]),
                                expires_delta=timedelta(days=7))
    return jsonify(_user_response(user, token)), 200


# ── PUT /api/auth/profile ──────────────────────────────────────────────────────
@auth_bp.route("/profile", methods=["PUT"])
@protect
def update_profile():
    data  = request.get_json()
    db    = current_app.config["DB"]
    uid   = ObjectId(g.user_id)

    update_fields = {}
    if data.get("name"):  update_fields["name"]  = data["name"].strip()
    if data.get("email"): update_fields["email"] = data["email"].strip().lower()
    if data.get("city"):  update_fields["city"]  = data["city"].strip()
    if "sanctionedLoad" in data: update_fields["sanctionedLoad"] = float(data["sanctionedLoad"])
    if "tariffRate" in data:     update_fields["tariffRate"]     = float(data["tariffRate"])
    if "historicalAvg" in data:  update_fields["historicalAvg"]  = float(data["historicalAvg"])

    if data.get("password"):
        update_fields["password"] = bcrypt.hashpw(
            data["password"].encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

    db.users.update_one({"_id": uid}, {"$set": update_fields})
    user  = db.users.find_one({"_id": uid})
    token = create_access_token(identity=str(user["_id"]),
                                expires_delta=timedelta(days=7))
    return jsonify(_user_response(user, token)), 200

# ── POST /api/auth/reset-password-demo ───────────────────────────────────────────
@auth_bp.route("/reset-password-demo", methods=["POST"])
def reset_password_demo():
    data = request.get_json()
    email = (data.get("email") or "").strip().lower()
    
    if not email:
        return jsonify({"message": "Email is required"}), 400
        
    db = current_app.config["DB"]
    user = db.users.find_one({"email": email})
    
    if not user:
        return jsonify({"message": "No account found with this email"}), 404
        
    import random
    import string
    
    # Generate a random password for the demo
    temp_password = "demo" + "".join(random.choices(string.digits, k=4))
    hashed = bcrypt.hashpw(temp_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    
    db.users.update_one(
        {"email": email},
        {"$set": {"password": hashed}}
    )
    
    # Send Email via SMTP
    import smtplib
    import os
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    sender_email = os.getenv("SMTP_EMAIL")
    sender_password = os.getenv("SMTP_PASSWORD")
    
    if sender_email and sender_password:
        try:
            msg = MIMEMultipart()
            msg['From'] = sender_email
            msg['To'] = email
            msg['Subject'] = "Password Reset - AI Energy Optimizer"
            
            body = f"Hello {user.get('name', 'User')},\n\nYour password has been successfully reset.\n\nYour new temporary password is: {temp_password}\n\nPlease log in and change your password as soon as possible.\n\nBest,\nAI Energy Optimizer Team"
            msg.attach(MIMEText(body, 'plain'))
            
            # Connect to Gmail SMTP server
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(sender_email, sender_password)
            text = msg.as_string()
            server.sendmail(sender_email, email, text)
            server.quit()
        except Exception as e:
            print(f"Failed to send email: {e}")
    else:
        print(f"SMTP Credentials not set. Temp password is: {temp_password}")
        
    return jsonify({
        "message": "Password reset successful. Check your email."
    }), 200
