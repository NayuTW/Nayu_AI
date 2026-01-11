"""
Active browser tools for interactive web browsing using Helium.
Provides tools for navigating, searching, and interacting with web pages.
"""
import os
from time import sleep
from typing import Optional, Any

from helium import *
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from smolagents import tool


load_dotenv()
# Chrome profile-directory
chrome_dir = os.getenv('CHROME_DIR', '$HOME/.config/chromium/')
# Global browser state
_browser_driver: Optional[Any] = None
_current_agent: Optional[Any] = None


def init_browser_tools(agent: Any) -> None:
    """
    Initialize browser tools with a reference to the agent.
    Should be called when VisionAgent initializes.
    
    Args:
        agent: The VisionAgent instance that will use these tools
    """
    global _current_agent
    _current_agent = agent


def get_driver() -> Optional[Any]:
    """Get the current browser driver instance."""
    global _browser_driver
    if _browser_driver is None:
        try:
            _browser_driver = helium.get_driver()
        except:
            pass
    return _browser_driver


# Chrome options
_chrome_options = webdriver.ChromeOptions()
_chrome_options.add_argument("--start-fullscreen")
_chrome_options.add_argument("--force-device-scale-factor=1")
_chrome_options.add_argument("--window-size=1920,1080")
_chrome_options.add_argument("--disable-pdf-viewer")
_chrome_options.add_argument("--window-position=0,0")
_chrome_options.add_argument(f"--user-data-dir={chrome_dir}")
_chrome_options.add_argument("--profile-directory=Default")

@tool
def start_browser() -> str:
    """Starts the Chrome browser instance for web browsing."""
    global _browser_driver
    try:
        _browser_driver = helium.start_chrome(headless=False, options=_chrome_options)
        sleep(1.0)
        return "Browser started successfully. Use go_to_url(url) to navigate to a website."
    except Exception as e:
        return f"Error starting browser: {e}"

start_browser.name = "start_browser"
start_browser.description = "Starts the Chrome browser instance for web browsing."


@tool
def go_to_url(url: str) -> str:
    """Navigate to a specific URL.
    
    Args:
        url: The URL to navigate to (e.g., https://github.com)
    """
    try:
        driver = get_driver()
        if driver is None:
            return "Error: Browser not started. Call start_browser first."
        helium.go_to(url)
        sleep(1.5)
        return f"Navigated to {url}. Current URL: {driver.current_url}"
    except Exception as e:
        return f"Error navigating to URL: {e}"

go_to_url.name = "go_to_url"
go_to_url.description = "Navigate to a specific URL in the browser."


@tool
def click_element(text: str) -> str:
    """Click on an element by its visible text.
    
    Args:
        text: The visible text of the element to click
    """
    try:
        driver = get_driver()
        if driver is None:
            return "Error: Browser not started. Call start_browser first."
        helium.click(text.replace('.','').strip())
        sleep(1.0)
        return f"Clicked on element: {text}"
    except Exception:
        selector = f'//*[contains(@aria-label, "{text.replace('.','').strip()}")]'
        try:

            helium.click(S(selector))
            sleep(1.0)
            return f"Clicked on element containing: {text}"
        except Exception as e:
            return f"Error clicking element: {e}"

click_element.name = "click_element"
click_element.description = "Click on an element by its visible text."

@tool
def click_answer(text: str) -> str:
    """Click on a multiple choice question element by its visible text.
    
    Args:
        text: The visible letter of the multiple choice answer to click
    """
    try:
        driver = get_driver()
        if driver is None:
            return "Error: Browser not started. Call start_browser first."
        helium.click(S(f'//input[@type="radio" and contains(@aria-label, "{text.strip()}")]'))
        sleep(1.0)
        return f"Clicked on answer: {text}"
    except Exception:
        partial_text = text.replace('.','')
        selector = f'//input[@type="radio" and contains(@aria-label, "{text[0]}")]'
        try:

            helium.click(S(selector))
            sleep(1.0)
            return f"Clicked on answer: {text}"
        except Exception as e:
            return f"Error clicking element: {e}"

click_answer.name = "click_answer"
click_answer.description = "Click on a multiple choice answer choice by its corresponding letter."

@tool
def click_link(text: str) -> str:
    """Click on a link by its visible text.
    
    Args:
        text: The visible text of the link to click
    """
    try:
        driver = get_driver()
        if driver is None:
            return "Error: Browser not started. Call start_browser first."
        helium.click(helium.Link(text))
        sleep(1.0)
        return f"Clicked on link: {text}"
    except Exception as e:
        return f"Error clicking link: {e}"

click_link.name = "click_link"
click_link.description = "Click on a link by its visible text."


