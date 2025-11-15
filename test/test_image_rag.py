"""
Test script to verify ImageRAG implementation code structure.
This test validates the code changes without requiring external dependencies.
"""
import os
import sys
import ast

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def test_file_exists(filepath, description):
    """Test that a file exists."""
    print(f"Testing {description}...")
    if not os.path.exists(filepath):
        print(f"  ✗ File not found: {filepath}")
        return False
    print(f"  ✓ File exists: {filepath}")
    return True

def test_class_exists(filepath, classname):
    """Test that a class exists in a file."""
    print(f"Testing class {classname} exists in {filepath}...")
    try:
        with open(filepath, 'r') as f:
            tree = ast.parse(f.read())
        
        classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
        if classname in classes:
            print(f"  ✓ Class {classname} found")
            return True
        else:
            print(f"  ✗ Class {classname} not found")
            return False
    except Exception as e:
        print(f"  ✗ Error parsing file: {e}")
        return False

def test_function_exists(filepath, funcname):
    """Test that a function exists in a file."""
    print(f"Testing function {funcname} exists in {filepath}...")
    try:
        with open(filepath, 'r') as f:
            tree = ast.parse(f.read())
        
        # Get top-level functions (not methods)
        functions = [node.name for node in tree.body if isinstance(node, ast.FunctionDef)]
        if funcname in functions:
            print(f"  ✓ Function {funcname} found")
            return True
        else:
            print(f"  ✗ Function {funcname} not found")
            return False
    except Exception as e:
        print(f"  ✗ Error parsing file: {e}")
        return False

def test_method_exists(filepath, classname, methodname):
    """Test that a method exists in a class."""
    print(f"Testing method {classname}.{methodname} exists...")
    try:
        with open(filepath, 'r') as f:
            tree = ast.parse(f.read())
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == classname:
                methods = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
                if methodname in methods:
                    print(f"  ✓ Method {methodname} found in {classname}")
                    return True
        
        print(f"  ✗ Method {methodname} not found in {classname}")
        return False
    except Exception as e:
        print(f"  ✗ Error parsing file: {e}")
        return False

def test_requirements_updated():
    """Test that requirements.txt includes new dependencies."""
    print("Testing requirements.txt updated...")
    try:
        with open("requirements.txt", 'r') as f:
            content = f.read()
        
        has_open_clip = "open_clip_torch" in content
        has_rapidocr = "rapidocr" in content
        
        if has_open_clip and has_rapidocr:
            print("  ✓ Requirements.txt includes open_clip_torch and rapidocr")
            return True
        else:
            missing = []
            if not has_open_clip:
                missing.append("open_clip_torch")
            if not has_rapidocr:
                missing.append("rapidocr")
            print(f"  ✗ Requirements.txt missing: {', '.join(missing)}")
            return False
    except Exception as e:
        print(f"  ✗ Error reading requirements.txt: {e}")
        return False

def test_main_agent_imports():
    """Test that main_agent_smol.py imports ImageRAG components."""
    print("Testing main_agent_smol.py imports...")
    try:
        with open("src/agents/main_agent_smol.py", 'r') as f:
            content = f.read()
        
        has_rag_tools = "from src.agents.tools.image_rag_tools import" in content
        has_rag_class = "from src.agents.vision.image_rag import ImageRAG" in content
        
        if has_rag_tools and has_rag_class:
            print("  ✓ main_agent_smol.py imports ImageRAG components")
            return True
        else:
            print("  ✗ main_agent_smol.py missing ImageRAG imports")
            return False
    except Exception as e:
        print(f"  ✗ Error reading main_agent_smol.py: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("ImageRAG Implementation Code Structure Test")
    print("=" * 60)
    print()
    
    results = []
    
    # Test core module files exist
    results.append(test_file_exists("src/agents/vision/__init__.py", "vision module init"))
    results.append(test_file_exists("src/agents/vision/image_rag.py", "image_rag module"))
    results.append(test_file_exists("src/agents/tools/image_rag_tools.py", "image_rag_tools module"))
    
    # Test core classes exist
    results.append(test_class_exists("src/agents/vision/image_rag.py", "CLIPEncoder"))
    results.append(test_class_exists("src/agents/vision/image_rag.py", "ImageRAG"))
    
    # Test core functions exist
    results.append(test_function_exists("src/agents/vision/image_rag.py", "_device"))
    results.append(test_function_exists("src/agents/vision/image_rag.py", "_tiles"))
    
    # Test ImageRAG methods exist
    results.append(test_method_exists("src/agents/vision/image_rag.py", "ImageRAG", "index_image"))
    results.append(test_method_exists("src/agents/vision/image_rag.py", "ImageRAG", "search"))
    results.append(test_method_exists("src/agents/vision/image_rag.py", "ImageRAG", "compare_images"))
    results.append(test_method_exists("src/agents/vision/image_rag.py", "ImageRAG", "find_ui"))
    results.append(test_method_exists("src/agents/vision/image_rag.py", "ImageRAG", "add_ui_prototype"))
    
    # Test tool classes exist
    results.append(test_class_exists("src/agents/tools/image_rag_tools.py", "ImageIndexTool"))
    results.append(test_class_exists("src/agents/tools/image_rag_tools.py", "ImageSearchTool"))
    results.append(test_class_exists("src/agents/tools/image_rag_tools.py", "ImageCompareTool"))
    results.append(test_class_exists("src/agents/tools/image_rag_tools.py", "ImageFindUITool"))
    
    # Test requirements and integration
    results.append(test_requirements_updated())
    results.append(test_main_agent_imports())
    
    # Summary
    print()
    print("=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(results)
    total = len(results)
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ All code structure tests passed!")
        sys.exit(0)
    else:
        print("\n✗ Some tests failed")
        sys.exit(1)
