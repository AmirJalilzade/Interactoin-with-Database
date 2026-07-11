# # embedding_service.py
# import requests
# from typing import List

# class EmbeddingService:
#     """
#     Calls a vLLM-served BGE-M3 model via its OpenAI‑compatible /embeddings endpoint.
#     Use this anywhere you need embeddings (ingestion, retrieval, etc.).
#     """
#     def __init__(self, base_url: str, api_key: str = "not-needed", model: str = "bge-m3"):
#         # base_url should point to your vLLM server, e.g., "http://localhost:8000/v1"
#         self.base_url = base_url.rstrip("/")
#         self.api_key = api_key
#         self.model = model
#         self.dim = 1024   # BGE-M3 dense dimension

#     def _call_api(self, texts: List[str]) -> List[List[float]]:
#         """Send texts to the /embeddings endpoint and return a list of vectors."""
#         if not texts:
#             return []

#         payload = {
#             "input": texts,
#             "model": self.model,
#         }
#         headers = {
#             "Authorization": f"Bearer {self.api_key}",
#             "Content-Type": "application/json",
#         }
#         resp = requests.post(
#             f"{self.base_url}/embeddings",
#             json=payload,
#             headers=headers,
#         )
#         resp.raise_for_status()
#         data = resp.json()

#         # OpenAI-compatible response: {"data": [{"embedding": [...], "index": 0}, ...]}
#         # Sort by index to preserve order.
#         embeddings = [None] * len(texts)
#         for item in data["data"]:
#             embeddings[item["index"]] = item["embedding"]
#         return embeddings

#     def embed_documents(self, texts: List[str]) -> List[List[float]]:
#         """Embed a list of documents, returning a list of vectors."""
#         return self._call_api(texts)

#     def embed_query(self, text: str) -> List[float]:
#         """Embed a single query string."""
#         return self.embed_documents([text])[0]


# embedding_service.py
import requests
from typing import List
import math
from config.settings import settings

class EmbeddingService:
    """
    Calls a vLLM-served BGE-M3 model via its OpenAI‑compatible /embeddings endpoint.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str = "not-needed",
        model: str = "bge-m3",
        timeout: int = 30,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.dim = 1024  # BGE-M3 dense dimension

    def _call_api(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        payload = {
            "input": texts,
            "model": self.model,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        resp = requests.post(
            f"{self.base_url}",
            json=payload,
            headers=headers,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()

        if "data" not in data:
            raise RuntimeError(f"Unexpected response: {data}")

        embeddings = [None] * len(texts)
        for item in data["data"]:
            vec = item["embedding"]
            if len(vec) != self.dim:
                raise ValueError(
                    f"Expected embedding dim {self.dim}, got {len(vec)}"
                )
            embeddings[item["index"]] = vec

        return embeddings

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self._call_api(texts)

    def embed_query(self, text: str) -> List[float]:
        return self.embed_documents([text])[0]


# -----------------------------
# ✅ Simple runtime test
# -----------------------------
if __name__ == "__main__":
    def cosine_similarity(a, b):
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(y * y for y in b))
        return dot / (na * nb)

    service = EmbeddingService(
        base_url=settings.embedding_base_url,  # change if needed
        model=settings.embedding_model,
    )

    print("🔍 Testing embedding service connection...")

    texts = [
        "The cat sits on the mat.",
        "A cat is sitting on a mat.",
        "I love programming."
    ]

    embeddings = service.embed_documents(texts)

    print(f"✅ Received {len(embeddings)} embeddings")
    print(f"✅ Embedding dimension: {len(embeddings[0])}")

    sim_0_1 = cosine_similarity(embeddings[0], embeddings[1])
    sim_0_2 = cosine_similarity(embeddings[0], embeddings[2])

    print(f"Similarity (0 vs 1): {sim_0_1:.4f}  ← should be HIGH")
    print(f"Similarity (0 vs 2): {sim_0_2:.4f}  ← should be LOW")

    print("✅ Embedding service is working correctly.")
