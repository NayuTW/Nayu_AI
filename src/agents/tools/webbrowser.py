"""
Unified WebBrowserTool combining web automation and markdown browsing capabilities.
"""
import asyncio
import hashlib
import os
import re
import time
from typing import Any, Optional
from urllib.parse import urlparse, urljoin

from bs4 import BeautifulSoup
from ddgs import DDGS
import html2text
from playwright.async_api import async_playwright
from readability import Document
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from smolagents import Tool

from src.agents.embeddings.local_embedder import LocalEmbedder


CACHE_DIR = ".cache/webbrowser"
os.makedirs(CACHE_DIR, exist_ok=True)

# Global session for connection pooling
_requests_session = None

def _get_requests_session():
    """Get or create a reusable requests session."""
    global _requests_session
    if _requests_session is None:
        _requests_session = requests.Session()
        _requests_session.headers.update({
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        })
    return _requests_session


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


def _to_markdown(html: str, base_url: str = "") -> tuple[str, str]:
    """Convert HTML to markdown with readability extraction."""
    try:
        doc = Document(html)
        title = doc.short_title() or ""
        summary_html = doc.summary(html_partial=True)
    except Exception:
        title = ""
        summary_html = html
    
    soup = BeautifulSoup(summary_html, "lxml")
    
    # Convert relative URLs to absolute
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("/") and base_url:
            try:
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
    """Fetch HTML using requests (static pages) with session pooling."""
    session = _get_requests_session()
    r = session.get(url, timeout=timeout)
    r.raise_for_status()
    return r.text


def _selenium_html(url: str, wait_ms: int = 1500, viewport: tuple[int, int] = (1200, 1600)) -> str:
    """Fetch HTML using Selenium (dynamic pages with JavaScript)."""
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
    """Fetch HTML with auto-fallback from static to dynamic."""
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


def _ddg_search(query: str, max_results: int = 6) -> list[dict[str, str]]:
    """Search using DuckDuckGo."""
    results = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=max_results):
            results.append({
                "title": r.get("title", ""),
                "href": r.get("href", ""),
                "body": r.get("body", "")
            })
    return results


def _summarize_markdown(md: str, max_chars: int = 1400) -> str:
    """Truncate markdown to a maximum character count."""
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
    """Extract domain from URL."""
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


class EmbeddingRanker:
    """Rank search results using local embeddings."""
    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5"):
        self.emb = LocalEmbedder(model_name=model_name, lazy_load=True)

    def score(self, query: str, candidates: list[dict[str, str]]) -> list[dict[str, Any]]:
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
    """Get or create singleton ranker instance."""
    global __RANKER
    if __RANKER is None:
        __RANKER = EmbeddingRanker(model_name="BAAI/bge-small-en-v1.5")
    return __RANKER


