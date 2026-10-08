import os
from pymongo import MongoClient
from dotenv import load_dotenv

# Use local sentence-transformers since your local PC has enough RAM!
from sentence_transformers import SentenceTransformer

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")

def main():
    print("Loading local embedding model...")
    model = SentenceTransformer('all-MiniLM-L6-v2')

    print("Connecting to MongoDB Atlas...")
    client = MongoClient(MONGO_URI)
    db = client["energy_optimizer"]
    collection = db["energy_rules"]
    
    # Clear existing if any
    collection.delete_many({})
    
    # Process all .txt files in the data folder
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    txt_files = [f for f in os.listdir(data_dir) if f.endswith(".txt")]
    
    for filename in txt_files:
        file_path = os.path.join(data_dir, filename)
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Split into chunks by double newline
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        
        print(f"Processing {filename}: Found {len(paragraphs)} paragraphs.")
        
        for i, p in enumerate(paragraphs):
            # Generate vector locally
            emb = model.encode(p).tolist()
            
            doc = {
                "text": p,
                "embedding": emb,
                "source": filename,
                "chunk_id": i
            }
            collection.insert_one(doc)
            print(f" -> Inserted chunk {i+1}/{len(paragraphs)} for {filename} successfully!")
            
    print("✅ All TXT documents successfully embedded and pushed to Cloud Vector Search!")

if __name__ == "__main__":
    main()
