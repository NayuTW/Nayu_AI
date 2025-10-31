import re
from typing import Dict, Any, List, Optional, Tuple
import chromadb
from src.agents.embeddings.local_embedder import LocalEmbedder

def _chunk_text(text: str, max_chars: int = 900, overlap: int = 120) -> List[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_chars:
        return [text]
    chunks = []
    i = 0
    while i < len(text):
        end = min(i + max_chars, len(text))
        boundary = max(text.rfind(". ", i, end), text.rfind("! ", i, end), text.rfind("? ", i, end))
        if boundary == -1 or boundary < i + max_chars * 0.6:
            boundary = end
        chunk = text[i:boundary].strip()
        if chunk:
            chunks.append(chunk)
        i = max(boundary - overlap, i + 1)
    return chunks

class MemoryTool:
    """
    Long-term memory using Chroma with a small local embedding model.
    - 'remember': store a fact or document (auto-chunked)
    - 'recall': retrieve top-k related memories using cosine similarity
    """
    def __init__(self, state, collection: str = "long_term", embed_model: Optional[str] = None, backend: Optional[str] = None):
        self.state = state
        self.embedder = LocalEmbedder(
            model_name=embed_model or "intfloat/e5-small-v2",
            backend=backend,
        )
        self.client = chromadb.PersistentClient(path=".chroma")
        self.col = self.client.get_or_create_collection(collection)

    @staticmethod
    def spec():
        # Add examples into description so the model understands typical calls.
        return {
            "name": "memory",
            "description": (
                "Store or retrieve long term memory using local embeddings. "
                "Use 'remember' when the user asks to store something, and 'recall' to look it up.\n"
                "Examples:\n"
                '- {"action":"remember","text":"Nayu prefers night mode","metadata":{"tag":"cli"}}\n'
                '- {"action":"recall","text":"Nayu night mode","k":3}'
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["remember", "recall"]},
                    "text": {"type": "string", "description": "Text to store or query against"},
                    "k": {"type": "number", "description": "Top-K results for recall"},
                    "doc_id": {"type": "string", "description": "Optional custom id for remember"},
                    "metadata": {"type": "object", "description": "Optional metadata dict for remember"},
                },
                "required": ["action"]
            }
        }

    async def digest_for_context(self, user_text: str) -> str:
        q = self.embedder.embed_text(user_text)
        hits = self.col.query(query_embeddings=[q], n_results=4)
        docs = hits.get("documents", [[]])[0]
        metas = hits.get("metadatas", [[]])[0]
        items = []
        for d, m in zip(docs, metas):
            tag = (m or {}).get("tag", "")
            prefix = f"[{tag}] " if tag else ""
            items.append(prefix + d[:200])
        digest = " | ".join(items[:4])
        return digest

    async def update_working_memo(self, state):
        state.scratchpad = state.scratchpad[-1000:]

    def _add_chunks(self, base_id: str, chunks: List[str], metadata: Optional[Dict[str, Any]] = None) -> int:
        safe_meta = metadata if (metadata and len(metadata) > 0) else {"tag": "general"}
        embs = self.embedder.embed_texts(chunks)
        ids = [f"{base_id}__{i}" for i in range(len(chunks))]
        metas = [dict(safe_meta) for _ in chunks]
        self.col.add(ids=ids, documents=chunks, embeddings=embs, metadatas=metas)
        return len(chunks)

    async def run(self, action: str, text: str = "", k: int = 4, doc_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if action == "remember" and text:
            base_id = doc_id or f"id_{abs(hash(text))}"
            chunks = _chunk_text(text)
            md = metadata if (metadata and len(metadata) > 0) else {"tag": "general"}
            n = self._add_chunks(base_id, chunks, metadata=md)
            summary = f"Stored {n} chunk(s) under {base_id}."
            delta = {"memory_digest": f"Remembered: {chunks[0][:200]}{'...' if len(chunks)>1 else ''}"}
            return {"summary": summary, "delta": delta}

        if action == "recall":
            if not text:
                return {"summary": "No query text provided.", "delta": {"memory_digest": ""}}
            q = self.embedder.embed_text(text)
            hits = self.col.query(query_embeddings=[q], n_results=max(1, int(k)))
            docs = hits.get("documents", [[]])[0]
            metas = hits.get("metadatas", [[]])[0]
            ids = hits.get("ids", [[]])[0]

            pairs = []
            for i, (d, m) in enumerate(zip(docs, metas)):
                tag = (m or {}).get("tag", "")
                pairs.append(f"- {ids[i]} {f'[{tag}] ' if tag else ''}{d[:300]}")
            summary = "Relevant memories:\n" + "\n".join(pairs) if pairs else "No relevant memories."
            delta = {"memory_digest": " | ".join(d[:160] for d in docs[:3])}
            return {"summary": summary[:1200], "delta": delta}

        return {"summary": "Invalid memory action/args.", "delta": {"memory_digest": ""}}