class WebBrowserTool:
    """
    Unified web browser tool combining:
    - Web search and markdown extraction (from md_browser)
    - Interactive browser automation (from web)
    
    Actions:
    - search: DuckDuckGo search with embedding-based ranking
    - fetch: Extract content from URL as markdown
    - browse: Research a query by fetching and ranking multiple pages
    - goto: Navigate to URL (interactive)
    - interact: Perform interactive actions (click, type, read, query)
    """
    
    def __init__(self, state):
        self.state = state
        self.browser = None
        self.page = None

    @staticmethod
    def spec():
        return {
            "name": "webbrowser",
            "description": (
                "Search the web, extract content as markdown, or perform interactive browser actions. "
                "Use 'search' to find information, 'fetch' to extract a specific URL, "
                "'browse' to research a query across multiple sources, "
                "'goto' to navigate interactively, or 'interact' for browser automation."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["search", "fetch", "browse", "goto", "interact"],
                        "description": "Operation to perform"
                    },
                    # Search/fetch/browse parameters
                    "query": {
                        "type": "string",
                        "description": "Search query for 'search' or 'browse' actions"
                    },
                    "url": {
                        "type": "string",
                        "description": "Target URL for 'fetch' or 'goto' actions"
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["auto", "static", "dynamic"],
                        "description": "Fetch mode: 'static' (requests), 'dynamic' (Selenium), 'auto' (fallback)"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum search results (default: 5)"
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Top K results to fetch for 'browse' (default: 3)"
                    },
                    "char_limit": {
                        "type": "integer",
                        "description": "Character limit per page (default: 1200)"
                    },
                    # Interactive browser parameters
                    "browser_action": {
                        "type": "string",
                        "enum": ["click_text", "type", "read", "query"],
                        "description": "Browser action for 'interact' mode"
                    },
                    "text": {
                        "type": "string",
                        "description": "Text to click for 'click_text' action"
                    },
                    "selector": {
                        "type": "string",
                        "description": "CSS selector for browser actions"
                    },
                    "input": {
                        "type": "string",
                        "description": "Text to type into selector"
                    },
                },
                "required": ["action"]
            }
        }

    async def _ensure_browser(self):
        """Ensure Playwright browser is initialized."""
        if self.browser is None:
            pw = await async_playwright().start()
            self.browser = await pw.chromium.launch(headless=True)
            self.page = await self.browser.new_page()

    async def _handle_search(self, query: str, max_results: int = 5) -> dict[str, Any]:
        """Handle search action."""
        results = _ddg_search(query, max_results=max_results)
        summary = f"Found {len(results)} search results for: {query}"
        if results:
            summary += "\n\n"
            for i, r in enumerate(results[:5], 1):
                summary += f"{i}. {r.get('title', 'No title')}\n   {r.get('href', '')}\n   {r.get('body', '')[:150]}...\n\n"
        return {
            "summary": summary[:2000],
            "delta": {"last_observation": summary[:500]},
            "sources": results
        }

    async def _handle_fetch(self, url: str, mode: str = "auto", char_limit: int = 1200) -> dict[str, Any]:
        """Handle fetch action."""
        try:
            html = await asyncio.to_thread(_static_or_dynamic, url, mode)
            title, md = _to_markdown(html, base_url=url)
            excerpt = _summarize_markdown(md, max_chars=char_limit)
            summary = f"## {title or 'Page'}\n\n{excerpt}\n\nSource: {url}"
            return {
                "summary": summary[:4000],
                "delta": {"last_observation": f"Fetched {title or url}: {excerpt[:200]}..."},
                "sources": [{"title": title, "href": url}],
                "markdown": excerpt
            }
        except Exception as e:
            summary = f"Failed to fetch {url}: {str(e)}"
            return {
                "summary": summary,
                "delta": {"last_observation": summary}
            }

    async def _handle_browse(
        self,
        query: str,
        mode: str = "auto",
        max_results: int = 5,
        top_k: int = 3,
        char_limit: int = 1200
    ) -> dict[str, Any]:
        """Handle browse action."""
        try:
            # Search and rank results
            candidates = _ddg_search(query, max_results=max_results)
            ranked = await asyncio.to_thread(_get_ranker().score, query, candidates)
            ranked = sorted(ranked, key=lambda x: x.get("_score", 0.0), reverse=True)[:top_k]
            
            sources = []
            chunks = []
            
            # Fetch and extract content from top results
            for r in ranked:
                href = r.get("href", "")
                if not href:
                    continue
                try:
                    html = await asyncio.to_thread(_static_or_dynamic, href, mode)
                    title, md = _to_markdown(html, base_url=href)
                    excerpt = _summarize_markdown(md, max_chars=char_limit)
                    sources.append({"title": title, "href": href})
                    chunks.append(f"## {title}\n\n{excerpt}\n\nSource: {href}")
                except Exception as e:
                    chunks.append(f"Failed to fetch {href}: {str(e)}")
            
            summary = f"Research results for: {query}\n\n" + "\n\n---\n\n".join(chunks)
            return {
                "summary": summary[:4000],
                "delta": {"last_observation": f"Browsed {len(sources)} pages for: {query}"},
                "sources": sources,
                "markdown": summary[:16000]
            }
        except Exception as e:
            summary = f"Browse failed for '{query}': {str(e)}"
            return {
                "summary": summary,
                "delta": {"last_observation": summary}
            }

    async def _handle_goto(self, url: str) -> dict[str, Any]:
        """Handle goto action (interactive navigation)."""
        await self._ensure_browser()
        await self.page.goto(url)
        content = await self.page.title()
        summary = f"Navigated to {url} - Title: {content}"
        return {
            "summary": summary,
            "delta": {"last_observation": summary}
        }

    async def _handle_interact(
        self,
        browser_action: str,
        text: str = "",
        selector: str = "",
        input: str = ""
    ) -> dict[str, Any]:
        """Handle interactive browser actions."""
        await self._ensure_browser()
        summary = ""
        
        if browser_action == "click_text" and text:
            el = await self.page.get_by_text(text).first
            await el.click()
            summary = f"Clicked text: {text}"
        elif browser_action == "type" and selector and input:
            await self.page.fill(selector, input)
            summary = f"Typed into {selector}: {input[:50]}"
        elif browser_action == "read":
            content = await self.page.content()
            summary = f"Page content (truncated): {content[:1000]}"
        elif browser_action == "query" and selector:
            txt = await self.page.inner_text(selector)
            summary = f"Selector {selector} text: {txt[:1000]}"
        else:
            summary = f"Invalid browser_action '{browser_action}' or missing parameters."
        
        return {
            "summary": summary,
            "delta": {"last_observation": summary}
        }

    async def run(
        self,
        action: str,
        query: str = "",
        url: str = "",
        mode: str = "auto",
        max_results: int = 5,
        top_k: int = 3,
        char_limit: int = 1200,
        browser_action: str = "",
        text: str = "",
        selector: str = "",
        input: str = ""
    ) -> dict[str, Any]:
        """Main entry point for the tool."""
        try:
            if action == "search":
                if not query:
                    return {"summary": "Error: 'query' required for search", "delta": {}}
                return await self._handle_search(query, max_results)
            
            elif action == "fetch":
                if not url:
                    return {"summary": "Error: 'url' required for fetch", "delta": {}}
                return await self._handle_fetch(url, mode, char_limit)
            
            elif action == "browse":
                if not query:
                    return {"summary": "Error: 'query' required for browse", "delta": {}}
                return await self._handle_browse(query, mode, max_results, top_k, char_limit)
            
            elif action == "goto":
                if not url:
                    return {"summary": "Error: 'url' required for goto", "delta": {}}
                return await self._handle_goto(url)
            
            elif action == "interact":
                if not browser_action:
                    return {"summary": "Error: 'browser_action' required for interact", "delta": {}}
                return await self._handle_interact(browser_action, text, selector, input)
            
            else:
                return {
                    "summary": f"Error: Unknown action '{action}'. Valid actions: search, fetch, browse, goto, interact",
                    "delta": {"last_observation": f"Invalid action: {action}"}
                }
        except Exception as e:
            error_msg = f"WebBrowser error ({action}): {str(e)}"
            return {
                "summary": error_msg,
                "delta": {"last_observation": error_msg}
            }


