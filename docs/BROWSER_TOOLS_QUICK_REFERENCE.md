# Interactive Browser Tools - Quick Reference

## For Users (MainAgent)

When you need visual analysis or interactive browsing, use the vision_agent:

```python
# Delegate browsing task
result = vision_agent(task="Your browsing task here")

# The agent will:
# 1. Start a browser if needed
# 2. Navigate and interact with web pages
# 3. Take screenshots to verify actions
# 4. Analyze results
# 5. Return observations and findings
```

## For Developers (VisionAgent)

### Available Browser Tools (Use Within VisionAgent)

```python
# Start browser
start_browser() → str
# Output: "Browser started successfully..."

# Navigate
go_to_url(url: str) → str
# Output: "Navigated to {url}..."

# Click elements
click_element(text: str) → str  # By visible text
click_link(text: str) → str     # Specifically for links

# Search on page
search_item_ctrl_f(text: str, nth_result: int = 1) → str
# Output: "Found 5 matches for 'Python'..."

# Scroll
scroll_down(num_pixels: int = 1200) → str
scroll_up(num_pixels: int = 1200) → str

# Navigation
go_back() → str
close_popups() → str

# Check state
get_current_url() → str
# Output: "Current URL: https://..."
```

### Using Browser Tools in VisionAgent

```python
# VisionAgent automatically has access to all tools
# They're registered in _init_tools() method

# Example: Search GitHub trending
def my_browsing_task():
    start_browser()
    go_to_url("https://github.com/trending")
    
    # Take screenshot to verify page loaded
    vision(task="What's on the page?")
    
    # Search for Python
    search_item_ctrl_f("Python")
    
    # Click Python link
    click_element("Python")
    
    # Wait and screenshot
    time.sleep(2)
    vision(task="Show me the Python trending repos")
```

## Implementation Details

### Browser Tool Structure

All tools follow this pattern:

```python
@tool
def tool_name(args) -> str:
    """Tool description."""
    try:
        driver = get_driver()
        if driver is None:
            return "Error: Browser not started. Call start_browser first."
        
        # Perform action
        action_result = perform_action()
        
        # Brief delay for UI responsiveness
        sleep(0.5)
        
        return f"Status: {action_result}"
    except Exception as e:
        return f"Error: {e}"

# Register tool attributes (required for smolagents)
tool_name.name = "tool_name"
tool_name.description = "Tool description"
```

### Adding New Browser Tools

To add a new browser tool to `active_browser.py`:

```python
@tool
def my_new_tool(param: str) -> str:
    """My tool description."""
    try:
        driver = get_driver()
        if driver is None:
            return "Error: Browser not started. Call start_browser first."
        
        # Your implementation here
        result = some_action(param)
        sleep(0.5)
        
        return f"Success: {result}"
    except Exception as e:
        return f"Error: {e}"

my_new_tool.name = "my_new_tool"
my_new_tool.description = "My tool description"
```

Then register in `vision_agent.py`:

```python
# In vision_agent.py _init_tools() method, add:
browser_tools = [
    # ... existing tools ...
    my_new_tool,  # Add your tool here
]
```

## Important Notes

### Browser Window Details
- **Size**: 1000x1350 pixels (for consistent screenshots)
- **Position**: 0,0 (top-left corner)
- **PDF Viewer**: Disabled
- **Scale Factor**: 1.0 (no scaling)

### Design Principles
1. **Single Browser**: Only one WebDriver instance at a time
2. **Error Handling**: All tools return strings, never throw exceptions
3. **Status Updates**: Tools return completion status for agent awareness
4. **Driver Safety**: Always check driver before use with `get_driver()`
5. **Responsiveness**: Brief sleep() after actions for UI updates

### Integration with Desktop Screenshots
- `.cache/desktop.png` updates every 2 seconds
- Updates instantly after MainAgent tool execution
- Updates after each browser tool action
- VisionAgent analyzes live screenshot for verification

### Performance Tips
1. Take screenshots after meaningful actions (not every action)
2. Use search_item_ctrl_f before clicking hard-to-find elements
3. Close popups with close_popups() instead of clicking X button
4. Scroll viewport-sized amounts (1200px) for efficiency
5. Use vision() to verify page state, not continuous screenshots

## Debugging

### Browser Not Starting
```python
result = start_browser()
if "Error" in result:
    print("Check if ChromeDriver is installed and in PATH")
    print("Check if Chrome is installed")
```

### Element Not Found
```python
# Try searching for text first
search_result = search_item_ctrl_f("button text")
if "Match #1 not found" in search_result:
    # Try scrolling
    scroll_down(1200)
    # Try again
    search_result = search_item_ctrl_f("button text")
```

### Screenshot Not Updating
```python
# Verify desktop capture is running
# Check .cache/desktop.png has recent modification time
# Take a new action that triggers capture
click_element("any button")
# Screenshot should update within 100ms
```

## Architecture Diagram

```
smolagents CodeAgent (VisionAgent)
│
├─ Tools Registered:
│  ├─ vision (VisionSmolTool)
│  │  └─ Analyzes .cache/desktop.png
│  │
│  └─ Browser Tools (9 tools)
│     ├─ start_browser
│     ├─ go_to_url
│     ├─ click_element
│     ├─ click_link
│     ├─ search_item_ctrl_f
│     ├─ scroll_down
│     ├─ scroll_up
│     ├─ go_back
│     ├─ close_popups
│     └─ get_current_url
│
├─ Global State:
│  ├─ _browser_driver (WebDriver instance)
│  └─ _current_agent (VisionAgent reference)
│
└─ Desktop Integration:
   └─ .cache/desktop.png (auto-updated by MainAgent)
```

## Common Workflows

### 1. Data Extraction from Website
```
start_browser()
go_to_url("https://example.com")
vision(task="Extract all table data")
→ Agent reads table from screenshot
→ Returns data
```

### 2. Multi-Step Navigation
```
start_browser()
go_to_url("https://example.com")
click_link("Login")
vision(task="What login form fields exist?")
click_element("Username")
→ Agent fills in via vision+typing
click_element("Submit")
vision(task="Verify logged in")
```

### 3. Search and Analysis
```
start_browser()
go_to_url("https://search.example.com")
search_item_ctrl_f("target query")
click_element("Search")
vision(task="Analyze search results")
scroll_down(1200)
vision(task="Show more results")
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Browser won't start | Install ChromeDriver, add to PATH |
| Click doesn't work | Use search_item_ctrl_f first, scroll, verify text exact match |
| Page not loading | Check URL is correct, wait longer with vision() call |
| Screenshot outdated | Click any element to trigger refresh |
| Multiple browsers open | Close all and start fresh with start_browser() |

---

**Quick Command Reference**:
- `start_browser()` - Begin browsing
- `go_to_url(url)` - Go to website
- `click_element(text)` / `click_link(text)` - Click something
- `search_item_ctrl_f(text)` - Find text on page
- `scroll_down(1200)` / `scroll_up(1200)` - Scroll page
- `go_back()` - Previous page
- `close_popups()` - Close modals
- `get_current_url()` - Check current URL
- `vision(task=...)` - Analyze screenshot
