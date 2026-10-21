import hashlib, uuid, requests
from qdrant_client import QdrantClient, models
from .config import OLLAMA_BASE_URL, OLLAMA_EMBED_MODEL, QDRANT_URL, QDRANT_API_KEY, QDRANT_COLLECTION

def _client():
    return QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=8)

def embed_text(text: str):
    try:
        r = requests.post(f"{OLLAMA_BASE_URL}/api/embed", json={"model": OLLAMA_EMBED_MODEL, "input": text}, timeout=60)
        r.raise_for_status()
        values = r.json().get("embeddings", [])
        return values[0] if values else None
    except requests.RequestException:
        try:
            r = requests.post(f"{OLLAMA_BASE_URL}/api/embeddings", json={"model": OLLAMA_EMBED_MODEL, "prompt": text}, timeout=60)
            r.raise_for_status()
            return r.json().get("embedding")
        except requests.RequestException:
            return None

def chunk_text(text: str, size: int = 900, overlap: int = 120) -> list[str]:
    text = " ".join(text.split())
    chunks, start = [], 0
    while start < len(text):
        end = min(len(text), start + size)
        chunks.append(text[start:end])
        if end == len(text): break
        start = max(end - overlap, start + 1)
    return chunks

def ingest_document(name: str, text: str) -> dict:
    chunks = chunk_text(text)
    if not chunks: return {"ok": False, "message": "No extractable text found."}
    vectors = [embed_text(chunk) for chunk in chunks]
    if any(v is None for v in vectors):
        return {"ok": False, "message": "Embedding failed. Start Ollama and pull the configured embedding model."}
    try:
        client = _client()
        try: client.get_collection(QDRANT_COLLECTION)
        except Exception:
            client.create_collection(collection_name=QDRANT_COLLECTION,
                vectors_config=models.VectorParams(size=len(vectors[0]), distance=models.Distance.COSINE))
        client.upsert(collection_name=QDRANT_COLLECTION, wait=True, points=[
            models.PointStruct(id=str(uuid.uuid4()), vector=vector,
                payload={"text": chunk, "source": name, "chunk": i,
                         "content_hash": hashlib.sha256(chunk.encode()).hexdigest(),
                         "team": "dba", "environment": "internal"})
            for i, (chunk, vector) in enumerate(zip(chunks, vectors))
        ])
        return {"ok": True, "message": f"Indexed {len(chunks)} chunks from {name}.", "chunks": len(chunks)}
    except Exception as exc:
        return {"ok": False, "message": f"Qdrant ingestion failed: {exc.__class__.__name__}."}

def retrieve(question: str, limit: int = 4) -> list[dict]:
    vector = embed_text(question)
    if not vector: return []
    try:
        result = _client().query_points(collection_name=QDRANT_COLLECTION, query=vector, limit=limit, with_payload=True)
        return [{"text": (p.payload or {}).get("text", ""), "source": (p.payload or {}).get("source", "unknown"), "score": p.score} for p in result.points]
    except Exception:
        return []
