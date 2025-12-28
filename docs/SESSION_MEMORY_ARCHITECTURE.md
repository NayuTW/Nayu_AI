# Session Memory Architecture

## Overview

This document describes the technical architecture of the session memory system.

## Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLI Interface                            │
│  (src/app.py)                                                    │
│  - Displays session ID on startup                                │
│  - /reset-session command                                        │
│  - /sessions command                                             │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                    MainAgent                                    │
│  (src/agents/sub_agents/main_agent.py)                          │
│  - Initializes SessionManager                                    │
│  - Assembles context from session, working set, and messages    │
│  - Persists user and assistant messages                         │
│  - Updates working set after tool calls                         │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                   SessionManager                                 │
│  (src/agents/memory/session_manager.py)                         │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  In-Memory LRU Cache                                     │   │
│  │  - Hot sessions kept in memory                           │   │
│  │  - Max 10 sessions by default                            │   │
│  │  - Write-through to disk                                 │   │
│  └─────────────────────────────────────────────────────────┘   │
│                       │                                          │
│                       ▼                                          │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  SessionState                                            │   │
│  │  - messages: List[Message]                               │   │
│  │  - summary: str (auto-generated every N turns)           │   │
│  │  - working_set: WorkingSet                               │   │
│  │  - turn_count: int                                       │   │
│  └─────────────────────────────────────────────────────────┘   │
│                       │                                          │
│                       ▼                                          │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Rolling Window Logic                                    │   │
│  │  - Truncate oldest messages first                        │   │
│  │  - Keep within max_messages (20) and max_tokens (4096)  │   │
│  │  - Preserve at least 5 most recent messages             │   │
│  └─────────────────────────────────────────────────────────┘   │
│                       │                                          │
│                       ▼                                          │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Summary Generator                                       │   │
│  │  - Triggered every summary_interval turns (default: 5)   │   │
│  │  - Extracts recent user intents                          │   │
│  │  - Keeps summary under 512 chars                         │   │
│  └─────────────────────────────────────────────────────────┘   │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                 Disk Persistence                                 │
│  (.nayu_ai/sessions/<session_id>.json)                          │
│                                                                  │
│  {                                                               │
│    "session_id": "session-1730626431-a4b2f3e1",                │
│    "messages": [                                                │
│      {"role": "user", "content": "...", "timestamp": ...},     │
│      {"role": "assistant", "content": "...", ...}              │
│    ],                                                           │
│    "summary": "Recent topics: ...",                            │
│    "working_set": {                                            │
│      "last_task": {...},                                       │
│      "artifacts": {"last_file": "report.txt", ...},           │
│      "env_context": {...}                                      │
│    },                                                           │
│    "turn_count": 5,                                            │
│    "last_updated": 1730626431.123                              │
│  }                                                              │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow

### User Input Flow

```
1. User enters message in CLI
   ↓
2. MainAgentSmol.handle_user_message()
   ↓
3. SessionManager.get_context(session_id)
   - Returns: (summary, working_set, messages)
   ↓
4. Assemble prompt with:
   - System prompt
   - OS context
   - Session summary
   - Working set
   - Recent messages
   - Current user input
   ↓
5. Send to LLM (CodeAgent)
   ↓
6. Receive agent response
   ↓
7. SessionManager.add_message() × 2
   - Add user message
   - Add assistant message
   ↓
8. SessionManager.update_working_set() (if needed)
   - Update artifacts (files, URLs)
   - Update task info
   ↓
9. Automatic processing:
   - Truncate if exceeding limits
   - Generate summary if at interval
   - Persist to disk (write-through)
```

### Session Reset Flow

```
1. User types /reset-session
   ↓
2. MainAgentSmol.reset_session()
   ↓
3. SessionManager.reset_session(session_id)
   - Remove from cache
   - Delete JSON file from disk
   ↓
4. Next message creates fresh session
```

## Context Assembly Example

Given this conversation:
```
User: Open the file report.txt
Agent: I've opened report.txt for you.
User: What's in that file?
```

