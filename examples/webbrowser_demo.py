"""
Demo script showing the capabilities of the unified WebBrowserTool.

This demonstrates how the tool combines:
1. Web search (DuckDuckGo)
2. Content extraction (markdown conversion with caching)
3. Research (multi-source with embedding ranking)
4. Interactive browsing (Playwright)

Usage:
    python examples/webbrowser_demo.py
"""

async def demo_search():
    """Demo: Search action"""
    print("\n=== DEMO: Search ===")
    print("Action: search")
    print("Query: 'Python async programming'")
    print("\nExpected output:")
    print("- List of search results from DuckDuckGo")
    print("- Title, URL, and snippet for each result")
    print("- Returns: summary with sources")
    

async def demo_fetch():
    """Demo: Fetch action"""
    print("\n=== DEMO: Fetch ===")
    print("Action: fetch")
    print("URL: 'https://example.com'")
    print("\nExpected output:")
    print("- Extracted content as clean markdown")
    print("- Title and main content from readability extraction")
    print("- Cached for future requests")
    print("- Returns: markdown excerpt with source")


async def demo_browse():
    """Demo: Browse action"""
    print("\n=== DEMO: Browse ===")
    print("Action: browse")
    print("Query: 'machine learning tutorials'")
    print("\nExpected output:")
    print("- Searches DuckDuckGo for relevant pages")
    print("- Ranks results using local embeddings (e5-small-v2)")
    print("- Fetches and extracts top 3 pages")
    print("- Returns: aggregated markdown with all sources")


async def demo_goto():
    """Demo: Goto action (interactive)"""
    print("\n=== DEMO: Goto (Interactive) ===")
    print("Action: goto")
    print("URL: 'https://github.com'")
    print("\nExpected output:")
    print("- Opens page in headless Playwright browser")
    print("- Returns page title")
    print("- Browser remains open for further interactions")


async def demo_interact():
    """Demo: Interact action (browser automation)"""
    print("\n=== DEMO: Interact (Browser Automation) ===")
    print("Action: interact")
    print("Examples:")
    print("\n1. Click text:")
    print("   browser_action: 'click_text'")
    print("   text: 'Sign in'")
    print("\n2. Type input:")
    print("   browser_action: 'type'")
    print("   selector: '#search'")
    print("   input: 'hello world'")
    print("\n3. Read page:")
    print("   browser_action: 'read'")
    print("\n4. Query selector:")
    print("   browser_action: 'query'")
    print("   selector: 'h1'")


def main():
    """Run all demos"""
    print("=" * 60)
    print("WebBrowserTool - Unified Web Tool Demo")
    print("=" * 60)
    print("\nThis tool combines the capabilities of:")
    print("  • WebTool (interactive browser automation)")
    print("  • MarkdownBrowserTool (search, fetch, research)")
    print("\nInto a single, streamlined interface with 5 actions:")
    print("  1. search  - DuckDuckGo search")
    print("  2. fetch   - Extract URL content as markdown")
    print("  3. browse  - Multi-source research with ranking")
    print("  4. goto    - Interactive navigation")
    print("  5. interact - Browser automation")
    
    import asyncio
    asyncio.run(demo_search())
    asyncio.run(demo_fetch())
    asyncio.run(demo_browse())
    asyncio.run(demo_goto())
    asyncio.run(demo_interact())
    
    print("\n" + "=" * 60)
    print("Key Improvements:")
    print("=" * 60)
    print("✓ Single tool instead of two confusing tools")
    print("✓ Clear action names with better error messages")
    print("✓ All parameters are optional (validated per action)")
    print("✓ Supports both content extraction AND automation")
    print("✓ Embedding-based ranking for better search results")
    print("✓ Caching for faster repeated requests")
    print("✓ Consistent async interface for main agent")
    print("✓ Smolagents wrapper for CodeAgent compatibility")
    print("\n")


if __name__ == "__main__":
    main()
