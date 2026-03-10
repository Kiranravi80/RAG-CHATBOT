from __future__ import annotations

from pathlib import Path
import hashlib

import faiss
import numpy as np


class HashEmbedder:
    def __init__(self, dim: int = 384) -> None:
        self.dim = dim

    def encode(self, texts: list[str]) -> np.ndarray:
        vectors = np.zeros((len(texts), self.dim), dtype="float32")
        for i, text in enumerate(texts):
            tokens = text.lower().split()
            if not tokens:
                continue
            for token in tokens:
                digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
                idx = int(digest[:8], 16) % self.dim
                vectors[i, idx] += 1.0
            norm = np.linalg.norm(vectors[i])
            if norm > 0:
                vectors[i] = vectors[i] / norm
        return vectors


class RagStore:
    def __init__(self) -> None:
        self.embedder = HashEmbedder()
        self.index: faiss.Index | None = None
        self.docs: list[str] = []

    def build(self, docs: list[str], extra_doc_path: str | None = None) -> None:
        merged = docs.copy()
        if extra_doc_path:
            p = Path(extra_doc_path)
            if p.exists():
                merged.extend([line.strip() for line in p.read_text(encoding="utf-8").splitlines() if line.strip()])
        if not merged:
            merged = ["No schema docs available."]
        embeddings = self.embedder.encode(merged)
        self.index = faiss.IndexFlatIP(embeddings.shape[1])
        self.index.add(embeddings)
        self.docs = merged

    def search(self, query: str, k: int = 8) -> list[str]:
        if self.index is None or not self.docs:
            return []
        q = self.embedder.encode([query])
        top_k = min(k, len(self.docs))
        _, idx = self.index.search(q, top_k)
        return [self.docs[i] for i in idx[0] if 0 <= i < len(self.docs)]
