"""
Image RAG system using CLIP embeddings and ChromaDB for efficient image search.
Based on the design in docs/VISION_REWORK.md
"""
from __future__ import annotations
import os
import uuid
from typing import List, Dict, Optional, Tuple

import torch
import numpy as np
from PIL import Image
import chromadb

try:
    import open_clip
except ImportError:
    open_clip = None

# Optional OCR: install rapidocr if desired
try:
    from rapidocr_onnxruntime import RapidOCR
except ImportError:
    RapidOCR = None

# add pytesseract fallback import attempt
try:
    import pytesseract
except Exception:
    pytesseract = None


def _device() -> str:
    """Get the best available device (cuda or cpu)."""
    return "cuda" if torch.cuda.is_available() else "cpu"


def _tiles(img: Image.Image, grid: Tuple[int, int] = (3, 3)) -> List[Tuple[Tuple[int, int, int, int], Image.Image]]:
    """
    Split image into a grid of tiles.
    
    Args:
        img: PIL Image to split
        grid: Tuple of (grid_width, grid_height)
        
    Returns:
        List of (bbox, tile_image) tuples where bbox is (x1, y1, x2, y2)
    """
    w, h = img.size
    gw, gh = grid
    tiles = []
    tw, th = w // gw, h // gh
    for i in range(gw):
        for j in range(gh):
            box = (i * tw, j * th, (i + 1) * tw if i < gw - 1 else w, (j + 1) * th if j < gh - 1 else h)
            tiles.append((box, img.crop(box)))
    return tiles

# helper: convert bbox to primitive dict for Chroma metadata
def _bbox_dict(bbox: Tuple[int, int, int, int]) -> Dict[str, int]:
    # Chroma requires metadata values to be primitive types.
    # Return a simple primitive representation (comma-separated string).
    x1, y1, x2, y2 = [int(v) for v in bbox]
    return f"{x1},{y1},{x2},{y2}"


class CLIPEncoder:
    """CLIP encoder for image and text embeddings."""
    
    def __init__(self, model_name: str = "ViT-B-32", pretrained: str = "laion2b_s34b_b79k"):
        """
        Initialize CLIP encoder.
        
        Args:
            model_name: CLIP model architecture
            pretrained: Pretrained weights to use
        """
        if open_clip is None:
            raise RuntimeError("open_clip_torch is not installed. pip install open_clip_torch")
        self.device = _device()
        self.model, _, self.preprocess = open_clip.create_model_and_transforms(
            model_name, pretrained=pretrained, device=self.device
        )
        self.tokenizer = open_clip.get_tokenizer(model_name)
        self.model.eval()

    @torch.inference_mode()
    def embed_image(self, image: Image.Image) -> np.ndarray:
        """
        Compute embedding for an image.
        
        Args:
            image: PIL Image
            
        Returns:
            Normalized embedding vector as numpy array
        """
        img = self.preprocess(image).unsqueeze(0).to(self.device)
        feats = self.model.encode_image(img)
        feats = feats / feats.norm(dim=-1, keepdim=True)
        return feats.detach().cpu().numpy()[0]

    @torch.inference_mode()
    def embed_text(self, text: str) -> np.ndarray:
        """
        Compute embedding for text.
        
        Args:
            text: Text string
            
        Returns:
            Normalized embedding vector as numpy array
        """
        tokens = self.tokenizer([text]).to(self.device)
        feats = self.model.encode_text(tokens)
        feats = feats / feats.norm(dim=-1, keepdim=True)
        return feats.detach().cpu().numpy()[0]


