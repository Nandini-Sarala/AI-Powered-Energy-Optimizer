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

## 🚀 Key Features Built

1. **Dashboard Analytics & Calendar Billing**: Real-time energy prediction, precise calendar-month billing logic, and dynamic charts (Recharts).
2. **AI EnergyBot (RAG Chatbot)**: A localized AI assistant powered by Groq (Qwen/LLaMa) and ChromaDB. It understands your specific tariff/appliance data and safely falls back to live DuckDuckGo web scraping if local documents are missing.
3. **Persistent Reward Wallet**: Users earn reward points directly based on actual energy savings compared to historical CSV datasets, which are securely persisted in MongoDB.
4. **AI Aggressive Load Shedding**: When sanctioned load is exceeded, the system automatically checks priorities (Non-essential -> Medium -> Essential) and intelligently shuts down appliances to protect the grid.
5. **Physical Hardware Integration (ESP32)**: Built-in support for Wokwi ESP32 Simulation. Allows real-time HTTP polling and interaction between physical switches and the React dashboard via a local tunnel.

---

## 🚀 How to Run

### Step 1 — Database and API Setup
1. **Groq API**: Get a free API key from [Groq Cloud](https://console.groq.com/keys) to run the AI chatbot.
2. **OpenWeatherMap**: Get a free API key from [OpenWeatherMap](https://openweathermap.org/api).
3. **MongoDB**: Have a local MongoDB running (`mongodb://localhost:27017`) OR a cloud Atlas cluster.
4. Paste these credentials into both `.env` files:
   - `server/.env` → `OPENWEATHER_API_KEY`, `MONGO_URI`, and `GROQ_API_KEY`
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
