# Custom Model Guide

This guide explains how to use custom Ollama models with Nayu_AI and the improvements made to handle custom models better.

## Problem

When using custom models created with `ollama create`, especially models not specifically fine-tuned for function calling, the agent was generating inappropriate responses like test code instead of normal conversational responses.

Example issue:
```
User: Hello
Agent: ' in the document
    assert doc.find_word('Hello') == True, "Test 1 Failed: 'Hello' should be found"
    ...
```

## Root Cause

The issue was caused by:
1. **Overly strict tool-calling prompt**: The system prompt forced JSON-only responses but didn't clearly explain when to chat vs when to use tools
2. **Lack of conversational guidance**: The prompts didn't emphasize that normal chat should be the default behavior
3. **Hardcoded model name**: The model name was hardcoded in the source, requiring code changes to use custom models

## Solution

### 1. Improved Tool-Calling Prompt

The `TOOL_CALLING_PROMPT_TEMPLATE` in `src/agents/llm/ollama_client.py` has been completely rewritten to:
- Clearly distinguish between conversational responses and tool calls
- Provide explicit guidance on when to use each format
- Add examples of both response types
- Include a decision rule: "Think: Does this REQUIRE a tool, or can I just chat?"
- Explicitly warn against generating code/tests unless asked

### 2. Enhanced System Prompt

The `SYSTEM_PROMPT` in `src/agents/base_agent.py` now:
- Emphasizes being "helpful, friendly" and prioritizes natural conversation
- Explicitly states to only use tools when specifically required
- Warns against generating code examples, tests, or documentation unless requested
- Includes the decision rule: "Can I answer this directly, or do I need a tool?"

### 3. Configurable Model Name

The main LLM model is now configurable via the `AGENT_MODEL` environment variable, so you don't need to modify the source code.

## Using a Custom Model

### Step 1: Create Your Custom Model

```bash
# Create your custom model with Ollama using a Modelfile
ollama create my-custom-model -f Modelfile

# Or from a GGUF file (create a temporary Modelfile first)
echo "FROM /path/to/your-model.gguf" > /tmp/Modelfile
ollama create my-custom-model -f /tmp/Modelfile
```

### Step 2: Set the Environment Variable

```bash
# Set the model name
export AGENT_MODEL=my-custom-model

# Or on the command line
AGENT_MODEL=my-custom-model python -m src.app
```

### Step 3: Run the Application

```bash
# Via make
AGENT_MODEL=my-custom-model make run

# Or directly
AGENT_MODEL=my-custom-model python -m src.app
```

## Testing Your Model

A test script is provided to validate that your model responds appropriately:

```bash
# Test with the default model
python test_llm_response.py

# Test with your custom model
AGENT_MODEL=my-custom-model python test_llm_response.py
```

The test validates:
1. **Conversational responses**: Simple greetings should return `{"text": "..."}` without code
2. **Tool calling**: Requests requiring tools should return `{"tool_call": {...}}`
3. **No tools available**: Should handle gracefully with text responses

## Expected Behavior

### Good Responses

**User: "Hello"**
```json
{"text": "Hello! How can I help you today?"}
```

**User: "What's the weather?"**
```json
{"text": "I don't have access to real-time weather data, but I can search the web for you if you'd like. Just let me know your location!"}
```

**User: "Search the web for Python tutorials"**
```json
{"tool_call": {"name": "webbrowser", "arguments": {"action": "search", "query": "Python tutorials"}}}
```

### Bad Responses (What We Fixed)

❌ Generating test code for simple greetings
❌ Echoing internal system details to users
❌ Writing documentation when just asked to chat
❌ Calling tools unnecessarily for simple questions

## Model Recommendations

For best results with custom models:
1. **Context size**: Use at least 8000 tokens (12000 recommended)
2. **Quantization**: Q4_K_M or Q5_K_M work well for 7-8B models
3. **Temperature**: 0.2-0.3 for more consistent responses
4. **Training**: If fine-tuning, include examples of:
   - Normal conversational exchanges
   - Proper JSON response formatting
   - Tool calling examples

## Troubleshooting

### Model generates code/tests for simple chat
- Make sure you're using the latest version with the improved prompts
- Check that the model supports instruction following
- Try a lower temperature (0.1-0.2)

### Model doesn't call tools when needed
- Some models may need more explicit tool-calling training
- The prompts now accept text responses gracefully
- Consider using a model specifically trained for function calling (e.g., qwen2:7b-instruct, llama3.1:8b-instruct)

### Model name not found
- Make sure your custom model is created in Ollama: `ollama list`
- Check the exact name matches: `ollama show my-custom-model`
- Ensure Ollama is running: `ollama serve`

## Environment Variables Summary

```bash
# Main LLM model name
export AGENT_MODEL=my-custom-model

# Dashboard settings
export AGENT_DASH_HOST=0.0.0.0
export AGENT_DASH_PORT=8008

# Optional TTS settings (use .pt for best performance)
export TTS_REF_AUDIO=/path/to/reference.pt  # or reference.wav
export TTS_REF_TEXT="The transcript of the reference audio"
```

## Further Customization

If you need to further customize the prompts:
- `src/agents/base_agent.py`: Edit `SYSTEM_PROMPT` for overall behavior
- `src/agents/llm/ollama_client.py`: Edit `TOOL_CALLING_PROMPT_TEMPLATE` for JSON response format

Remember to restart the application after changing Python files.
