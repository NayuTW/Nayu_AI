from __future__ import annotations
import math
from typing import Iterable, List, Optional
from functools import lru_cache

class LocalEmbedder:
    """
    Lightweight local embedder with two backends:
    - fastembed (preferred for speed)
    - sentence-transformers (fallback)
    Returns L2-normalized vectors.
    Supports lazy initialization and caching.
    """

    def __init__(
        self,
        model_name: str = "intfloat/e5-small-v2",
        backend: Optional[str] = None,
        device: Optional[str] = None,
        lazy_load: bool = True,
    ):
        self.model_name = model_name
        self.backend = backend
        self.device = device
        self._backend = None
        self._fe_model = None
        self._st_model = None
        if not lazy_load:
            self._init_backend()

    def _init_backend(self):
        """Initialize the embedding backend (lazy loading)."""
        if self._backend is not None:
            return  # Already initialized
        
        if self.backend in (None, "fastembed"):
            try:
                from fastembed import TextEmbedding
                self._fe_model = TextEmbedding(model_name=self.model_name)
                self._backend = "fastembed"
            except Exception:
                if self.backend == "fastembed":
                    raise
                self._fe_model = None
        if self._backend is None:
            from sentence_transformers import SentenceTransformer
            self._st_model = SentenceTransformer(self.model_name, device=self.device or "cpu")
            self._backend = "sentence-transformers"
        # Warm up the model with a probe
        _ = self._embed_texts_internal(["probe"])[0]

    def _l2(self, v: List[float]) -> List[float]:
        s = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / s for x in v]

    def _embed_texts_internal(self, texts: List[str]) -> List[List[float]]:
        """Internal method for embedding without caching."""
        if not texts:
            return []
        if self._backend == "fastembed":
            vecs = list(self._fe_model.embed(texts))
        else:
            vecs = self._st_model.encode(texts, normalize_embeddings=False, show_progress_bar=False).tolist()
        return [self._l2(v) for v in vecs]

    def embed_texts(self, texts: Iterable[str]) -> List[List[float]]:
        """Embed multiple texts. Initializes model on first call."""
        self._init_backend()
        texts_list = list(texts)
        return self._embed_texts_internal(texts_list)

    @lru_cache(maxsize=128)
    def embed_text_cached(self, text: str) -> tuple:
        """Embed single text with caching. Returns tuple for hashability."""
        self._init_backend()
        result = self._embed_texts_internal([text])[0]
        return tuple(result)

    def embed_text(self, text: str) -> List[float]:
        """
        Embed single text and return as list.
        Uses internal caching for improved performance on repeated queries.
        """
        return list(self.embed_text_cached(text))