# Vision Tool Fix - Qwen2-VL Token Mismatch Error

## Issue
When using the vision tool to analyze images (particularly screenshots from the desktop tool), the following error occurred:

```
vision failed: Image features and image tokens do not match: tokens: 0, features 2691
```

## Root Cause
The vision tool was using an outdated API for the Qwen2-VL processor. The old implementation directly passed text and images to the processor:

```python
inputs = processor(text=prompt, images=image, return_tensors="pt")
```

This approach doesn't properly format the input for Qwen2-VL-2B-Instruct models, which expect a specific chat template format where images and text are structured as conversation messages.

## Solution
The fix updates the vision tool to use the correct Qwen2-VL chat template API:

### New Implementation
```python
# 1. Structure the input as a conversation message
messages = [
    {
        "role": "user",
        "content": [
            {"type": "image", "image": image},  # PIL Image object
            {"type": "text", "text": prompt}
        ]
    }
]

# 2. Apply the chat template to format the conversation
text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)

# 3. Process with the formatted text and image
inputs = processor(text=[text], images=[image], return_tensors="pt")
```

### Key Changes
1. **Message Structure**: Input is now structured as a conversation with explicit content types
2. **Chat Template**: Uses `apply_chat_template()` to properly format the conversation
3. **List Wrapping**: Text and images are wrapped in lists for consistent batching
4. **Image Object**: Uses PIL Image object directly for better consistency

## Impact
- ✅ Fixes the "Image features and image tokens do not match" error
- ✅ Enables proper image analysis workflow: `desktop screenshot → vision describe`
- ✅ Aligns with official Qwen2-VL model usage patterns
- ✅ Maintains backward compatibility with existing code

## Testing Recommendations
After this fix, you should be able to:

1. Take a screenshot using the desktop tool:
   ```json
   {"tool_call": {"name": "desktop", "arguments": {"action": "screenshot"}}}
   ```

2. Analyze the screenshot with the vision tool:
   ```json
   {"tool_call": {"name": "vision", "arguments": {"path": ".cache/screenshot_XXXXX.png"}}}
   ```

3. The vision tool should return a description without errors

## References
- [Qwen2-VL Model Card](https://huggingface.co/Qwen/Qwen2-VL-2B-Instruct)
- [Transformers Vision Language Documentation](https://huggingface.co/docs/transformers/main/en/model_doc/qwen2_vl)

## Related Files
- `src/agents/tools/vision.py` - Vision tool implementation
- `src/agents/tools/desktop.py` - Desktop tool (screenshot functionality)
- `src/agents/main_agent.py` - Main agent orchestrator
