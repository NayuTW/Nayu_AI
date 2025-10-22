from __future__ import annotations
import math
from typing import Iterable, List, Optional

class LocalEmbedder:
    """
    Lightweight local embedder with two backends:
    - fastembed (preferred for speed)
    - sentence-transformers (fallback)
    Returns L2-normalized vectors.
    """

    def __init__(
        self,
        model_name: str = "intfloat/e5-small-v2",
        backend: Optional[str] = None,
        device: Optional[str] = None,
    ):
        self.model_name = model_name
        self.backend = backend
        self.device = device
        self._init_backend()

    def _init_backend(self):
        self._backend = None
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
        _ = self.embed_texts(["probe"])[0]

    def _l2(self, v: List[float]) -> List[float]:
        s = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / s for x in v]

    def embed_texts(self, texts: Iterable[str]) -> List[List[float]]:
        texts = list(texts)
        if not texts:
            return []
        if self._backend == "fastembed":
            vecs = list(self._fe_model.embed(texts))
        else:
            vecs = self._st_model.encode(texts, normalize_embeddings=False, show_progress_bar=False).tolist()
        return [self._l2(v) for v in vecs]

    def embed_text(self, text: str) -> List[float]:
        return self.embed_texts([text])[0]