@tool
def search_item_ctrl_f(text: str, nth_result: int = 1) -> str:
    """Search for text on the current page and jump to the nth occurrence.
    
    Args:
        text: The text to search for on the page
        nth_result: Which occurrence to jump to (1-indexed, default: 1)
    """
    try:
        driver = get_driver()
        if driver is None:
            return "Error: Browser not started. Call start_browser first."
        elements = driver.find_elements(By.XPATH, f"//*[contains(text(), '{text}')]")
        if not elements:
            return f"No matches found for '{text}'"
        if nth_result > len(elements):
            return f"Match #{nth_result} not found (only {len(elements)} matches found)"
        elem = elements[nth_result - 1]
        driver.execute_script("arguments[0].scrollIntoView(true);", elem)
        sleep(0.5)
        return f"Found {len(elements)} matches for '{text}'. Focused on element #{nth_result}"
    except Exception as e:
        return f"Error searching for text: {e}"

search_item_ctrl_f.name = "search_item_ctrl_f"
search_item_ctrl_f.description = "Searches for text on the current page and jumps to the nth occurrence."


@tool
def scroll_down(num_pixels: int = 1200) -> str:
    """Scroll down the page by the specified number of pixels.
    
    Args:
        num_pixels: Number of pixels to scroll down (default: 1200 for one viewport)
    """
    try:
        driver = get_driver()
        if driver is None:
            return "Error: Browser not started. Call start_browser first."
        driver.execute_script(f"window.scrollBy(0, {num_pixels});")
        sleep(0.5)
        return f"Scrolled down {num_pixels} pixels"
    except Exception as e:
        return f"Error scrolling: {e}"

scroll_down.name = "scroll_down"
scroll_down.description = "Scroll down by specified number of pixels."


@tool
def scroll_up(num_pixels: int = 1200) -> str:
    """Scroll up the page by the specified number of pixels.
    
    Args:
        num_pixels: Number of pixels to scroll up (default: 1200 for one viewport)
    """
    try:
        driver = get_driver()
        if driver is None:
            return "Error: Browser not started. Call start_browser first."
        driver.execute_script(f"window.scrollBy(0, -{num_pixels});")
        sleep(0.5)
        return f"Scrolled up {num_pixels} pixels"
    except Exception as e:
        return f"Error scrolling: {e}"

scroll_up.name = "scroll_up"
scroll_up.description = "Scroll up by specified number of pixels."


@tool
def go_back() -> str:
    """Goes back to the previous page."""
    try:
        driver = get_driver()
        if driver is None:
            return "Error: Browser not started. Call start_browser first."
        driver.back()
        sleep(1.0)
        return "Went back to previous page"
    except Exception as e:
        return f"Error going back: {e}"

go_back.name = "go_back"
go_back.description = "Goes back to the previous page."


@tool
def close_popups() -> str:
    """Close any visible modal or pop-up on the page using the Escape key.
    
    Use this tool to dismiss pop-up windows and modal dialogs.
    """
    try:
        driver = get_driver()
        if driver is None:
            return "Error: Browser not started. Call start_browser first."
        webdriver.ActionChains(driver).send_keys(Keys.ESCAPE).perform()
        sleep(0.5)
        return "Sent Escape key to close pop-ups"
    except Exception as e:
        return f"Error closing popups: {e}"

close_popups.name = "close_popups"
close_popups.description = "Closes any visible modal or pop-up on the page using Escape key."


@tool
def get_current_url() -> str:
    """Get the current URL of the browser."""
    try:
        driver = get_driver()
        if driver is None:
            return "Error: Browser not started. Call start_browser first."
        return f"Current URL: {driver.current_url}"
    except Exception as e:
        return f"Error getting URL: {e}"

get_current_url.name = "get_current_url"
get_current_url.description = "Get the current URL of the browser."


def init_browser_tools(agent: "CodeAgent") -> None:
    """Initialize browser tools with a reference to the VisionAgent."""
    global _current_agent
    _current_agent = agent
    # Set up Python environment with necessary imports in the agent
    try:
        agent.python_executor("from helium import *")
    except Exception:
        pass  # Agent may not have python_executor available


# Guidance for the agent on how to use browser tools
HELIUM_INSTRUCTIONS = """
## Interactive Web Browsing Tools Available:

**To start browsing:**
1. Call `start_browser()` to open Chrome
2. Use `go_to_url(url)` to navigate to a website

**To interact with pages:**
- Use `click_element(text)` to click buttons/elements by their visible text
- Use `click_link(text)` to click links
- Use `search_item_ctrl_f(text)` to find text on page and jump to it
- Use `scroll_down(num_pixels)` or `scroll_up(num_pixels)` to scroll
- Use `close_popups()` to dismiss modal windows
- Use `get_current_url()` to check the current page URL
- Use `go_back()` to go back to previous page

**Important tips:**
- The desktop screenshot at .cache/desktop.png updates automatically
- If an action fails, check the error message and try again
- Never try to login to pages
- If you can't find an element, try scrolling first
- Use search_item_ctrl_f to locate text before interacting with it
"""
