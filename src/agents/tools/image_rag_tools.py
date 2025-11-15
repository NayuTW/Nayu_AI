"""
Smolagents-compatible tool wrappers for the ImageRAG system.
These tools expose the ImageRAG functionality to the main agent.
"""
import os
import json
from typing import Optional
from smolagents import Tool

from src.agents.vision.image_rag import ImageRAG


class ImageIndexTool(Tool):
    """Index an image for later search using CLIP embeddings and OCR."""
    
    name = "image_index"
    description = (
        "Index an image (screenshot or file) for later search. "
        "This creates CLIP embeddings and runs OCR to enable fast similarity search. "
        "Use this before calling image_search on a new image."
    )
    inputs = {
        "image_path": {
            "type": "string",
            "description": "Full path to the image file to index"
        },
        "action_id": {
            "type": "string",
            "description": "Optional action identifier for tracking",
            "nullable": True
        }
    }
    output_type = "string"
    
    def __init__(self, image_rag: Optional[ImageRAG] = None):
        super().__init__()
        self.image_rag = image_rag
    
    def forward(self, image_path: str, action_id: Optional[str] = None) -> str:
        """Index the image and return result."""
        if not self.image_rag:
            return "Error: ImageRAG system not initialized"
        
        if not image_path or not image_path.strip():
            return "Error: image_path parameter is required and cannot be empty"
        
        if not os.path.exists(image_path):
            return f"Error: Image file not found at path: {image_path}"
        
        try:
            result = self.image_rag.index_image(image_path, action_id)
            return json.dumps(result, indent=2)
        except Exception as e:
            return f"Error indexing image: {str(e)}"


class ImageSearchTool(Tool):
    """Search indexed images using natural language questions."""
    
    name = "image_search"
    description = (
        "Search indexed images using a natural language question. "
        "Returns relevant regions with OCR text and similarity scores. "
        "Use this to find specific content in screenshots without running a VLM."
    )
    inputs = {
        "question": {
            "type": "string",
            "description": "Natural language question about the image content"
        },
        "image_id": {
            "type": "string",
            "description": "Optional image ID to search within a specific image",
            "nullable": True
        },
        "k": {
            "type": "integer",
            "description": "Number of results to return (default: 6)",
            "nullable": True
        }
    }
    output_type = "string"
    
    def __init__(self, image_rag: Optional[ImageRAG] = None):
        super().__init__()
        self.image_rag = image_rag
    
    def forward(self, question: str, image_id: Optional[str] = None, k: Optional[int] = None) -> str:
        """Search for relevant image regions."""
        if not self.image_rag:
            return "Error: ImageRAG system not initialized"
        
        if not question or not question.strip():
            return "Error: question parameter is required and cannot be empty"
        
        try:
            k_val = k if k is not None else 6
            result = self.image_rag.search(question, image_id, k_val)
            return json.dumps(result, indent=2)
        except Exception as e:
            return f"Error searching images: {str(e)}"


class ImageCompareTool(Tool):
    """Compare two images to find differences in text and content."""
    
    name = "image_compare"
    description = (
        "Compare two images to find differences. "
        "Returns added and removed text detected via OCR. "
        "Useful for detecting changes after an action (e.g., before/after click)."
    )
    inputs = {
        "image_a": {
            "type": "string",
            "description": "Path to the first image (before)"
        },
        "image_b": {
            "type": "string",
            "description": "Path to the second image (after)"
        }
    }
    output_type = "string"
    
    def __init__(self, image_rag: Optional[ImageRAG] = None):
        super().__init__()
        self.image_rag = image_rag
    
    def forward(self, image_a: str, image_b: str) -> str:
        """Compare two images and return differences."""
        if not self.image_rag:
            return "Error: ImageRAG system not initialized"
        
        if not image_a or not image_a.strip():
            return "Error: image_a parameter is required and cannot be empty"
        
        if not image_b or not image_b.strip():
            return "Error: image_b parameter is required and cannot be empty"
        
        if not os.path.exists(image_a):
            return f"Error: Image A not found at path: {image_a}"
        
        if not os.path.exists(image_b):
            return f"Error: Image B not found at path: {image_b}"
        
        try:
            result = self.image_rag.compare_images(image_a, image_b)
            return json.dumps(result, indent=2)
        except Exception as e:
            return f"Error comparing images: {str(e)}"


class ImageFindUITool(Tool):
    """Find UI elements by description using a prototype library."""
    
    name = "image_find_ui"
    description = (
        "Find UI elements (buttons, icons, etc.) by description. "
        "Searches a library of previously seen UI elements. "
        "Returns matching elements with bounding boxes and confidence scores."
    )
    inputs = {
        "query": {
            "type": "string",
            "description": "Description of the UI element to find (e.g., 'close button', 'settings icon')"
        },
        "k": {
            "type": "integer",
            "description": "Number of matches to return (default: 5)",
            "nullable": True
        }
    }
    output_type = "string"
    
    def __init__(self, image_rag: Optional[ImageRAG] = None):
        super().__init__()
        self.image_rag = image_rag
    
    def forward(self, query: str, k: Optional[int] = None) -> str:
        """Find UI elements matching the query."""
        if not self.image_rag:
            return "Error: ImageRAG system not initialized"
        
        if not query or not query.strip():
            return "Error: query parameter is required and cannot be empty"
        
        try:
            k_val = k if k is not None else 5
            result = self.image_rag.find_ui(query, k_val)
            return json.dumps(result, indent=2)
        except Exception as e:
            return f"Error finding UI elements: {str(e)}"
