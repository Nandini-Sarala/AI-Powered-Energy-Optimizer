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
│   │   │   ├── PrivateRoute.jsx   ← Route guard (requires JWT)
│   │   │   └── EnergyBot.jsx      ← AI Chatbot UI
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
│   │   ├── dataset/               ← Historical usage datasets (CSV)
│   │   └── models/                ← Serialized Scikit-Learn models
│   ├── routes/
│   │   ├── auth.py                ← POST /api/auth/login, /register
│   │   ├── energy.py              ← Calendar bill prediction, rewards
│   │   ├── appliances.py          ← CRUD operations for appliances
│   │   ├── chat.py                ← AI Chatbot (Groq API, RAG, Web Scraper)
│   │   └── middleware.py          ← JWT protection & helpers
│   ├── chroma_db/                 ← Local vector database for RAG (Ignored in Git)
│   ├── app.py                     ← Flask server entry & health check
│   ├── physical_simulator.py      ← ESP32 Wokwi Hardware Simulator Integration
│   ├── requirements.txt           ← Python dependencies
│   └── .env                       ← PORT, MONGO_URI, JWT_SECRET, GROQ_API_KEY
```

---

## 🚀 Key Features & Edge-Cases Solved

1. **AI Budget Guard (Predictive Bill Balancing)**: A machine learning script (`ai_budget_calculator.py`) analyzes historical `monthly_units_consumed.csv` datasets to calculate a strict daily house budget. It intelligently distributes this budget using priority multipliers (Medium gets 2x shares vs Non-essential). It also features a compassionate "Minimum Grace Allowance" (min 1.0 kWh) to ensure the house is never paralyzed, even if the math budget is negative.
2. **Real-Time Budget Enforcer**: The core simulation loop tracks accumulated kWh every second. The exact moment an appliance hits its AI-assigned limit, it is forced OFF and safely locked (`lockedBySystem = True`) with a dashboard alert to protect the user's monthly budget.
3. **Smart Virtual Breaker (Grid Overload)**: When the sanctioned load is exceeded (>90%), the system checks priorities (Non-essential -> Medium) and intelligently shuts down appliances to protect the grid. Instead of locking them, it sends a "Smart Recommendation" to the user to wait before turning them back on.
4. **Hardware Resilience (Edge-Cases Solved)**: 
   - **Total Power Cut (Watchdog)**: A real-time heartbeat ping detects massive grid failures (30s+ timeout) and instantly blacks out the React dashboard.
   - **Wi-Fi Disconnects (Offline Caching)**: If the router dies but electricity remains, the ESP32 physical simulator caches local hardware button presses. When Wi-Fi is restored, it bulk-syncs all offline events to the cloud database.
5. **Dashboard Analytics & Calendar Billing**: Real-time energy prediction, precise calendar-month billing logic, and dynamic charts (Recharts).
6. **AI EnergyBot (RAG Chatbot)**: A localized AI assistant powered by Groq (Qwen/LLaMa) and ChromaDB. It understands your specific tariff/appliance data and safely falls back to live DuckDuckGo web scraping if local documents are missing.
7. **Persistent Reward Wallet**: Users earn reward points directly based on actual energy savings compared to historical CSV datasets, which are securely persisted in MongoDB.
8. **Automated Password Recovery**: Secure SMTP-based "Forgot Password" flow using Python `smtplib` and MIME to instantly email randomized temporary passwords.
9. **Cloud-Ready**: Comes with `start.sh`, `gunicorn`, and clear configurations for instant deployment to Render, Vercel, and MongoDB Atlas.

---

## 🚀 How to Run

### Step 1 — Database and API Setup
1. **Groq API**: Get a free API key from [Groq Cloud](https://console.groq.com/keys) to run the AI chatbot.
2. **OpenWeatherMap**: Get a free API key from [OpenWeatherMap](https://openweathermap.org/api).
3. **MongoDB**: Have a local MongoDB running (`mongodb://localhost:27017`) OR a cloud Atlas cluster.
4. **Gmail SMTP (Optional)**: For the "Forgot Password" feature, generate a 16-letter App Password in your Google Account security settings.
5. Paste these credentials into both `.env` files:
   - `server/.env` → `OPENWEATHER_API_KEY`, `MONGO_URI`, `GROQ_API_KEY`, `SMTP_EMAIL`, and `SMTP_PASSWORD`
   - `client/.env` → `VITE_OPENWEATHER_API_KEY`

### Step 2 — Start Backend (Python/Flask)
Open a terminal and run:
```bash
cd server
python -m venv venv           # Optional: Create virtual environment
.\venv\Scripts\activate       # Optional: Activate it (Windows)
pip install -r requirements.txt
python app.py
# Server runs on http://localhost:5000
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
Dashboard       →  GET /api/energy/dashboard →  PyMongo fetch & Billing logic
                ←  { stats, rewards }        ←  Calculates Wallet Discounts

EnergyBot UI    →  POST /api/chat            →  ChromaDB / Groq LLM API
                ←  { reply }                 ←  RAG + Web Scraper

Physical Switch →  POST /api/hardware        →  Flask processes manual override
(Wokwi ESP32)   ←  GET  /api/hardware        ←  ESP32 polls backend every 3s
```

### Key Concepts Used:
| Concept | Where Used |
|---------|-----------|
| **JWT Authentication** | `Flask-JWT-Extended` — `create_access_token()` + `@jwt_required()` |
| **Retrieval-Augmented Generation (RAG)** | `chat.py` — Combining ChromaDB local rules with Groq LLM |
| **React Context API** | `AuthContext.jsx` — global auth state |
| **Axios Interceptors** | `api.js` — auto-attach JWT to all requests |
| **PyMongo Database** | Native MongoDB queries |
| **IoT Architecture** | HTTP Polling from Wokwi ESP32 to Python via Localtunnel |
