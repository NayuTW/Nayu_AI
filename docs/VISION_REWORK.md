## The goal
- The goal of this PR is to allow the main text-only agent “see” images faster and more efficiently without switching the main agent to a VLM or sacrificing 16k context/low-latency GPU-only inference.
- To do this the current Vision tool must be replaced.

## Design: Image Embedding + Agentic RAG flow
- Indexing step (on every new screenshot/image):
- Tile or grid-crop the image (e.g., 3x3 or 4x4).
- Compute an embedding for each tile and the whole image.
- Run OCR; attach OCR text per tile and globally.
- Run a tiny tagger for labels.
- Store in Chroma with metadata: image_id, action_id, timestamp, bbox, ocr_text, tags.

## Query step (what the main agent calls):
- `ImageRAGTool.search(question[, image_id or image_path, k]) ->`
- Embed the question using the text encoder (CLIP text).
- Retrieve top-k tiles (and/or across the global corpus).
- Return ranked evidence with bboxes, OCR snippets, and similarity scores.
- If confidence is high, return a structured summary to the main agent (no VLM calls).
- If confidence is low or the question demands fine-grained reasoning, escalate:
  - Run a small VLM ONLY on the top-1 or top-2 crops.
  - Return the short answer + evidence. This confines the VLM latency and VRAM usage.
  
## For desktop automation:
- Add ImageRAGTool.find_ui(target_label_or_icon) that returns bbox + confidence via embedding match to a library of known UI assets (pre-embedded).
- Add find_diff(image_a, image_b) using embedding + OCR diffs.

## Proposed tool API
- `image_index(image_path: str, action_id: Optional[str]) -> {image_id, regions_indexed}`
- `image_search(question: str, image_id: Optional[str], k: int=6) -> {summary, evidence: [region]}`
- `image_find_ui(query: str, k: int=5) -> {matches: [{prototype, bbox, score}]}`
- `image_compare(image_a: str, image_b: str) -> {added_text, removed_text, changed_regions}`

