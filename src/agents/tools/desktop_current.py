"""
Desktop screenshot capture module with clean OOP design.
Provides periodic desktop screenshot capture with atomic file writes.
"""
import time
import os
import threading
from typing import Optional, Callable

try:
    import mss
    from PIL import Image
    SCREENSHOT_AVAILABLE = True
except ImportError:
    SCREENSHOT_AVAILABLE = False


class ScreenshotCaptureError(Exception):
    """Base exception for screenshot capture errors."""
    pass


class DesktopCurrentCapture:
    """Handle periodic desktop screenshot capture to a single desktop.png file."""
    
    SCREENSHOT_FILENAME = "desktop.png"
    
    def __init__(
        self,
        interval: float = 2.0,
        output_dir: str = ".cache",
        error_callback: Optional[Callable[[str], None]] = None,
    ):
        """
        Initialize capture handler.
        
        Args:
            interval: Capture interval in seconds (default 2.0)
            output_dir: Directory to save screenshots (default .cache)
            error_callback: Optional callback for error reporting
        """
        if not SCREENSHOT_AVAILABLE:
            raise ScreenshotCaptureError(
                "MSS/PIL not available. Install with: pip install mss Pillow"
            )
        
        self.interval = interval
        self.output_dir = output_dir
        self._error_callback = error_callback
        self._output_path = os.path.join(output_dir, self.SCREENSHOT_FILENAME)
        
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Periodic capture state
        self._capture_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._state_lock = threading.Lock()
        self._is_running = False
    
    def _capture_screenshot(self) -> str:
        """
        Capture a screenshot and save to the persistent desktop.png file.
        Uses atomic writes to prevent partial/corrupted files.
        
        Returns:
            Path to the captured screenshot
            
        Raises:
            ScreenshotCaptureError: If capture fails
        """
        try:
            with mss.mss() as sct:
                shot = sct.grab(sct.monitors[1])
                img = Image.frombytes("RGB", shot.size, shot.rgb)
            
            # Atomic write: save to temp file, then replace
            tmp_path = f"{self._output_path}.tmp"
            img.save(tmp_path)
            os.replace(tmp_path, self._output_path)
            
            return self._output_path
        except Exception as e:
            raise ScreenshotCaptureError(f"Failed to capture screenshot: {e}")
    
    def _capture_loop(self) -> None:
        """Background loop for periodic screenshot capture."""
        while not self._stop_event.is_set():
            try:
                self._capture_screenshot()
            except ScreenshotCaptureError as e:
                if self._error_callback:
                    self._error_callback(str(e))
            
            # Wait for interval or until stop is signaled
            self._stop_event.wait(self.interval)
        
        # Mark as not running when loop exits
        with self._state_lock:
            self._is_running = False
    
    def start(self) -> str:
        """
        Start periodic screenshot capture.
        
        Returns:
            Status message
        """
        with self._state_lock:
            if self._is_running:
                return f"Periodic capture already running (interval={self.interval}s)"
            
            self._is_running = True
            self._stop_event.clear()
        
        self._capture_thread = threading.Thread(
            target=self._capture_loop,
            name="desktop_current_capture",
            daemon=True,
        )
        self._capture_thread.start()
        return f"Started periodic screenshot capture (interval={self.interval}s)"
    
    def stop(self) -> str:
        """
        Stop periodic screenshot capture.
        
        Returns:
            Status message
        """
        with self._state_lock:
            if not self._is_running:
                return "Periodic capture not running"
        
        self._stop_event.set()
        if self._capture_thread and self._capture_thread.is_alive():
            self._capture_thread.join(timeout=3.0)
        
        return "Stopped periodic screenshot capture"
    
    def capture_now(self) -> str:
        """
        Capture a single screenshot immediately and update desktop.png.
        
        Returns:
            Path to the captured screenshot or error message
        """
        try:
            return self._capture_screenshot()
        except ScreenshotCaptureError as e:
            if self._error_callback:
                self._error_callback(str(e))
            return f"Error: {e}"
    
    def is_running(self) -> bool:
        """Check if periodic capture is active."""
        with self._state_lock:
            return self._is_running
    
    def get_screenshot_path(self) -> str:
        """Get the path to the current desktop.png screenshot."""
        return self._output_path
