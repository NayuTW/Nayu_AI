"""
Smolagents-compatible wrapper for WebBrowserTool.
Used by CodeAgent which requires the smolagents Tool interface.
"""
from typing import Dict, Any, Optional
from smolagents import Tool

from src.agents.tools.webbrowser import (
    _ddg_search,
    _static_or_dynamic,
    _to_markdown,
    _summarize_markdown,
    _get_ranker,
)


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
