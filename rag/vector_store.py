import json
import logging
import os
from typing import List, Dict, Any, Optional
import numpy as np
from google import genai

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

class HealthVectorStore:
    """
    Vector store that indexes scraped health content chunks with their metadata
    and performs trust-weighted semantic retrieval.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        data_path: str = "output/scraped_data.json",
        cache_path: str = "output/embeddings.json",
        embedding_model: str = "gemini-embedding-2"
    ):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is required to initialize HealthVectorStore.")
        
        self.client = genai.Client(api_key=self.api_key)
        self.data_path = data_path
        self.cache_path = cache_path
        self.embedding_model = embedding_model
        
        self.chunks: List[Dict[str, Any]] = []
        self.embeddings: Optional[np.ndarray] = None
        
        self._load_or_build_index()

    def _load_or_build_index(self):
        """Loads cached embeddings if valid, or extracts and embeds chunks."""
        if not os.path.exists(self.data_path):
            raise FileNotFoundError(f"Scraped data file not found at '{self.data_path}'. Run main.py first.")

        with open(self.data_path, "r", encoding="utf-8") as f:
            raw_sources = json.load(f)

        extracted_chunks: List[Dict[str, Any]] = []
        for s_idx, source in enumerate(raw_sources):
            source_url = source.get("source_url", "")
            source_type = source.get("source_type", "")
            author = source.get("author", "Unknown")
            published_date = source.get("published_date", "")
            trust_score = float(source.get("trust_score", 0.0) or 0.0)
            topic_tags = source.get("topic_tags", [])
            content_chunks = source.get("content_chunks", [])

            for c_idx, chunk_text in enumerate(content_chunks):
                if chunk_text.strip():
                    extracted_chunks.append({
                        "chunk_id": f"{source_type}_{s_idx}_{c_idx}",
                        "text": chunk_text.strip(),
                        "source_url": source_url,
                        "source_type": source_type,
                        "author": author,
                        "published_date": published_date,
                        "trust_score": trust_score,
                        "topic_tags": topic_tags
                    })

        self.chunks = extracted_chunks
        logging.info(f"Loaded {len(self.chunks)} content chunks across {len(raw_sources)} sources.")

        # Check if valid cached embeddings exist
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    cached_data = json.load(f)
                
                # Check if cache matches current chunks length and chunk_ids
                if len(cached_data) == len(self.chunks) and all(
                    c["chunk_id"] == self.chunks[i]["chunk_id"] for i, c in enumerate(cached_data)
                ):
                    self.embeddings = np.array([c["embedding"] for c in cached_data], dtype=np.float32)
                    logging.info(f"Loaded {len(self.embeddings)} cached chunk embeddings from {self.cache_path}.")
                    return
            except Exception as e:
                logging.warning(f"Could not load cache ({e}), re-embedding all chunks...")

        # Generate fresh embeddings
        logging.info(f"Generating embeddings for {len(self.chunks)} chunks using {self.embedding_model}...")
        embeddings_list = []
        cache_records = []

        for i, chunk in enumerate(self.chunks):
            try:
                res = self.client.models.embed_content(
                    model=self.embedding_model,
                    contents=chunk["text"]
                )
                emb = res.embeddings[0].values
                embeddings_list.append(emb)
                cache_records.append({
                    "chunk_id": chunk["chunk_id"],
                    "embedding": emb
                })
            except Exception as e:
                logging.error(f"Error embedding chunk {chunk['chunk_id']}: {e}")
                # Zero fallback vector with 3072 dims
                zero_vec = [0.0] * 3072
                embeddings_list.append(zero_vec)
                cache_records.append({
                    "chunk_id": chunk["chunk_id"],
                    "embedding": zero_vec
                })

        self.embeddings = np.array(embeddings_list, dtype=np.float32)

        # Save to cache
        os.makedirs(os.path.dirname(self.cache_path) or ".", exist_ok=True)
        with open(self.cache_path, "w", encoding="utf-8") as f:
            json.dump(cache_records, f)
        logging.info(f"Saved {len(cache_records)} embeddings to cache at {self.cache_path}.")

    def search(
        self,
        query: str,
        top_k: int = 4,
        min_trust_score: float = 0.0,
        trust_weight: float = 0.30
    ) -> List[Dict[str, Any]]:
        """
        Retrieves top_k chunks for a query using Trust-Weighted Hybrid Ranking.

        Composite Score = (1 - trust_weight) * CosineSimilarity + trust_weight * TrustScore
        """
        if not query.strip() or self.embeddings is None or len(self.chunks) == 0:
            return []

        # 1. Embed user query
        res = self.client.models.embed_content(
            model=self.embedding_model,
            contents=query.strip()
        )
        q_emb = np.array(res.embeddings[0].values, dtype=np.float32)

        # 2. Compute Cosine Similarities
        # norm(q) and norm(docs)
        q_norm = np.linalg.norm(q_emb)
        if q_norm == 0:
            return []
        
        doc_norms = np.linalg.norm(self.embeddings, axis=1)
        doc_norms[doc_norms == 0] = 1e-10
        cosine_sims = np.dot(self.embeddings, q_emb) / (doc_norms * q_norm)

        # Normalize cosine similarities to [0, 1] range for fair weighting
        # Cosine sims for modern embeddings are typically in [0.2, 0.9]
        norm_cosine = np.clip(cosine_sims, 0.0, 1.0)

        # 3. Filter by min_trust_score and compute composite scores
        results = []
        for idx, chunk in enumerate(self.chunks):
            trust = chunk["trust_score"]
            if trust < min_trust_score:
                continue

            sim = float(norm_cosine[idx])
            composite_score = float((1.0 - trust_weight) * sim + trust_weight * trust)

            results.append({
                **chunk,
                "similarity": round(sim, 4),
                "composite_score": round(composite_score, 4)
            })

        # 4. Sort by composite_score descending
        results.sort(key=lambda x: x["composite_score"], reverse=True)
        return results[:top_k]