The assembled context looks like:
```
SYSTEM_PROMPT: You are a helpful AI assistant...
OS_CONTEXT: Running on Ubuntu 22.04...

CONTEXT: [SharedState fields]

SESSION SUMMARY:
Recent topics: Open the file report.txt

WORKING SET:
Last task: file_open - success
Artifacts: last_file=report.txt

RECENT CONVERSATION:
User: Open the file report.txt
Assistant: I've opened report.txt for you.

MESSAGE SOURCE: cli

USER MESSAGE:
What's in that file?

Respond naturally. You can reference previous messages and artifacts.
```

The agent can now understand that "that file" refers to "report.txt" from:
1. Working set artifact: `last_file=report.txt`
2. Recent conversation context
3. Task information

## Performance Characteristics

| Operation | Time | Memory | Disk I/O |
|-----------|------|--------|----------|
| Get context | <1ms | ~2KB per session | Read JSON |
| Add message | <5ms | ~0.5KB per message | Write JSON |
| Truncate window | <1ms | -1KB per removed message | - |
| Generate summary | <1ms | ~200 bytes | - |
| Flush cache | <10ms | Releases cache | Write all |
| Reset session | <5ms | Frees memory | Delete JSON |

## Token Budget

Default configuration:
- **Max messages**: 20 (10 user + 10 assistant)
- **Max tokens**: ~4096 (approximate)
- **Token estimation**: 1 token ≈ 4 characters

Typical prompt size with session context:
- System prompt: ~300 tokens
- Session summary: ~100-200 tokens
- Working set: ~50-100 tokens
- Recent messages (10): ~500-1000 tokens
- Current user message: ~50-200 tokens
- **Total**: ~1000-1800 tokens

This leaves plenty of room for LLM response (~2000-3000 tokens).

## Extensibility Points

### Custom Summary Generation

Replace `_generate_summary()` with LLM-based summarization:
```python
def _generate_summary(self, state: SessionState):
    # Use LLM to generate better summaries
    prompt = f"Summarize this conversation: {state.messages[-10:]}"
    summary = llm.generate(prompt)
    state.summary = summary
```

### Automatic Working Set Updates

Extract artifacts from tool calls:
```python
# After tool call in src/agents/sub_agents/main_agent.py
if tool_name == "webbrowser" and "url" in tool_result:
    self.update_working_set(
        session_id=session_id,
        artifacts={"last_url": tool_result["url"]}
    )
```

### Multi-User Sessions

Use channel_id or user_id as session key:
```python
# For Discord
session_id = f"discord-{channel_id}"
# For multi-user CLI
session_id = f"user-{username}"
```

### Semantic Message Pruning

Replace oldest-first truncation with relevance-based:
```python
def _truncate_messages(self, state: SessionState):
    # Keep most relevant messages instead of just recent
    embeddings = self.embed_messages(state.messages)
    scores = self.relevance_scores(embeddings, current_query)
    state.messages = keep_top_k(state.messages, scores, k=20)
```

## Testing Strategy

| Test Type | Coverage | File |
|-----------|----------|------|
| Unit tests | SessionManager API | test_session_memory.py |
| Integration | Agent workflow | test_integration_memory.py |
| End-to-end | Complete flow | test_e2e_session.py |
| Manual | CLI simulation | test_cli_manual.py |

All tests run independently without requiring:
- Ollama / LLM
- Network access
- External services

## Security Considerations

1. **File paths**: Session files are created in `.nayu_ai/sessions/` with sanitized IDs
2. **No sensitive data**: Sessions should not store API keys or credentials
3. **Access control**: Sessions are filesystem-based; use OS permissions for security
4. **Size limits**: Max messages and token limits prevent unbounded growth

## Migration Path

If upgrading from a version without session memory:
1. Sessions are created automatically on first use
2. No database migration needed
3. Old fine-tuning data (SQLiteStore) is preserved
4. Each new conversation starts with a fresh session
5. Users can continue using the CLI without changes

## Future Enhancements

See [SESSION_MEMORY.md](SESSION_MEMORY.md#future-enhancements) for planned improvements.
