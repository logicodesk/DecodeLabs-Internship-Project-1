import os
import json

# Lazy-loaded heavy dependencies (loaded on first use)
_model = None
_np = None
_faiss = None
_PyPDF2 = None

def _load_deps():
    global _model, _np, _faiss, _PyPDF2
    if _model is None:
        import numpy as np
        from sentence_transformers import SentenceTransformer
        import faiss
        import PyPDF2 as _pdf
        _np = np
        _faiss = faiss
        _PyPDF2 = _pdf
        _model = SentenceTransformer('all-MiniLM-L6-v2')

UPLOAD_DIR = "uploads"
INDEX_DIR = "faiss_indexes"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(INDEX_DIR, exist_ok=True)

def extract_text_from_file(file_path: str) -> str:
    _load_deps()
    text = ""
    if file_path.lower().endswith(".pdf"):
        with open(file_path, "rb") as f:
            reader = _PyPDF2.PdfReader(f)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    elif file_path.lower().endswith((".txt", ".md", ".csv")):
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
    return text

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)
    return chunks

def build_index_for_session(session_id: str, file_path: str):
    _load_deps()
    text = extract_text_from_file(file_path)
    if not text.strip():
        return False
        
    chunks = chunk_text(text)
    
    # Generate embeddings
    embeddings = _model.encode(chunks)
    embeddings = _np.array(embeddings).astype("float32")
    
    # Initialize FAISS
    dimension = embeddings.shape[1]
    index = _faiss.IndexFlatL2(dimension)
    index.add(embeddings)
    
    # Save index and chunks
    index_path = os.path.join(INDEX_DIR, f"{session_id}.index")
    chunks_path = os.path.join(INDEX_DIR, f"{session_id}_chunks.json")
    
    _faiss.write_index(index, index_path)
    with open(chunks_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f)
        
    return True

def query_index(session_id: str, query: str, top_k: int = 3) -> str:
    index_path = os.path.join(INDEX_DIR, f"{session_id}.index")
    chunks_path = os.path.join(INDEX_DIR, f"{session_id}_chunks.json")
    
    if not os.path.exists(index_path) or not os.path.exists(chunks_path):
        return ""
    
    _load_deps()
    index = _faiss.read_index(index_path)
    with open(chunks_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)
        
    query_vector = _model.encode([query])
    query_vector = _np.array(query_vector).astype("float32")
    
    distances, indices = index.search(query_vector, top_k)
    
    results = []
    for idx in indices[0]:
        if idx < len(chunks) and idx != -1:
            results.append(chunks[idx])
            
    return "\n\n".join(results)