## Skeleton:
```python
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

# Optional OCR: install paddleocr or rapidocr if desired
try:
    from rapidocr_onnxruntime import RapidOCR
except ImportError:
    RapidOCR = None


def _device() -> str:
    return "cuda" if torch.cuda.is_available() else "cpu"


def _tiles(img: Image.Image, grid: Tuple[int, int] = (3, 3)) -> List[Tuple[Tuple[int, int, int, int], Image.Image]]:
    w, h = img.size
    gw, gh = grid
    tiles = []
    tw, th = w // gw, h // gh
    for i in range(gw):
        for j in range(gh):
            box = (i * tw, j * th, (i + 1) * tw if i < gw - 1 else w, (j + 1) * th if j < gh - 1 else h)
            tiles.append((box, img.crop(box)))
    return tiles


class CLIPEncoder:
    def __init__(self, model_name: str = "ViT-B-32", pretrained: str = "laion2b_s34b_b79k"):
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
        img = self.preprocess(image).unsqueeze(0).to(self.device)
        feats = self.model.encode_image(img)
        feats = feats / feats.norm(dim=-1, keepdim=True)
        return feats.detach().cpu().numpy()[0]

    @torch.inference_mode()
    def embed_text(self, text: str) -> np.ndarray:
        tokens = self.tokenizer([text]).to(self.device)
        feats = self.model.encode_text(tokens)
        feats = feats / feats.norm(dim=-1, keepdim=True)
        return feats.detach().cpu().numpy()[0]


class ImageRAG:
    def __init__(
        self,
        chroma_client: Optional[chromadb.Client] = None,
        collection_name: str = "image_regions",
        model_name: str = "ViT-B-32",
        pretrained: str = "laion2b_s34b_b79k",
        use_ocr: bool = True,
        grid: Tuple[int, int] = (3, 3),
    ):
        self.encoder = CLIPEncoder(model_name=model_name, pretrained=pretrained)
        self.grid = grid
        self.chroma = chroma_client or chromadb.Client()
        self.col = self.chroma.get_or_create_collection(collection_name)
        self.ocr = RapidOCR() if (use_ocr and RapidOCR is not None) else None

    def _ocr_text(self, image: Image.Image) -> str:
        if self.ocr is None:
            return ""
        res, _ = self.ocr(np.array(image)[:, :, ::-1])  # expects BGR
        if not res:
            return ""
        return " ".join([r[1] for r in res])

    def index_image(self, image_path: str, action_id: Optional[str] = None) -> Dict:
        assert os.path.exists(image_path), f"Image not found: {image_path}"
        img = Image.open(image_path).convert("RGB")
        image_id = str(uuid.uuid4())

        # Whole-image embedding + OCR
        whole_emb = self.encoder.embed_image(img).tolist()
        whole_ocr = self._ocr_text(img)

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
            "bbox": [0, 0, img.width, img.height],
            "type": "whole",
            "action_id": action_id,
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
                "bbox": [int(x) for x in bbox],
                "type": "tile",
                "tile_index": idx,
                "action_id": action_id,
            })
            documents.append(tile_ocr or "")

        self.col.add(ids=ids, embeddings=embs, metadatas=metadatas, documents=documents)
        return {"image_id": image_id, "regions_indexed": len(ids), "path": image_path}

    def search(
        self,
        question: str,
        image_id: Optional[str] = None,
        k: int = 6,
        where: Optional[Dict] = None,
    ) -> Dict:
        qvec = self.encoder.embed_text(question).tolist()
        filt = where.copy() if where else {}
        if image_id:
            filt["image_id"] = image_id
        results = self.col.query(
            query_embeddings=[qvec],
            n_results=k,
            where=filt if filt else None,
        )
        hits = []
        for i in range(len(results["ids"][0])):
            hits.append({
                "id": results["ids"][0][i],
                "score": float(results["distances"][0][i]) if "distances" in results else None,
                "metadata": results["metadatas"][0][i],
                "ocr_text": results["documents"][0][i],
            })
        summary = self._summarize_evidence(question, hits)
        return {"question": question, "summary": summary, "evidence": hits}

    def _summarize_evidence(self, question: str, hits: List[Dict]) -> str:
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

    def compare_images(self, image_path_a: str, image_path_b: str, grid: Tuple[int, int]=(3,3)) -> Dict:
        # Simple diff using embeddings + OCR; you can evolve to SSIM/perceptual metrics.
        img_a = Image.open(image_path_a).convert("RGB")
        img_b = Image.open(image_path_b).convert("RGB")
        ocr_a = self._ocr_text(img_a)
        ocr_b = self._ocr_text(img_b)
        added = [t for t in ocr_b.split() if t not in set(ocr_a.split())]
        removed = [t for t in ocr_a.split() if t not in set(ocr_b.split())]
        return {"added_text": added[:50], "removed_text": removed[:50]}
``` 
## How to expose as a smolagents tool

- Wrap the ImageRAG methods in Tool classes (or your function-calling registry) that:
-   Accept JSON inputs.
-   Return compact JSON: summary + evidence (bboxes, paths) with small strings.
- Register them  so MainAgent can call:
-   `image_index`
-   `image_search`
-   `image_find_ui ` (can build this by maintaining a “ui_prototypes” collection and retrieving against it)
-   `image_compare`

## Operational Considerations
- Keep the encoder resident on GPU; batch tile embeddings; use torch.inference_mode() and fp16/bf16 for speed.
- Don’t over-crop: 3x3 or 4x4 is often enough. Add a “focused crop” mode if the planner provides an approximate ROI.
- Cache everything: embeddings and OCR live in Chroma with timestamps and action_id so you can answer “what changed after click(X)?” instantly.
- Confidence heuristics: If top similarity < threshold, escalate to small VLM on only the top-1 crop; otherwise avoid VLM calls entirely.
- UI library bootstrapping: Whenever you successfully click an element, save a small crop around it and its label as a prototype. Over time, your “UI memory” makes future detection instant.

## Model choices (local, fast)
- Image-text encoders (for embeddings):
- OpenCLIP ViT-B/32 or ViT-L/14 (openclip-torch). Good speed/size tradeoff.
- SigLIP base/large variants are very strong, but some are heavier. Try base patch16 384 if VRAM allows.
- Jina-CLIP-v1 is a compact alternative.
- OCR:
- RapidOCR runs fully local and fast on CPU or GPU.
- captioner/last-mile VLM:
  - qwen3-vl:8b_q4_K_M as an on-demand small VLM for top-1 crop only when needed.
  - Keep it unloaded by default or on separate process; only spin it up when retrieval confidence is low.


