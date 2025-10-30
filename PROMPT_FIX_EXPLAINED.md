# Prompt Fix Explained: Why the First Fix Didn't Work

## The Problem After Initial Fix

Even after improving the prompts, users still reported the agent generating code for simple greetings:

```
User: Hello
Agent: [Java Spring Boot controller code]
```

## Root Cause: Conflicting System Messages

### What Was Happening (BEFORE this fix)

```python
# In main_agent.py
messages = [
    {"role": "system", "content": SYSTEM_PROMPT},  # "Be conversational..."
    {"role": "system", "content": f"Context: {context}"},
    {"role": "user", "content": "Hello"}
]

# In ollama_client.py - PREPENDED another system message
sys_aug = [{"role": "system", "content": tool_calling_prompt}]  # "Output JSON..."
payload["messages"] = sys_aug + messages  # Prepended!
```

**Actual message order sent to Ollama:**
```
1. system: "You must output ONLY JSON..." (tool-calling format)
2. system: "Be conversational and friendly..." (conversational behavior)
3. system: "Context: ..."
4. user: "Hello"
```

**Problem:** Model sees conflicting instructions and prioritizes the first one (JSON format) over being conversational!

## The Fix: Unified System Prompt

### What Happens Now (AFTER this fix)

```python
# In main_agent.py - ONE unified prompt
SYSTEM_PROMPT_WITH_TOOLS = """
You are a helpful, friendly AI assistant.

RESPONSE FORMAT - You MUST respond using ONLY valid JSON:
1. For normal conversation: {"text": "your conversational response"}
2. For tools: {"tool_call": {"name": "...", "arguments": {...}}}

CRITICAL RULES:
- DEFAULT to conversation: For "Hello", "How are you", etc. → use {"text": "..."}
- Do NOT generate code in your {"text": "..."} responses

EXAMPLES:
- User: "Hello" → {"text": "Hello! How can I help you today?"}
- User: "Search Python tutorials" → {"tool_call": {...}}
"""

# In ollama_client.py - APPEND tools to existing prompt
if tool_spec:
    modified_content = msg["content"] + f"\n\nAVAILABLE TOOLS:\n{tool_str}"
```

**Actual message order sent to Ollama:**
```
1. system: "You are helpful... DEFAULT to conversation... Examples: 'Hello' → {"text": "..."} ... TOOLS: [...]"
2. system: "Context: ..."
3. user: "Hello"
```

**Benefit:** Model gets ONE clear, unified instruction without conflicts!

## Key Improvements in the Unified Prompt

### 1. Explicit Default Behavior
```
CRITICAL RULES:
- DEFAULT to conversation: For "Hello", "How are you", questions, etc. → use {"text": "..."}
```

### 2. Concrete Examples
```
WHEN TO USE EACH FORMAT:
- User: "Hello" → {"text": "Hello! How can I help you today?"}
- User: "What's the weather?" → {"text": "I don't have real-time weather data..."}
- User: "Search for Python tutorials" → {"tool_call": {...}}
```

### 3. Explicit Anti-Code Instruction
```
- Do NOT generate code, tests, examples, or documentation in your {"text": "..."} responses
```

## Visual Comparison

### Before (Conflicting Prompts)
```
┌─────────────────────────────────┐
│ System Msg 1: "Output JSON"     │ ← Model focuses here!
├─────────────────────────────────┤
│ System Msg 2: "Be conversational"│ ← Ignored or lower priority
├─────────────────────────────────┤
│ System Msg 3: "Context..."      │
├─────────────────────────────────┤
│ User: "Hello"                   │
└─────────────────────────────────┘
Result: {"text": "public class Hello..."} ❌
```

### After (Unified Prompt)
```
┌─────────────────────────────────┐
│ System Msg 1:                   │
│  • "Be conversational"          │
│  • "DEFAULT to conversation"    │
│  • "Format: JSON"               │
│  • "Example: Hello → {text:..}" │
│  • "Available tools: [...]"     │
├─────────────────────────────────┤
│ System Msg 2: "Context..."      │
├─────────────────────────────────┤
│ User: "Hello"                   │
└─────────────────────────────────┘
Result: {"text": "Hello! How can I help?"} ✅
```

## Why This Works

1. **No conflicts**: Model gets one coherent instruction set
2. **Clear priority**: "DEFAULT to conversation" stated upfront
3. **Concrete examples**: Shows exactly what to do for "Hello"
4. **Format integrated**: JSON format is presented as a wrapper for conversation, not the primary goal

## Testing the Fix

```bash
# Run the test
python test_greeting_response.py

# Expected output:
✓ Response format: Conversational text (correct)
✓ Response content: No code generation (correct)
✓ TEST PASSED: Agent responds conversationally to greetings
```

## Summary

The first fix improved the prompt content but didn't fix the architectural issue of having **multiple conflicting system messages**. This second fix addresses the root cause by:

1. ✅ Creating ONE unified system prompt in main_agent.py
2. ✅ Removing the conflicting prompt prepending in ollama_client.py
3. ✅ Making conversation the explicit DEFAULT behavior
4. ✅ Providing concrete examples inline with the format instructions

This ensures the model receives clear, unified guidance without contradictory instructions.
