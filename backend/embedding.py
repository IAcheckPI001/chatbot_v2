
import math
import numpy as np
from model import client

embedding_cache = {}

def get_proc_embedding(proc):
    if proc not in embedding_cache or embedding_cache[proc] is None:
        result = get_embedding(proc)
        if result is not None:
            embedding_cache[proc] = result
        return result
    return embedding_cache[proc]

def get_embedding(text: str):
    try:
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Embedding error: {e}")
        return None

def cosine(vec1, vec2):
    dot = sum(a*b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a*a for a in vec1))
    norm2 = math.sqrt(sum(b*b for b in vec2))
    
    if norm1 == 0 or norm2 == 0:
        return 0.0
    
    return dot / (norm1 * norm2)

# ===== Hàm cosine similarity =====
def cosine_similarity(vec1, vec2):
    return np.dot(vec1, vec2) / (
        np.linalg.norm(vec1) * np.linalg.norm(vec2)
    )
