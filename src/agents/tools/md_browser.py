import hashlib
import os
import re
import time
from typing import Dict, Any, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from readability import Document
import html2text

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions

from smolagents import Tool

from src.agents.embeddings.local_embedder import LocalEmbedder

CACHE_DIR = ".cache/md_browser"
os.makedirs(CACHE_DIR, exist_ok=True)

def _hash(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def _cache_path(key: str, suffix: str) -> str:
    return os.path.join(CACHE_DIR, f"{_hash(key)}.{suffix}")

def _save(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)

def _load(path: str) -> Optional[str]:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return None

def _to_markdown(html: str, base_url: str = "") -> Tuple[str, str]:
    try:
        doc = Document(html)
        title = doc.short_title() or ""
        summary_html = doc.summary(html_partial=True)
    except Exception:
        title = ""
        summary_html = html
    soup = BeautifulSoup(summary_html, "lxml")
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("/"):
            try:
                from urllib.parse import urlparse, urljoin
                base = urlparse(base_url)
                abs_href = urljoin(f"{base.scheme}://{base.netloc}", href)
                a["href"] = abs_href
            except Exception:
                pass
    h2t = html2text.HTML2Text()
    h2t.body_width = 0
    h2t.ignore_images = True
    h2t.ignore_emphasis = False
    h2t.ignore_links = False
    h2t.protect_links = True
    md = h2t.handle(str(soup))
    md = re.sub(r"\n{3,}", "\n\n", md).strip()
    return title, md

def _requests_fetch(url: str, timeout: int = 15) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    }
    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.text

def _selenium_html(url: str, wait_ms: int = 1500, viewport: Tuple[int, int] = (1200, 1600)) -> str:
    options = ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument(f"--window-size={viewport[0]},{viewport[1]}")
    driver = webdriver.Chrome(options=options)
    try:
        driver.get(url)
        time.sleep(wait_ms / 1000.0)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.5);")
        time.sleep(0.4)
        html = driver.page_source
        return html
    finally:
        driver.quit()

def _static_or_dynamic(url: str, mode: str = "auto") -> str:
    key = f"{mode}:{url}"
    cached = _load(_cache_path(key, "html"))
    if cached:
        return cached
    html = ""
    if mode in ("static", "auto"):
        try:
            html = _requests_fetch(url)
        except Exception:
            if mode == "static":
                raise
    if not html and mode in ("dynamic", "auto"):
        html = _selenium_html(url)
    _save(_cache_path(key, "html"), html)
    return html

def _ddg_search(query: str, max_results: int = 6) -> List[Dict[str, str]]:
    results = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=max_results):
            results.append({"title": r.get("title",""), "href": r.get("href",""), "body": r.get("body","")})
    return results

def _summarize_markdown(md: str, max_chars: int = 1400) -> str:
    if len(md) <= max_chars:
        return md
    blocks = md.split("\n\n")
    out = []
    total = 0
    for b in blocks:
        if b.strip().startswith("```"):
            continue
        out.append(b)
        total += len(b) + 2
        if total >= max_chars:
            break
    out.append("\n\n[...truncated...]")
    return "\n\n".join(out)

def _domain_from_url(url: str) -> str:
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc.lower()
    except Exception:
        return ""

class EmbeddingRanker:
    def __init__(self, model_name: str = "intfloat/e5-small-v2"):
        self.emb = LocalEmbedder(model_name=model_name)

    def score(self, query: str, candidates: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        texts = [((c.get("title") or "") + " " + (c.get("body") or "")).strip() for c in candidates]
        qv = self.emb.embed_text(query)
        cvs = self.emb.embed_texts(texts)
        scored = []
        for c, v in zip(candidates, cvs):
            score = float(sum(q * x for q, x in zip(qv, v)))
            c2 = dict(c)
            c2["_score"] = score
            scored.append(c2)
        return scored

__RANKER: Optional[EmbeddingRanker] = None
def _get_ranker() -> EmbeddingRanker:
    global __RANKER
    if __RANKER is None:
        __RANKER = EmbeddingRanker(model_name="intfloat/e5-small-v2")
    return __RANKER

class MarkdownBrowserTool(Tool):
    name = "md_browser"
    description = (
        "Search and read webpages as Markdown. Use 'fetch' for a specific URL or 'browse' to research a query. "
        "Prefers static fetch (requests + readability); auto-falls back to headless Selenium. "
        "Uses a small local embedding model to rank links."
    )
    inputs = {
        "action": {"type": "string", "enum": ["search", "fetch", "browse"], "description": "Operation"},
        "query": {"type": "string", "description": "Search query for 'search' or 'browse'"},
        "url": {"type": "string", "description": "Target URL for 'fetch'"},
        "mode": {"type": "string", "enum": ["auto", "static", "dynamic"], "default": "auto"},
        "max_results": {"type": "integer", "default": 5},
        "top_k": {"type": "integer", "default": 3},
        "depth": {"type": "integer", "default": 1},
        "per_page_char_budget": {"type": "integer", "default": 1200},
        "domain_whitelist": {"type": "string", "description": "Comma-separated allowed domains (optional)"},
    }
    outputs = {
        "summary": {"type": "string"},
        "sources": {"type": "array", "items": {"type": "object"}},
        "markdown": {"type": "string"},
    }

    def forward(
        self,
        action: str,
        query: str = "",
        url: str = "",
        mode: str = "auto",
        max_results: int = 5,
        top_k: int = 3,
        depth: int = 1,
        per_page_char_budget: int = 1200,
        domain_whitelist: str = "",
    ) -> Dict[str, Any]:
        if action == "search":
            results = _ddg_search(query, max_results=max_results)
            return {"summary": f"Search results for: {query}", "sources": results, "markdown": ""}

        if action == "fetch":
            assert url, "url required for fetch"
            html = _static_or_dynamic(url, mode=mode)
            title, md = _to_markdown(html, base_url=url)
            excerpt = _summarize_markdown(md, max_chars=per_page_char_budget)
            return {"summary": f"{title or 'Page'} — extracted and summarized.", "sources": [{"title": title, "href": url}], "markdown": excerpt}

        if action == "browse":
            assert query, "query required for browse"
            whitelist = {d.strip().lower() for d in domain_whitelist.split(",") if d.strip()} if domain_whitelist else set()

            candidates = _ddg_search(query, max_results=max_results)
            ranked = _get_ranker().score(query, candidates)
            for r in ranked:
                host = _domain_from_url(r.get("href", ""))
                if whitelist and any(host.endswith(w) for w in whitelist):
                    r["_score"] = r.get("_score", 0.0) + 0.5
            ranked = sorted(ranked, key=lambda x: x.get("_score", 0.0), reverse=True)[:top_k]

            sources = []
            chunks = []
            for r in ranked:
                href = r.get("href", "")
                if not href:
                    continue
                try:
                    html = _static_or_dynamic(href, mode=mode)
                    title, md = _to_markdown(html, base_url=href)
                    excerpt = _summarize_markdown(md, max_chars=per_page_char_budget)
                    sources.append({"title": title, "href": href})
                    chunks.append(f"# {title}\n\n{excerpt}\n\nSource: {href}")
                except Exception as e:
                    chunks.append(f"Failed to fetch {href}: {e}")

            summary = f"Browse summary for: {query}\n\n" + "\n\n---\n\n".join(chunks)
            return {"summary": summary[:4000], "sources": sources, "markdown": summary[:16000]}

        return {"summary": "Invalid action", "sources": [], "markdown": ""}