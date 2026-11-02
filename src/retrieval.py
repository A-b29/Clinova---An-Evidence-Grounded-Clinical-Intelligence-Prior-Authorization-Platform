"""Policy embeddings and vector search."""
import logging
from functools import lru_cache

import numpy as np

from .schemas import PolicyChunk, RetrievedChunk

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
BACKENDS = ("minilm", "tfidf")
log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _minilm():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(MODEL_NAME, device="cpu")


def _make_encoder(backend: str, corpus: list[str]):
    """Return (backend_used, encode_fn). encode_fn maps texts -> L2-normalized row vectors."""
    if backend not in BACKENDS:
        raise ValueError(f"unknown embedding backend {backend!r}; choose from {BACKENDS}")
    if backend == "minilm":
        try:
            model = _minilm()
            return "minilm", lambda texts: model.encode(texts, normalize_embeddings=True)
        except Exception as e:  # package missing, no network and no cached weights, etc.
            log.warning("MiniLM unavailable (%s); falling back to TF-IDF", e)
    from sklearn.feature_extraction.text import TfidfVectorizer
    vec = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, stop_words="english").fit(corpus)
    return "tfidf", lambda texts: vec.transform(texts).toarray()  # rows are L2-normalized by default


class PolicyIndex:
    """In-memory vector index over policy chunks.

    contextual_headers prepends "document title | section" to each chunk before
    embedding, so a passage like "imaging of the affected joint" still carries
    which procedure's policy it belongs to.
    """
    # ponytail: brute-force cosine over a numpy matrix; move to FAISS / pgvector past ~100k chunks.

    def __init__(self, chunks: list[PolicyChunk], backend: str = "minilm", contextual_headers: bool = True):
        self.chunks = chunks
        texts = [f"{c.title} | {c.section} | {c.text}" if contextual_headers else c.text for c in chunks]
        self.backend, self._encode = _make_encoder(backend, texts)
        self.matrix = np.asarray(self._encode(texts))

    def search(self, query: str, k: int = 3, procedure_code: str | None = None) -> list[RetrievedChunk]:
        """Top-k chunks by cosine similarity.

        If procedure_code matches a policy's 'Applies to procedure codes', search only that
        policy plus general (code-less) documents; unknown or missing codes search everything.
        """
        scores = self.matrix @ np.asarray(self._encode([query]))[0]
        routed = procedure_code and any(procedure_code in c.procedure_codes for c in self.chunks)
        allowed = [i for i, c in enumerate(self.chunks)
                   if not routed or not c.procedure_codes or procedure_code in c.procedure_codes]
        top = sorted(allowed, key=lambda i: -scores[i])[:k]
        return [RetrievedChunk(**self.chunks[i].model_dump(), score=round(float(scores[i]), 3)) for i in top]
