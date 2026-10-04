import os
import glob
from langchain_text_splitters import RecursiveCharacterTextSplitter
import chromadb
from sentence_transformers import SentenceTransformer
from pypdf import PdfReader

def ingest_documents():
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    db_dir = os.path.join(os.path.dirname(__file__), "chroma_db")
    
    # Initialize ChromaDB client
    chroma_client = chromadb.PersistentClient(path=db_dir)
    collection_name = "energy_rules"
    
    # Try to delete existing collection to start fresh
    try:
        chroma_client.delete_collection(name=collection_name)
    except:
        pass
        
    collection = chroma_client.create_collection(name=collection_name)
    
    # Initialize Embedding Model
    print("Loading embedding model...")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    
    # Read text and PDF files
    txt_files = glob.glob(os.path.join(data_dir, "*.txt"))
    pdf_files = glob.glob(os.path.join(data_dir, "*.pdf"))
    all_files = txt_files + pdf_files
    
    if not all_files:
        print("No text or PDF files found in data directory.")
        return

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        length_function=len,
    )
    
    all_chunks = []
    all_metadatas = []
    all_ids = []
    
    chunk_id = 0
    for file_path in all_files:
        filename = os.path.basename(file_path)
        print(f"Processing {filename}...")
        text = ""
        try:
            if filename.lower().endswith(".pdf"):
                pdf = PdfReader(file_path)
                for page in pdf.pages:
                    extracted = page.extract_text()
                    if extracted:
                        text += extracted + "\n"
            else:
                with open(file_path, 'r', encoding='utf-8') as f:
                    text = f.read()
        except Exception as e:
            print(f"Failed to read {filename}: {e}")
            continue
            
        chunks = text_splitter.split_text(text)
        for chunk in chunks:
            all_chunks.append(chunk)
            all_metadatas.append({"source": filename})
            all_ids.append(f"chunk_{chunk_id}")
            chunk_id += 1
            
    print(f"Total chunks generated: {len(all_chunks)}")
    
    print("Generating embeddings and storing in ChromaDB...")
    # Generate embeddings
    embeddings = model.encode(all_chunks).tolist()
    
    # Add to Chroma
    collection.add(
        documents=all_chunks,
        embeddings=embeddings,
        metadatas=all_metadatas,
        ids=all_ids
    )
    
    print("Successfully ingested documents into ChromaDB!")

if __name__ == "__main__":
    ingest_documents()
