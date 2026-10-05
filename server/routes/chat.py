import os
from flask import Blueprint, request, jsonify, current_app, g
from groq import Groq
from bson import ObjectId
from datetime import date, datetime
from routes.middleware import protect
import chromadb
from sentence_transformers import SentenceTransformer
import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from pypdf import PdfReader
import io

def scrape_official_info(query):
    try:
        # Determine which ESCOM the query is for
        query_lower = query.lower()
        if "bescom" in query_lower:
            search_suffix = "Karnataka BESCOM"
        elif "mescom" in query_lower:
            search_suffix = "Karnataka MESCOM"
        elif "gescom" in query_lower:
            search_suffix = "Karnataka GESCOM"
        elif "cesc" in query_lower:
            search_suffix = "Karnataka CESC Mysore"
        else:
            search_suffix = "Karnataka HESCOM"
            
        search_query = f"{query} {search_suffix}"
        search_results = DDGS().text(search_query, max_results=1)
        if not search_results:
            return None, None
            
        target_url = search_results[0]['href']
            
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(target_url, headers=headers, timeout=5)
        
        text_content = ""
        if 'application/pdf' in response.headers.get('Content-Type', '') or target_url.lower().endswith('.pdf'):
            pdf = PdfReader(io.BytesIO(response.content))
            for page in pdf.pages[:3]:
                text_content += page.extract_text() + "\n"
        else:
            soup = BeautifulSoup(response.text, 'html.parser')
            text_content = soup.get_text(separator=' ', strip=True)
            
        return text_content[:2000], target_url
    except Exception as e:
        print(f"[WARN] Scraping failed: {e}")
        return None, None

# ── Initialize RAG models globally ──────────────────────────────────────────
try:
    print("[INFO] Loading RAG resources for chatbot...")
    _db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "chroma_db")
    _chroma_client = chromadb.PersistentClient(path=_db_path)
    _collection = _chroma_client.get_collection(name="energy_rules")
    _embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    print("[OK] RAG resources loaded successfully.")
except Exception as e:
    print(f"[WARN] Failed to load RAG resources: {e}")
    _embedding_model = None
    _collection = None

chat_bp = Blueprint("chat", __name__)

