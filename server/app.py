"""
AI-Powered Energy Consumption Optimizer — Flask Backend
=======================================================
Routes:
  POST   /api/auth/register
  POST   /api/auth/login
  PUT    /api/auth/profile
  GET    /api/energy/weather
  GET    /api/energy/logs
  POST   /api/energy/logs
  GET    /api/energy/dashboard
  POST   /api/energy/recommendations
  GET    /api/appliances
  POST   /api/appliances
  PUT    /api/appliances/<id>
  DELETE /api/appliances/<id>
"""

import os
from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

app = Flask(__name__)

# ── CORS: Allow any localhost origin (React on 5173, 5174, etc.) ───────────────
CORS(app, origins=["http://localhost:5173", "http://localhost:5174",
                   "http://localhost:5175", "http://localhost:3000"],
     supports_credentials=True)

# ── JWT Configuration ──────────────────────────────────────────────────────────
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET", "energy_ai_secret_key_2024")
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = False   # tokens last 7 days effectively
jwt = JWTManager(app)

# ── MongoDB Connection ─────────────────────────────────────────────────────────
MONGO_URI = os.getenv("MONGO_URI")
try:
    client = MongoClient(MONGO_URI)
    db = client["energy_optimizer"]
    # Expose db to blueprints via app config
    app.config["DB"] = db
    print("[OK] MongoDB connected")
except Exception as e:
    print(f"[ERROR] MongoDB connection error: {e}")
    exit(1)

# ── Register Blueprints ────────────────────────────────────────────────────────
from routes.auth import auth_bp
from routes.energy import energy_bp
from routes.appliances import appliances_bp
from routes.chat import chat_bp

app.register_blueprint(auth_bp, url_prefix="/api/auth")
app.register_blueprint(energy_bp, url_prefix="/api/energy")
app.register_blueprint(appliances_bp, url_prefix="/api/appliances")
app.register_blueprint(chat_bp, url_prefix="/api/chat")

from routes.stream import stream_bp
app.register_blueprint(stream_bp, url_prefix="/api/stream")

# ── Start Simulation Engine daemon thread ──────────────────────────────────────
from routes.energy import init_simulation
init_simulation(app)

# ── Health check ───────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return {"message": "Energy Optimizer API is running (Flask)"}

@app.route("/api/health")
def health_check():
    try:
        # Ping MongoDB to ensure it is connected and responding
        db.command("ping")
        return {"status": "ok", "database": "connected"}, 200
    except Exception as e:
        return {"status": "error", "database": "disconnected", "details": str(e)}, 503

# ── Start Server ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"[OK] Flask server running on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
