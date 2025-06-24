from sentence_transformers import SentenceTransformer
import numpy as np

from sentence_transformers import SentenceTransformer

SentenceTransformer("all-MiniLM-L6-v2", device='cpu')  # explicitly use CPU


def chunk_text(text, max_words=100):
    words = text.split()
    return [' '.join(words[i:i+max_words]) for i in range(0, len(words), max_words)]

def get_embedding(text):
    return embedder.encode([text])[0]  # shape (384,)
