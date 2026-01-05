"""
WriteFileTool for smolagents - allows file creation/writing with guardrails.
Restricted to .workspace directory with safety checks for harmful content.
"""
import os
import re
from smolagents import Tool


# Common safe file extensions
ALLOWED_EXTENSIONS = {
    '.py', '.txt', '.md', '.csv', '.json', '.yaml', '.yml',
    '.html', '.css', '.js', '.xml', '.log', '.toml',
    '.ini', '.cfg', '.conf', '.rst', '.tex'
}

# Patterns to detect potentially harmful code
HARMFUL_PATTERNS = [
    # System commands
    r'os\.system\s*\(',
    r'subprocess\.',
    r'eval\s*\(',
    r'exec\s*\(',
    r'__import__\s*\(',
    # File system operations outside scope
    r'os\.remove',
    r'os\.rmdir',
    r'os\.unlink',
    r'shutil\.rmtree',
    # Network operations that could be malicious
    r'socket\.',
    r'urllib\.request',
    # Dangerous imports
    r'import\s+subprocess',
    r'from\s+subprocess',
    r'import\s+os(?:\s|$|,|;|#)',
    r'from\s+os\s+import\b',
    # Additional dangerous patterns
    r'os\.popen\s*\(',
    r'os\.spawn',
    r'compile\s*\(',
    r'importlib'
    r'__builtins__',
]

# Patterns for potentially sensitive data (warning only)
SENSITIVE_PATTERNS = [
    r'password\s*=\s*["\']',
    r'api_key\s*=\s*["\']',
    r'secret\s*=\s*["\']',
    r'token\s*=\s*["\']',
    r'private_key\s*=\s*["\']',
]


class WriteFileSmolTool(Tool):
    """
    File writing tool with guardrails for smolagents CodeAgent.
    
    Allows writing files to the .workspace directory with safety checks:
    - Restricted to .workspace directory
    - Limited to common safe file extensions
    - Scans for potentially harmful code patterns
    - Warns about sensitive data patterns
    """
    
    name = "write_file"
    description = (
        "Write content to a file in the .workspace directory. "
        "Supports common file types: .py, .txt, .md, .csv, .json, .yaml, .html, .js, etc. "
        "Has guardrails to prevent harmful operations. "
        "Use: write_file(filename='myfile.txt', content='file content here', mode='write') "
        "Mode can be 'write' (overwrite) or 'append'."
    )
    inputs = {
        "filename": {
            "type": "string",
            "description": "Name of file to write (will be created in .workspace directory)"
        },
        "content": {
            "type": "string",
            "description": "Content to write to the file"
        },
        "mode": {
            "type": "string",
            "enum": ["write", "append"],
            "description": "Write mode: 'write' (overwrite/create) or 'append' (add to end)",
            "default": "write",
            "nullable": True
        }
    }
    output_type = "string"
    
    def __init__(self, workspace_dir: str = ".workspace"):
        super().__init__()
        self.workspace_dir = os.path.abspath(workspace_dir)
        # Ensure workspace directory exists
        os.makedirs(self.workspace_dir, exist_ok=True)
    
    def _check_filename_safe(self, filename: str) -> tuple[bool, str]:
        """
        Verify filename is safe.
        
        Returns:
            (is_safe, error_message)
        """
        # Remove any directory traversal attempts
        clean_name = os.path.basename(filename)
        if clean_name != filename:
            return False, f"Filename cannot contain path separators. Use '{clean_name}' instead."
        
        # Check extension
        _, ext = os.path.splitext(clean_name) 
        if not ext:
            return False, "Files must have an extension. Allowed extensions: " + ', '.join(sorted(ALLOWED_EXTENSIONS))
        if ext.lower() not in ALLOWED_EXTENSIONS:
            allowed = ', '.join(sorted(ALLOWED_EXTENSIONS))
            return False, f"File extension '{ext}' not allowed. Allowed: {allowed}"
        
        return True, ""
    
    def _scan_content_safety(self, content: str, filename: str) -> tuple[bool, str, list[str]]:
        """
        Scan content for harmful patterns and sensitive data.
        
        Returns:
            (is_safe, error_or_warning, warnings_list)
        """
        warnings = []
        
        # Only scan Python files for code-related patterns
        _, ext = os.path.splitext(filename)
        if ext == '.py':
            # Check for harmful patterns
            for pattern in HARMFUL_PATTERNS:
                if re.search(pattern, content, re.IGNORECASE | re.MULTILINE):
                    return False, f"Content contains potentially harmful pattern: {pattern}", []
        
        # Check for sensitive data (warning only, not blocking)
        for pattern in SENSITIVE_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                warnings.append(f"Warning: Content may contain sensitive data matching pattern: {pattern}")
        
        return True, "", warnings
    
    def forward(
        self,
        filename: str,
        content: str,
        mode: str = "write"
    ) -> str:
        """
        Write content to a file in the workspace directory.
        
        Args:
            filename: Name of the file to write
            content: Content to write to the file
            mode: 'write' (overwrite/create) or 'append'
        
        Returns:
            Success message or error description
        """
        try:
            # Require valid mode
            if mode not in ("write", "append"):
                return f"Error: Invalid mode '{mode}'. Must be 'write' or 'append'."
            
            # Validate filename
            is_safe, error_msg = self._check_filename_safe(filename)
            if not is_safe:
                return f"Error: {error_msg}"
            
            # Scan content for safety
            is_safe, error_msg, warnings = self._scan_content_safety(content, filename)
            if not is_safe:
                return f"Error: {error_msg}"
            
            # Construct full path
            filepath = os.path.join(self.workspace_dir, filename)
            
            # Ensure we're still within workspace (double-check, resolve symlinks)
            real_path = os.path.realpath(filepath)
            workspace_real = os.path.realpath(self.workspace_dir)
            if not real_path.startswith(workspace_real):
                return f"Error: Path '{filepath}' resolves outside workspace directory"
            
            # Write file
            file_mode = 'a' if mode == 'append' else 'w'
            with open(filepath, file_mode, encoding='utf-8') as f:
                f.write(content)
            
            # Build response
            action_word = "Appended to" if mode == 'append' else "Wrote"
            size = len(content)
            response = f"{action_word} file: {filepath} ({size} characters)"
            
            # Add warnings if any
            if warnings:
                response += "\n\n" + "\n".join(warnings)
            
            return response
            
        except PermissionError as e:
            return f"Error: Permission denied - {str(e)}"
        except OSError as e:
            return f"Error: File operation failed - {str(e)}"
        except Exception as e:
<<<<<<< HEAD
            return f"Error: Unexpected error while writing file - {str(e)}"
=======
            return f"Error: Unexpected error while writing file - {str(e)}"
>>>>>>> main
