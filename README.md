# ⚡ AI Powered Energy Consumption Optimizer
### Python Flask + React Project — Full Documentation

---

## 🗂️ Project Structure
```
AI-Powered-Energy-Optimizer/
├── client/                    # React + Vite Frontend
│   ├── src/
│   │   ├── context/
│   │   │   └── AuthContext.jsx    ← Global JWT auth state
│   │   ├── services/
│   │   │   └── api.js             ← Axios instance + JWT interceptor
│   │   ├── components/
│   │   │   ├── Sidebar.jsx        ← Navigation sidebar
│   │   │   └── PrivateRoute.jsx   ← Route guard (requires JWT)
│   │   ├── pages/
│   │   │   ├── Login.jsx          ← Login / Signup page
│   │   │   ├── Dashboard.jsx      ← Main dashboard (⭐ Key page)
│   │   │   └── Appliances.jsx     ← Appliance management & AI timers
│   │   ├── App.jsx                ← Router + layouts
│   │   ├── main.jsx               ← React entry point
│   │   └── index.css              ← Global design system
│   └── .env                       ← VITE_API_BASE_URL, OPENWEATHER_KEY
│
├── server/                    # Python + Flask Backend
│   ├── ml/                        # Machine Learning Models
│   │   ├── predict.py             ← ML Prediction Logic
│   │   └── models/                ← Serialized Scikit-Learn models
│   ├── routes/
│   │   ├── auth.py                ← POST /api/auth/login, /register
│   │   ├── energy.py              ← GET /api/energy/weather, /logs, AI shed logic
│   │   ├── appliances.py          ← CRUD operations for appliances
│   │   └── middleware.py          ← JWT protection & helpers
│   ├── app.py                     ← Flask server entry & health check
│   ├── physical_simulator.py      ← ESP32 Wokwi Hardware Simulator Integration
│   ├── requirements.txt           ← Python dependencies
│   └── .env                       ← PORT, MONGO_URI, JWT_SECRET, OPENWEATHER_API_KEY
```

---

## 🚀 Key Features Built

1. **Dashboard Analytics**: Real-time energy prediction, charts (Recharts), weather integration, and reward points.
2. **AI Aggressive Load Shedding**: When sanctioned load is exceeded, the system automatically checks priorities (Non-essential -> Medium -> Essential) and intelligently shuts down appliances to protect the grid.
3. **Physical Hardware Integration (ESP32)**: Built-in support for Wokwi ESP32 Simulation. Allows real-time HTTP polling and interaction between physical switches and the React dashboard via a local tunnel.
4. **Appliance Timers**: Manual shutdown timers applied directly to devices via the Appliances UI.
5. **Production Health Checks**: The Flask backend exposes a `/api/health` endpoint that actively pings the MongoDB cluster to ensure system uptime.

---

## 🚀 How to Run

### Step 1 — Database and API Setup
1. **OpenWeatherMap**: Go to [OpenWeatherMap](https://openweathermap.org/api), sign up, get your free API key.
2. **MongoDB**: Have a local MongoDB running (`mongodb://localhost:27017`) OR a cloud Atlas cluster.
3. Paste these credentials into both `.env` files:
   - `server/.env` → `OPENWEATHER_API_KEY` and `MONGO_URI`
   - `client/.env` → `VITE_OPENWEATHER_API_KEY` (if used directly by frontend)

### Step 2 — Start Backend (Python/Flask)
Open a terminal and run:
```bash
cd server
python -m venv venv           # Optional: Create virtual environment
.\venv\Scripts\activate       # Optional: Activate it (Windows)
pip install -r requirements.txt
python app.py
# Server runs on http://localhost:5000
# Check Health: http://localhost:5000/api/health
```

### Step 3 — Start Frontend (React/Vite)
Open a **second** terminal and run:
```bash
cd client
npm install
npm run dev
# App runs on http://localhost:5173
```

### Step 4 — Run the Hardware Simulator (Optional)
If you want to sync your React dashboard with the ESP32 physical hardware simulator:
```bash
cd server
python physical_simulator.py
```
*This will generate a Localtunnel URL that you can paste into your Wokwi C++ sketch!*

---

## 🏗️ Architecture (React + Flask + MongoDB + Hardware)

```
React (Vite)                Flask (Python)          MongoDB / ML Models / ESP32
─────────────               ──────────────          ──────────────────────────
Dashboard       →  GET /api/energy/dashboard →  PyMongo fetch & AI logic
                ←  { stats, notifications }  ←  Aggressive shedding evaluation

Physical Switch →  POST /api/hardware        →  Flask processes manual override
(Wokwi ESP32)   ←  GET  /api/hardware        ←  ESP32 polls backend every 3s
```

### Key Concepts Used:
| Concept | Where Used |
|---------|-----------|
| **JWT Authentication** | `Flask-JWT-Extended` — `create_access_token()` + `@jwt_required()` |
| **Password Hashing** | `bcrypt` python library in `auth.py` |
| **React Context API** | `AuthContext.jsx` — global auth state |
| **Axios Interceptors** | `api.js` — auto-attach JWT to all requests |
| **PyMongo Database** | Native MongoDB queries and Health Checks (`db.command('ping')`) |
| **IoT Architecture** | HTTP Polling from Wokwi ESP32 to Python via Localtunnel |

---

## 🔐 Authentication Flow
```
1. User fills signup form → POST /api/auth/register
2. Server (Flask): bcrypt hashes password → PyMongo saves to MongoDB
3. Server (Flask): Flask-JWT-Extended signs JWT → returns to client
4. Client (React): stores token in localStorage
5. All subsequent requests: Axios interceptor adds "Authorization: Bearer <token>"
6. Protected routes: @jwt_required() decorator verifies JWT in Flask routes
```
