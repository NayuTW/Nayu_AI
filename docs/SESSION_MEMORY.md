# Session Memory - Conversational Continuity

This document describes the session memory feature that enables the Nayu_AI agent to maintain conversational context across CLI turns.

## Overview

Session memory provides conversational continuity by preserving:
- **Recent conversation history** (rolling window of messages)
- **Conversation summaries** (automatically generated every N turns)
- **Working set memory** (last task, artifacts like files/URLs, environment context)

This allows natural references like "that file", "the previous task", or "it" to be resolved correctly.

## Features

### 1. Session-Scoped Conversations

Each session maintains its own isolated conversation history. By default, the CLI uses a session ID based on the startup timestamp, but you can manage multiple sessions:

```bash
# List all sessions
/sessions

# Reset current session (clear history)
/reset-session
```

### 2. Rolling Context Window

The session manager maintains the last N messages within a configurable token budget:
- **Max messages**: 20 by default (configurable)
- **Max tokens**: ~4096 by default (configurable)
- **Truncation**: Oldest messages are removed first when limits are exceeded

### 3. Automatic Summaries

Every N turns (default: 5), the system generates a compact summary of the conversation to maintain long-term context without overwhelming the prompt with full message history.

### 4. Working Set Memory

The working set tracks:
- **Last task**: `{id, type, outcome}`
- **Artifacts**: `{last_file, last_dir, last_url, last_repo_branch, ...}`
- **Environment context**: `{project_root, active_profile, ...}`

This structured memory helps resolve references like:
- "Open that file" → resolves to `artifacts.last_file`
- "Go back to that URL" → resolves to `artifacts.last_url`
- "Continue the previous task" → references `last_task`

### 5. Persistence

Sessions are persisted to disk in JSON format:
- **Location**: `.nayu_ai/sessions/<session_id>.json`
- **Format**: Human-readable JSON with messages, summary, and working set
- **Caching**: In-memory LRU cache for active sessions with write-through to disk

## Usage Examples

### Basic Conversation

```
You: Open the file report.txt
Agent: I've opened report.txt for you.
You: What's in that file?
Agent: [Reads the file and responds...]
You: Add a conclusion section to it
Agent: [Agent understands "it" refers to report.txt]
```

### Session Management

```
You: /sessions
Available sessions (2):
  - session-1730626431-a4b2f3e1 (current)
  - manual-test-session

You: /reset-session
Session session-1730626431-a4b2f3e1 has been reset. Conversation history cleared.
```

## Configuration

Session manager settings can be configured when initializing `MainAgent`:

```python
session_manager = SessionManager(
    session_dir=".nayu_ai/sessions",    # Directory for session files
    max_messages=20,                     # Max messages in rolling window
    max_tokens=4096,                     # Approximate token budget
    summary_interval=5,                  # Generate summary every N turns
    max_cache_size=10                    # Max sessions in memory cache
)
```

## Architecture

### Components

1. **SessionManager** (`src/agents/memory/session_manager.py`)
   - Manages session state, persistence, and context assembly
   - Handles rolling window truncation and summary generation
   - Provides LRU cache for active sessions

2. **SessionState** (dataclass)
   - Stores messages, summary, working set, and metadata for a session
   - Automatically persisted to disk

3. **WorkingSet** (dataclass)
   - Tracks last_task, artifacts, and environment context
   - Provides formatted context strings for prompts

4. **Integration** (`src/agents/main_agent.py`)
   - Session context is assembled in `handle_user_message()`
   - Messages are added to session before and after agent execution
   - Working set can be updated after tool calls (future enhancement)

### Prompt Assembly

The full prompt sent to the LLM includes:

```
SYSTEM_PROMPT
OS_CONTEXT

CONTEXT: [SharedState context]

SESSION SUMMARY: [Compact conversation summary]

WORKING SET: [Last task, artifacts, environment]

RECENT CONVERSATION: [Last N messages]

MESSAGE SOURCE: [cli/discord/etc]

USER MESSAGE: [Current user input]
```

## Performance

Session memory is designed for minimal overhead:
- **Storage**: JSON files, ~1-2KB per session with 20 messages
- **Memory**: In-memory LRU cache for hot sessions
- **Latency**: <10ms for context assembly
- **Token cost**: ~500-1000 tokens added to prompt (depends on conversation length)

## Testing

Comprehensive test suite included:
- `test_session_memory.py` - Unit tests for SessionManager
- `test_integration_memory.py` - Integration tests with agent workflow
- `test_cli_manual.py` - Manual CLI simulation

Run tests:
```bash
python test_session_memory.py
python test_integration_memory.py
python test_cli_manual.py
```

## Future Enhancements

Potential improvements:
1. **Automatic working set updates**: Extract file/URL references from tool calls
2. **Multi-user sessions**: Discord/chat channels with per-user or per-channel sessions
3. **LLM-generated summaries**: Use LLM to create better conversation summaries
4. **Semantic truncation**: Keep most relevant messages instead of just recent ones
5. **Cross-session memory**: Share knowledge across sessions via memory tool
6. **Session forking**: Branch conversations for "what-if" scenarios

## Troubleshooting

### Session files growing too large

Adjust `max_messages` or `max_tokens` in SessionManager configuration to limit history.

### Context not being preserved

Check:
1. Session ID is consistent across turns
2. `.nayu_ai/sessions/` directory has write permissions
3. Session manager is being flushed on exit

### Performance issues

Reduce `max_messages` or `max_tokens` to keep prompt size smaller.

## Related Documentation

- [Architecture Overview](../README.md)
- [Tool System](TOOLS.md)
- [Memory Tool](MEMORY_TOOL.md)