class WebBrowserSmolTool(Tool):
    """
    Smolagents-compatible web browser tool for CodeAgent.
    Provides search, fetch, and browse capabilities.
    """
    name = "webbrowser"
    description = (
        "Search the web, extract content as markdown, or research a query. "
        "Use 'search' to find information with DuckDuckGo, "
        "'fetch' to extract content from a specific URL as markdown, "
        "or 'browse' to research a query across multiple ranked sources. "
        "Returns structured markdown content with sources."
    )
    inputs = {
        "action": {
            "type": "string",
            "enum": ["search", "fetch", "browse"],
            "description": "Operation: 'search' (DuckDuckGo), 'fetch' (single URL), or 'browse' (multi-source research)"
        },
        "query": {
            "type": "string",
            "description": "Search query for 'search' or 'browse' actions",
            "nullable": True
        },
        "url": {
            "type": "string",
            "description": "Target URL for 'fetch' action",
            "nullable": True
        },
        "mode": {
            "type": "string",
            "description": "Fetch mode: 'static' (requests), 'dynamic' (Selenium), 'auto' (fallback)",
            "enum": ["auto", "static", "dynamic"],
            "default": "auto",
            "nullable": True
        },
        "max_results": {
            "type": "integer",
            "description": "Maximum search results (default: 5)",
            "default": 5,
            "nullable": True
        },
        "top_k": {
            "type": "integer",
            "description": "Top K results to fetch for 'browse' (default: 3)",
            "default": 3,
            "nullable": True
        },
        "char_limit": {
            "type": "integer",
            "description": "Character limit per page (default: 1200)",
            "default": 1200,
            "nullable": True
        },
    }
    outputs = {
        "summary": {"type": "string"},
        "sources": {"type": "array", "items": {"type": "object"}},
        "markdown": {"type": "string"},
    }
    output_type = "string"

    def forward(
        self,
        action: str,
        query: Optional[str] = None,
        url: Optional[str] = None,
        mode: str = "auto",
        max_results: int = 5,
        top_k: int = 3,
        char_limit: int = 1200,
    ) -> str:
        """
        Execute web browser action and return formatted results.
        
        Returns:
            Formatted string with summary and sources
        """
        try:
            if action == "search":
                if not query:
                    return "Error: 'query' required for search action"
                results = _ddg_search(query, max_results=max_results)
                summary = f"Search results for: {query}\n\n"
                for i, r in enumerate(results, 1):
                    summary += f"{i}. {r.get('title', 'No title')}\n"
                    summary += f"   URL: {r.get('href', '')}\n"
                    summary += f"   {r.get('body', '')[:150]}...\n\n"
                return summary[:2000]

            elif action == "fetch":
                if not url:
                    return "Error: 'url' required for fetch action"
                html = _static_or_dynamic(url, mode=mode)
                title, md = _to_markdown(html, base_url=url)
                excerpt = _summarize_markdown(md, max_chars=char_limit)
                return f"## {title or 'Page'}\n\n{excerpt}\n\nSource: {url}"

            elif action == "browse":
                if not query:
                    return "Error: 'query' required for browse action"
                
                # Search and rank
                candidates = _ddg_search(query, max_results=max_results)
                ranked = _get_ranker().score(query, candidates)
                ranked = sorted(ranked, key=lambda x: x.get("_score", 0.0), reverse=True)[:top_k]
                
                # Fetch and extract
                chunks = []
                for r in ranked:
                    href = r.get("href", "")
                    if not href:
                        continue
                    try:
                        html = _static_or_dynamic(href, mode=mode)
                        title, md = _to_markdown(html, base_url=href)
                        excerpt = _summarize_markdown(md, max_chars=char_limit)
                        chunks.append(f"## {title}\n\n{excerpt}\n\nSource: {href}")
                    except Exception as e:
                        chunks.append(f"Failed to fetch {href}: {str(e)}")
                
                result = f"Research results for: {query}\n\n" + "\n\n---\n\n".join(chunks)
                return result[:4000]

            else:
                return f"Error: Unknown action '{action}'. Valid actions: search, fetch, browse"

        except Exception as e:
            return f"WebBrowser error: {str(e)}"
