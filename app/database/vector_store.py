"""ChromaDB-backed vector memory used for duplicate / near-duplicate invoice detection.

This is part of Facility 3 (Knowledge Memory): in addition to the
structured SQLite tables, Brain OS keeps a semantic memory of every
invoice it has seen so the risk engine can flag likely duplicate
submissions (Facility 4: Risk Engine anomalies).

The embedding function is a deterministic, offline hashing-trick
bag-of-words vectorizer rather than a downloaded neural model. That
keeps the MVP fully self-contained and reproducible on a machine with
no network access, while still exercising a real ChromaDB collection,
real upserts, and real cosine-similarity queries.
"""

import hashlib
import math
import re
from typing import Any, Optional

import chromadb
from chromadb.api.types import Documents, Embeddings


class DeterministicHashEmbeddingFunction:
    """Offline hashing-trick embedding function conforming to Chroma's protocol."""

    DIMENSIONS = 256

    def __init__(self, dimensions: int = DIMENSIONS) -> None:
        self.dimensions = dimensions

    def __call__(self, input: Documents) -> Embeddings:  # noqa: A002 - Chroma's protocol name
        return [self._embed_one(text) for text in input]

    def embed_query(self, input: Documents) -> Embeddings:  # noqa: A002 - Chroma's protocol name
        return self(input)

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in re.findall(r"[a-z0-9]+", text.lower()):
            digest = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
            bucket = digest % self.dimensions
            sign = 1.0 if (digest // self.dimensions) % 2 == 0 else -1.0
            vector[bucket] += sign
        norm = math.sqrt(sum(v * v for v in vector))
        return [v / norm for v in vector] if norm > 0 else vector

    @staticmethod
    def name() -> str:
        return "brain_os_hash_embedding_v1"

    def get_config(self) -> dict[str, Any]:
        return {"dimensions": self.dimensions}

    @staticmethod
    def build_from_config(config: dict[str, Any]) -> "DeterministicHashEmbeddingFunction":
        return DeterministicHashEmbeddingFunction(dimensions=config.get("dimensions", DeterministicHashEmbeddingFunction.DIMENSIONS))


def _invoice_document(vendor: Optional[str], po_number: Optional[str], amount: Optional[float]) -> str:
    return f"vendor:{(vendor or '').strip().lower()} po:{(po_number or '').strip().lower()} amount:{amount if amount is not None else ''}"


class VectorMemory:
    """Thin wrapper around a persistent Chroma collection of invoice fingerprints."""

    def __init__(self, persist_path: str, collection_name: str) -> None:
        self._client = chromadb.PersistentClient(path=persist_path)
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            embedding_function=DeterministicHashEmbeddingFunction(),
            metadata={"hnsw:space": "cosine"},
        )

    def find_similar(
        self, vendor: Optional[str], po_number: Optional[str], amount: Optional[float], n_results: int = 3
    ) -> list[dict]:
        """Return the most similar previously-seen invoices, most similar first."""
        if self._collection.count() == 0:
            return []
        document = _invoice_document(vendor, po_number, amount)
        results = self._collection.query(
            query_texts=[document], n_results=min(n_results, self._collection.count())
        )
        matches: list[dict] = []
        ids = results.get("ids", [[]])[0]
        distances = results.get("distances", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        for workflow_id, distance, metadata in zip(ids, distances, metadatas):
            similarity = max(0.0, 1.0 - distance)
            matches.append({"workflow_id": workflow_id, "similarity": similarity, "metadata": metadata})
        return matches

    def remember(self, workflow_id: str, vendor: Optional[str], po_number: Optional[str], amount: Optional[float]) -> None:
        """Index this invoice so future submissions can be compared against it."""
        document = _invoice_document(vendor, po_number, amount)
        self._collection.upsert(
            ids=[workflow_id],
            documents=[document],
            metadatas=[{"vendor": vendor or "", "po_number": po_number or "", "amount": amount if amount is not None else 0.0}],
        )
