"""
MemoryTool converted to smolagents Tool class.
Uses Chroma with local embeddings for long-term memory.
"""
import re
from typing import Dict, Any, List, Optional
import chromadb
from smolagents import Tool

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


class MemorySmolTool(Tool):
    """
    Long-term memory using Chroma with a small local embedding model.
    Stores and retrieves information using vector similarity.
    """
    name = "memory"
    description = (
        "Store or retrieve long-term memory using local embeddings. "
        "Use 'remember' action to store information, and 'recall' action to retrieve relevant memories. "
        "Examples: remember(action='remember', text='User prefers dark mode', metadata={'tag': 'preference'}) "
        "or recall(action='recall', text='user preferences', k=3)"
    )
    inputs = {
        "action": {
            "type": "string",
            "description": "Action to perform: 'remember' to store or 'recall' to retrieve"
        },
        "text": {
            "type": "string",
            "description": "Text to store (for remember) or query text (for recall)",
            "nullable": True
        },
        "k": {
            "type": "integer",
            "description": "Number of results to retrieve (for recall)",
            "nullable": True
        },
        "doc_id": {
            "type": "string",
            "description": "Optional custom document ID (for remember)",
            "nullable": True
        },
        "metadata": {
            "type": "object",
            "description": "Optional metadata dictionary (for remember)",
            "nullable": True
        }
    }
    output_type = "string"
    
    def __init__(self, collection: str = "long_term", embed_model: Optional[str] = None, backend: Optional[str] = None):
        super().__init__()
        # Use lazy loading for embedder
        self.embedder = LocalEmbedder(
            model_name=embed_model or "intfloat/e5-small-v2",
            backend=backend,
            lazy_load=True,
        )
        self.client = chromadb.PersistentClient(path=".chroma")
        self.col = self.client.get_or_create_collection(collection)
    
    def digest_for_context(self, user_text: str) -> str:
        """Get relevant memory digest for context."""
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
    
    def _add_chunks(self, base_id: str, chunks: List[str], metadata: Optional[Dict[str, Any]] = None) -> int:
        """Add chunks with batch embedding."""
        if not chunks:
            return 0
        safe_meta = metadata if (metadata and len(metadata) > 0) else {"tag": "general"}
        # Batch embed all chunks at once
        embs = self.embedder.embed_texts(chunks)
        ids = [f"{base_id}__{i}" for i in range(len(chunks))]
        metas = [dict(safe_meta) for _ in chunks]
        # Single batch insert to Chroma
        self.col.add(ids=ids, documents=chunks, embeddings=embs, metadatas=metas)
        return len(chunks)
    
    def forward(
        self,
        action: str,
        text: Optional[str] = None,
        k: int = 4,
        doc_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Execute memory action and return formatted result."""
        if action == "remember":
            if not text:
                return "Error: 'text' is required for remember action"
            
            # Use hashlib for consistent, reliable ID generation
            import hashlib
            base_id = doc_id or f"id_{hashlib.md5(text.encode()).hexdigest()[:16]}"
            chunks = _chunk_text(text)
            md = metadata if (metadata and len(metadata) > 0) else {"tag": "general"}
            n = self._add_chunks(base_id, chunks, metadata=md)
            
            first_chunk = chunks[0][:200]
            if len(chunks) > 1:
                first_chunk += "..."
            return f"Stored {n} chunk(s) under {base_id}. First chunk: {first_chunk}"
        
        elif action == "recall":
            if not text:
                return "Error: 'text' is required for recall action"
            
            q = self.embedder.embed_text(text)
            hits = self.col.query(query_embeddings=[q], n_results=k)
            docs = hits.get("documents", [[]])[0]
            metas = hits.get("metadatas", [[]])[0]
            
            if not docs:
                return f"No memories found for query: {text}"
            
            results = []
            for i, (doc, meta) in enumerate(zip(docs, metas), 1):
                tag = (meta or {}).get("tag", "general")
                results.append(f"{i}. [{tag}] {doc[:400]}")
            
            return f"Found {len(docs)} relevant memories:\n" + "\n".join(results)
        
        else:
            return f"Error: Unknown action '{action}'. Use 'remember' or 'recall'"