class ImageRAG:
    """
    Image RAG system for indexing and searching images using embeddings.
    """
    
    def __init__(
        self,
        chroma_client: Optional[chromadb.Client] = None,
        collection_name: str = "image_regions",
        model_name: str = "ViT-B-32",
        pretrained: str = "laion2b_s34b_b79k",
        use_ocr: bool = True,
        grid: Tuple[int, int] = (3, 3),
    ):
        """
        Initialize ImageRAG system.
        """
        self.encoder = CLIPEncoder(model_name=model_name, pretrained=pretrained)
        self.grid = grid
        self.chroma = chroma_client or chromadb.Client()
        self.col = self.chroma.get_or_create_collection(collection_name)
        self.ocr = RapidOCR() if (use_ocr and RapidOCR is not None) else None
        # track embedding dimensionality (set on first index)
        self.embedding_dim: Optional[int] = None

    def _ocr_text(self, image: Image.Image) -> str:
        """
        Extract text from image using OCR with fallbacks.
        """
        if self.ocr is not None:
            try:
                res, _ = self.ocr(np.array(image)[:, :, ::-1])  # expects BGR
                if res:
                    return " ".join([r[1] for r in res])
            except Exception:
                # fallthrough to other fallbacks
                pass

        # pytesseract fallback if available
        if pytesseract is not None:
            try:
                txt = pytesseract.image_to_string(image)
                return txt.strip()
            except Exception:
                pass

        return ""

    def index_image(self, image_path: str, action_id: Optional[str] = None) -> Dict:
        """
        Index an image by computing embeddings and OCR for the whole image and tiles.
        """
        assert os.path.exists(image_path), f"Image not found: {image_path}"
        img = Image.open(image_path).convert("RGB")
        image_id = str(uuid.uuid4())

        # Whole-image embedding + OCR
        whole_emb = self.encoder.embed_image(img).tolist()
        whole_ocr = self._ocr_text(img)

        # set embedding dim if unset
        try:
            self.embedding_dim = len(whole_emb)
        except Exception:
            self.embedding_dim = None

        ids = []
        embs = []
        metadatas = []
        documents = []

        # Whole image as one document
        ids.append(f"{image_id}:whole")
        embs.append(whole_emb)
        metadatas.append({
            "image_id": image_id,
            "image_path": image_path,
            "bbox": _bbox_dict((0, 0, img.width, img.height)),
            "type": "whole",
            "action_id": action_id or "",
        })
        documents.append(whole_ocr or "")

        # Tiles
        for idx, (bbox, tile) in enumerate(_tiles(img, self.grid)):
            tile_emb = self.encoder.embed_image(tile).tolist()
            tile_ocr = self._ocr_text(tile)
            ids.append(f"{image_id}:tile:{idx}")
            embs.append(tile_emb)
            metadatas.append({
                "image_id": image_id,
                "image_path": image_path,
                "bbox": _bbox_dict(bbox),
                "type": "tile",
                "tile_index": idx,
                "action_id": action_id or "",
            })
            documents.append(tile_ocr or "")

        # debug: print indexing summary
        try:
            print(f"[ImageRAG] Adding {len(ids)} regions for image {image_id} (emb_dim={self.embedding_dim})")
        except Exception:
            pass

        self.col.add(ids=ids, embeddings=embs, metadatas=metadatas, documents=documents)
        return {"image_id": image_id, "regions_indexed": len(ids), "path": image_path}

    def search(
        self,
        question: str,
        image_id: Optional[str] = None,
        k: int = 6,
        where: Optional[Dict] = None,
    ) -> Dict:
        """
        Search for image regions matching a text query.
        """
        qvec = self.encoder.embed_text(question).tolist()

        # debug: check embedding dims
        if self.embedding_dim is not None and len(qvec) != self.embedding_dim:
            return {
                "question": question,
                "summary": None,
                "evidence": [],
                "error": (
                    f"Embedding-dimension mismatch: query vector dim={len(qvec)} "
                    f"but indexed embeddings dim={self.embedding_dim}. "
                    "Reindex images with the same CLIP model or use a compatible model."
                )
            }

        filt = where.copy() if where else {}
        if image_id:
            filt["image_id"] = image_id

        try:
            results = self.col.query(
                query_embeddings=[qvec],
                n_results=k,
                where=filt if filt else None,
            )
        except Exception as e:
            return {
                "question": question,
                "summary": None,
                "evidence": [],
                "error": f"Chroma query failed: {e}"
            }

        hits = []
        # defensive access to result structure
        try:
            ids_list = results.get("ids", [[]])[0]
            dists = results.get("distances", [[]])[0]
            metas = results.get("metadatas", [[]])[0]
            docs = results.get("documents", [[]])[0]
        except Exception:
            ids_list = results["ids"][0] if "ids" in results else []
            dists = results.get("distances", [[]])[0] if "distances" in results else [None] * len(ids_list)
            metas = results.get("metadatas", [[]])[0] if "metadatas" in results else [None] * len(ids_list)
            docs = results.get("documents", [[]])[0] if "documents" in results else ["" for _ in ids_list]

        for i in range(len(ids_list)):
            hits.append({
                "id": ids_list[i],
                "score": float(dists[i]) if dists and dists[i] is not None else None,
                "metadata": metas[i],
                "ocr_text": docs[i],
            })
        summary = self._summarize_evidence(question, hits)
        return {"question": question, "summary": summary, "evidence": hits}

    def _summarize_evidence(self, question: str, hits: List[Dict]) -> str:
        """
        Create a compact summary of search results.
        
        Args:
            question: Original query
            hits: List of search results
            
        Returns:
            Summary string
        """
        # Heuristic compact summary for your main LLM; you can route this through your local LLM if desired.
        texts = [h.get("ocr_text", "") for h in hits if h.get("ocr_text")]
        texts = [t.strip() for t in texts if t.strip()]
        if not texts:
            return f"No strong OCR evidence found; {len(hits)} visual regions retrieved for: {question}"
        uniq = []
        seen = set()
        for t in texts:
            if t not in seen:
                uniq.append(t)
                seen.add(t)
        joined = " | ".join(uniq[:5])
        return f"Likely relevant on-screen text: {joined}"

    def compare_images(self, image_path_a: str, image_path_b: str, grid: Optional[Tuple[int, int]] = None) -> Dict:
        """
        Compare two images using OCR and embeddings.
        
        Args:
            image_path_a: Path to first image
            image_path_b: Path to second image
            grid: Optional grid size (defaults to self.grid)
            
        Returns:
            Dict with added_text and removed_text lists
        """
        # Simple diff using embeddings + OCR; you can evolve to SSIM/perceptual metrics.
        img_a = Image.open(image_path_a).convert("RGB")
        img_b = Image.open(image_path_b).convert("RGB")
        ocr_a = self._ocr_text(img_a)
        ocr_b = self._ocr_text(img_b)
        added = [t for t in ocr_b.split() if t not in set(ocr_a.split())]
        removed = [t for t in ocr_a.split() if t not in set(ocr_b.split())]
        return {"added_text": added[:50], "removed_text": removed[:50]}

    def find_ui(self, query: str, k: int = 5, prototype_collection: str = "ui_prototypes") -> Dict:
        """
        Find UI elements matching a query from a library of prototypes.
        
        Args:
            query: Text description of UI element to find
            k: Number of matches to return
            prototype_collection: Name of collection containing UI prototypes
            
        Returns:
            Dict with matches list containing prototype info, bbox, and score
        """
        try:
            proto_col = self.chroma.get_collection(prototype_collection)
        except Exception:
            return {"matches": [], "message": f"UI prototype collection '{prototype_collection}' not found"}
        
        qvec = self.encoder.embed_text(query).tolist()
        results = proto_col.query(
            query_embeddings=[qvec],
            n_results=k,
        )
        
        matches = []
        for i in range(len(results["ids"][0])):
            matches.append({
                "prototype_id": results["ids"][0][i],
                "score": float(results["distances"][0][i]) if "distances" in results else None,
                "metadata": results["metadatas"][0][i],
                "label": results["documents"][0][i],
            })
        
        return {"matches": matches}

    def add_ui_prototype(
        self,
        image_path: str,
        label: str,
        bbox: Optional[Tuple[int, int, int, int]] = None,
        prototype_collection: str = "ui_prototypes"
    ) -> Dict:
        """
        Add a UI element to the prototype library.
        
        Args:
            image_path: Path to image containing UI element
            label: Label/description of the UI element
            bbox: Optional bounding box (x1, y1, x2, y2) to crop element
            prototype_collection: Name of collection to store prototypes
            
        Returns:
            Dict with prototype_id
        """
        img = Image.open(image_path).convert("RGB")
        if bbox:
            img = img.crop(bbox)
        
        emb = self.encoder.embed_image(img).tolist()
        prototype_id = str(uuid.uuid4())
        
        proto_col = self.chroma.get_or_create_collection(prototype_collection)
        proto_col.add(
            ids=[prototype_id],
            embeddings=[emb],
            metadatas=[{
                "image_path": image_path,
                "bbox": _bbox_dict(bbox if bbox else (0, 0, img.width, img.height)),
                "label": label,
            }],
            documents=[label]
        )
        
        return {"prototype_id": prototype_id, "label": label}