@chat_bp.route("", methods=["POST"])
@chat_bp.route("/", methods=["POST"])
@protect
def handle_chat():
    data = request.get_json()
    message = data.get("message")
    history = data.get("history", [])

    if not message:
        return jsonify({"message": "Message is required"}), 400

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return jsonify({"message": "Groq API key not configured"}), 500

    client = Groq(api_key=api_key)

    try:
        db = current_app.config["DB"]
        uid = ObjectId(g.user_id)
        user = db.users.find_one({"_id": uid})

        # Gather ALL appliances to find historical breakdowns
        appliances_raw = list(db.appliances.find({"userId": uid}))
        
        # Get unique latest appliances for the header
        unique_appliances = {}
        for a in appliances_raw:
            name = a.get("name")
            if not name: continue
            if name not in unique_appliances:
                unique_appliances[name] = a
            else:
                ca = a.get("createdAt")
                curr_ca = unique_appliances[name].get("createdAt")
                if ca and curr_ca and str(ca) > str(curr_ca):
                    unique_appliances[name] = a
                    
        appliances = list(unique_appliances.values())
        active_appliances = [app for app in appliances if app.get("status", False)]
        logs = list(db.energylogs.find({"userId": uid}).sort("date", -1).limit(7))

        # ── Build system prompt ──────────────────────────────────────────────
        system_prompt = (
            "You are EnergyBot, an AI assistant for an AI-Powered Energy Optimizer app.\n"
            "You are helpful, concise, and friendly. Answer in 2-3 sentences max. Use ₹ for costs.\n"
            "RULES:\n"
            "A. Relevant Question & Info Available: Answer using the KNOWLEDGE BASE provided below. If the answer involves an actionable step, provide a direct clickable markdown link. If you use the LIVE WEB DATA, cite the source URL. Ignore obvious junk/unreliable info from the web data.\n"
            "B. Relevant Question & Info Missing: If the exact specific information is unavailable in both the web data and local database, politely state that the information could not be found. Do not classify it as off-topic.\n"
            "C. Unrelated Question: If the user asks anything completely unrelated to energy or Karnataka schemes (e.g. colors, coding, general trivia), politely explain that the chatbot is designed for home electricity consumption, billing, tariffs, energy-saving recommendations, and Karnataka government schemes (Gruha Jyothi, Yuva Nidhi, etc). It supports all Karnataka ESCOMs including BESCOM, HESCOM, MESCOM, GESCOM, and CESC.\n"
            "CRITICAL RULE: Never invent tariff rates or claim that an older tariff is current.\n\n"
            f"USER PROFILE:\n"
            f"- Name: {user.get('name', 'User')}\n"
            f"- City: {user.get('city', 'Unknown')}\n"
            f"- Sanctioned Load: {user.get('sanctionedLoad', 4000)}W\n"
            f"- Tariff Rate: ₹{user.get('tariffRate', 5.80)}/unit\n\n"
            "ALL REGISTERED APPLIANCES IN THIS SYSTEM:\n"
        )

        if appliances:
            for app in appliances:
                status = "ON (running now)" if app.get("status", False) else "OFF"
                system_prompt += f"- {app['name']}: {app.get('power', 0)}W | {status} | Priority: {app.get('priority', 'Medium')}\n"
        else:
            system_prompt += "- No appliances registered yet\n"

        system_prompt += "\nCURRENTLY ACTIVE: "
        if active_appliances:
            system_prompt += ", ".join([f"{a['name']} ({a.get('power', 0)}W)" for a in active_appliances]) + "\n"
        else:
            system_prompt += "None\n"

        system_prompt += "\nLAST 7 DAYS ENERGY LOG:\n"
        if logs:
            for log in logs:
                cost = log.get("costPerUnit", 5.80) * log["unitsConsumed"]
                
                breakdown_str = ""
                if "breakdown" in log and isinstance(log["breakdown"], dict):
                    sorted_b = sorted(log["breakdown"].items(), key=lambda x: x[1], reverse=True)
                    top_2 = [f"{k} ({v:.1f} kWh)" for k, v in sorted_b[:2] if v > 0]
                    if top_2:
                        breakdown_str = " | Mainly caused by: " + ", ".join(top_2)
                        
                system_prompt += f"- {log['date']}: {log['unitsConsumed']:.2f} kWh (₹{cost:.2f}){breakdown_str}\n"
        else:
            system_prompt += "- No logs available\n"

        # ── Web Scraping Retrieval ───────────────────────────────────────────
        print("\n[DEBUG] --- WEB SCRAPING ---")
        scraped_text, source_url = scrape_official_info(message)
        if scraped_text:
            print(f"[DEBUG] Scraped Source: {source_url}")
        else:
            print("[DEBUG] No web results found or scraping failed.")
        print("[DEBUG] -----------------------------\n")

        # ── RAG Retrieval ────────────────────────────────────────────────────
        retrieved_context = ""
        if _embedding_model and _collection:
            try:
                query_embedding = _embedding_model.encode([message]).tolist()
                results = _collection.query(
                    query_embeddings=query_embedding,
                    n_results=10
                )
                if results['documents'] and results['documents'][0]:
                    retrieved_context = "\n".join(results['documents'][0])
                
                print("\n[DEBUG] --- RAG RETRIEVAL ---")
                print(f"[DEBUG] User Query: {message}")
                print(f"[DEBUG] Retrieved Document Names: {results['metadatas'][0]}")
                if 'distances' in results and results['distances']:
                    print(f"[DEBUG] Similarity Scores (distances): {results['distances'][0]}")
                print(f"[DEBUG] Retrieved Text Chunks: {results['documents'][0]}")
                print("[DEBUG] -----------------------------\n")
            except Exception as e:
                print(f"RAG Retrieval Error: {e}")

        if scraped_text or retrieved_context:
            system_prompt += "\n\nOFFICIAL KNOWLEDGE BASE:\n"
            if scraped_text:
                system_prompt += f"--- LIVE WEB DATA (Source: {source_url}) ---\n{scraped_text}\n\n"
            if retrieved_context:
                system_prompt += f"--- LOCAL DATABASE (2023 Order) ---\n{retrieved_context}\n"

        print("\n[DEBUG] Final Context sent to Groq:\n")
        print(system_prompt)
        print("[DEBUG] -----------------------------\n")

        # ── Build messages list ──────────────────────────────────────────────
        messages = [{"role": "system", "content": system_prompt}]

        for msg in history:
            role = "assistant" if msg["role"] == "bot" else "user"
            messages.append({"role": role, "content": msg["content"]})

        messages.append({"role": "user", "content": message})

        # ── Call Groq API ────────────────────────────────────────────────────
        response = client.chat.completions.create(
            model="qwen/qwen3.8-27b",
            messages=messages,
            max_tokens=300,
            temperature=0.7,
        )

        reply = response.choices[0].message.content
        return jsonify({"reply": reply}), 200

    except Exception as e:
        import traceback
        traceback.print_exc()

        err_str = str(e).lower()
        if "rate" in err_str or "429" in err_str:
            return jsonify({"reply": "I'm receiving too many requests. Please wait a moment and try again!"}), 200

        print(f"Chatbot error: {e}")
        return jsonify({"message": "Failed to process chat"}), 500
