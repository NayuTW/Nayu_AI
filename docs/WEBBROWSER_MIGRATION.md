# WebBrowser Tool Migration Guide

## Overview

The `web` and `md_browser` tools have been unified into a single `webbrowser` tool to eliminate confusion and provide a streamlined interface for all web-related operations.

## What Changed

### Before (Two Separate Tools)

#### WebTool (`web.py`)
- **Actions**: goto, click_text, type, read, query
- **Problem**: Limited to basic Playwright automation, error message "Invalid web action/args" for invalid inputs
- **Not registered**: Only available to main agent

#### MarkdownBrowserTool (`md_browser.py`)
- **Actions**: search, fetch, browse
- **Problem**: Only available to CodeAgent, not available to main agent
- **Features**: DuckDuckGo search, embedding-based ranking, markdown conversion

### After (Single Unified Tool)

#### WebBrowserTool (`webbrowser.py`)
- **Actions**: search, fetch, browse, goto, interact
- **Benefits**: 
  - All web operations in one tool
  - Available to both main agent and CodeAgent
  - Better error messages
  - Clear parameter validation per action
  - Consistent async interface

## Action Reference

### 1. search
Search the web using DuckDuckGo.

**Parameters:**
- `query` (required): Search query
- `max_results` (optional): Maximum results (default: 5)

**Returns:** List of search results with title, URL, and snippet

**Example:**
```json
{
  "action": "search",
  "query": "Python async programming",
  "max_results": 10
}
```

### 2. fetch
Extract content from a single URL as markdown.

**Parameters:**
- `url` (required): URL to fetch
- `mode` (optional): "auto" (default), "static", or "dynamic"
- `char_limit` (optional): Character limit (default: 1200)

**Returns:** Markdown content with title and source

**Example:**
```json
{
  "action": "fetch",
  "url": "https://example.com",
  "mode": "auto",
  "char_limit": 1500
}
```

### 3. browse
Research a query by fetching and ranking multiple sources.

**Parameters:**
- `query` (required): Research query
- `mode` (optional): "auto" (default), "static", or "dynamic"
- `max_results` (optional): Maximum search results (default: 5)
- `top_k` (optional): Number of pages to fetch (default: 3)
- `char_limit` (optional): Character limit per page (default: 1200)

**Returns:** Aggregated markdown from top-ranked sources

**Example:**
```json
{
  "action": "browse",
  "query": "machine learning tutorials",
  "top_k": 5
}
```

### 4. goto
Navigate to a URL using interactive browser (Playwright).

**Parameters:**
- `url` (required): URL to navigate to

**Returns:** Page title

**Example:**
```json
{
  "action": "goto",
  "url": "https://github.com"
}
```

### 5. interact
Perform interactive browser automation.

**Parameters:**
- `browser_action` (required): "click_text", "type", "read", or "query"
- Additional parameters based on browser_action:
  - **click_text**: `text` (required)
  - **type**: `selector` (required), `input` (required)
  - **read**: (no additional parameters)
  - **query**: `selector` (required)

**Returns:** Action result or content

**Examples:**
```json
{
  "action": "interact",
  "browser_action": "click_text",
  "text": "Sign in"
}
```

```json
{
  "action": "interact",
  "browser_action": "type",
  "selector": "#search-box",
  "input": "hello world"
}
```

## Migration Steps

### For Main Agent
No changes needed! The tool is automatically registered as `webbrowser` instead of `web`.

### For CodeAgent
The tool is now available through the smolagents wrapper (`webbrowser_smol.py`) which provides the same search/fetch/browse capabilities.

### For Custom Code
If you have custom code importing the old tools, update:

```python
# Old
from src.agents.tools.web import WebTool
from src.agents.tools.md_browser import MarkdownBrowserTool

# New
from src.agents.tools.webbrowser import WebBrowserTool
from src.agents.tools.webbrowser_smol import WebBrowserSmolTool  # For smolagents
```

## Key Improvements

1. **Single Tool**: No more confusion between `web` and `md_browser`
2. **Better Errors**: Clear error messages for invalid actions or missing parameters
3. **Universal Access**: Available to both main agent and CodeAgent
4. **Consistent Interface**: All actions follow the same async pattern
5. **Smart Fetching**: Auto-fallback from static to dynamic loading
6. **Embedding Ranking**: Better search results using local embeddings
7. **Caching**: Repeated requests are cached for performance

## Backward Compatibility Notes

- Old tool files (`web.py` and `md_browser.py`) have been removed
- Tool name changed from `web` to `webbrowser` in main agent
- CodeAgent now uses `WebBrowserSmolTool` instead of `MarkdownBrowserTool`
- All old action names still work in their respective modes:
  - Old `web` actions: now under `interact`
  - Old `md_browser` actions: now direct actions (search, fetch, browse)
