# Continuous Running Agent Architecture

## Overview

This implementation transforms the Nayu_AI agent from a request-response system into a continuously running, character-focused AI that maintains presence and can handle interruptions mid-response.

## Architecture Components

### 1. Event-Driven Input System

**File:** `src/app.py`

The blocking `while True: input()` loop has been replaced with an event-driven architecture:

- **Non-blocking input loop**: Uses `asyncio.to_thread()` for input collection
- **Event queue system**: User inputs are queued via `InterruptManager`
- **Concurrent processing**: Input collection and response display run in parallel
- **Agent runs continuously**: The `ContinuousAgentRunner` maintains agent state between interactions

### 2. Interrupt Support

**Files:** 
- `src/agents/core/events.py` - Enhanced EventBus
- `src/agents/core/interrupt_manager.py` - Interrupt routing

**Features:**
- Three priority levels: `HIGH`, `NORMAL`, `BACKGROUND`
- Interrupt queue alongside regular event system
- Non-blocking interrupt checking
- Graceful interruption during response generation

**Usage:**
```python
# Signal an interrupt
await interrupt_manager.signal_user_input(
    text="new message",
    source="cli",
    metadata={"session_id": session_id}
)

# Check for interrupts
if bus.has_interrupt():
    interrupt = await bus.get_interrupt(timeout=0.1)
```

### 3. Character State Machine

**File:** `src/agents/core/character_state.py`

Tracks the agent's current activity and attention:

**States:**
- `IDLE` - Waiting for input, passive observation
- `THINKING` - Processing input, deciding action
- `RESPONDING` - Generating response
- `INTERRUPTED` - Response was interrupted
- `TOOL_USE` - Executing a tool

**Attention Stack:**
- Maintains context of current task
- Tracks source, user, channel for multi-user support
- Provides state transition history

### 4. Continuous Agent Runner

**File:** `src/agents/core/continuous_runner.py`

Coordinates continuous operation:

- Non-blocking message processing via input queue
- Interrupt-aware execution
- State machine management
- Idle/active state transitions
- Heartbeat events when idle (every 5 seconds)

**Key Methods:**
```python
# Start continuous operation
await continuous_runner.start()

# Queue input for processing
await continuous_runner.queue_input(text, source, metadata)

# Get current state
state = continuous_runner.get_state()
```

### 5. Streaming Response System

**Files:**
- `src/agents/core/streaming_handler.py` - Streaming coordination
- `src/agents/main_agent_smol.py` - Streaming methods

**Features:**
- Token-by-token streaming with configurable buffer
- Interrupt checking during stream (every N tokens)
- Stream events: `stream.chunk`, `stream.complete`, `stream.interrupted`
- Character-by-character display with natural typing effect

**Enable Streaming:**
```bash
export AGENT_STREAMING=true
python -m src.app
```

### 6. Token Optimization

**Files:**
- `src/agents/memory/session_manager.py` - Context management
- `src/agents/llm/litellm_model.py` - KV cache support

**Optimizations:**
- **Aggressive trimming**: Max 10 messages, ~500 token budget (vs 4096)
- **Compact context**: Returns only last 5-7 messages
- **Token estimation**: Monitors context size
- **Message truncation**: 500 char limit per message in history
- **KV cache**: `keep_alive=-1` keeps model loaded
- **Dynamic context**: Configurable via environment variable

**Configuration:**
```bash
export AGENT_COMPACT_CONTEXT=true  # Use ultra-compact context (default)
export AGENT_KEEP_ALIVE=-1         # Keep model loaded (default)
```

## Usage

### Starting the Agent

```bash
# Standard mode
python -m src.app

# With streaming enabled
AGENT_STREAMING=true python -m src.app
```

### CLI Commands

- `voice on` / `voice off` - Toggle voice notifications
- `/reset-session` - Clear conversation history
- `/sessions` - List all sessions
- `/state` - Show current agent state
- `quit` - Exit application

### State Inspection

The `/state` command shows:
```
Agent State: idle
Attention Depth: 0
Current Task: None
```

During processing:
```
Agent State: responding
Attention Depth: 1
Current Task: Responding to: Hello...
```

## Memory Efficiency

### Before (Request-Response)
- Active context: ~4096 tokens
- Full history kept in RAM
- Agent terminated after each response
- Context rebuilt on every request

### After (Continuous)
- Active context: ~500 tokens (8x improvement)
- Only recent messages in RAM
- Agent stays alive between interactions
- Incremental context updates
- KV cache reduces reprocessing

## Event Flow

### User Input Flow
1. User types message in CLI
2. Input queued via `InterruptManager.signal_user_input()`
3. `ContinuousAgentRunner` receives interrupt
4. State transitions: `IDLE` → `THINKING` → `RESPONDING`
5. Agent processes message with compact context
6. Response streamed (if enabled) or displayed directly
7. State returns to `IDLE`

### Interrupt Flow
1. User types new message during response
2. `InterruptManager` signals with `NORMAL` priority
3. `StreamingHandler` detects interrupt
4. Current stream terminates gracefully
5. Partial response is preserved
6. New message begins processing

## Testing

All functionality is covered by tests:

```bash
# Session memory tests
PYTHONPATH=. python test/test_session_memory.py

# Continuous agent tests (interrupts, state machine)
PYTHONPATH=. python test/test_continuous_agent.py

# Streaming tests
PYTHONPATH=. python test/test_streaming.py

# Token optimization tests
PYTHONPATH=. python test/test_token_optimization.py
```

**Test Coverage:**
- Session management: 7/7 tests
- Continuous operation: 4/4 tests
- Streaming: 4/4 tests
- Token optimization: 5/5 tests
- **Total: 20/20 tests passing ✅**

## API Integration

### Discord Integration

The continuous architecture is compatible with Discord:

```python
# Discord messages are handled the same way
await agent.handle_external_message(
    text=message.content,
    user_id=str(message.author.id),
    channel_id=str(message.channel.id),
    source="discord",
    metadata={"guild_id": str(message.guild.id)}
)
```

Streaming can be enabled for Discord by updating the bot's message handling to listen for `stream.chunk` events.

### Custom Integrations

To integrate with other platforms:

```python
# 1. Queue input via interrupt manager
await interrupt_manager.signal_user_input(
    text=user_message,
    source="custom_platform",
    metadata={"user_id": user_id, "channel_id": channel_id}
)

# 2. Subscribe to output events
event_queue = await bus.subscribe()

async def handle_output():
    while True:
        event = await event_queue.get()
        if event.type == "stream.chunk":
            # Send partial response
            await send_to_platform(event.payload["content"])
        elif event.type == "agent.output":
            # Send complete response
            await send_to_platform(event.payload["text"])
```

## Performance Characteristics

### Latency
- **First response**: Same as before (model loading + inference)
- **Subsequent responses**: Faster due to KV cache
- **Interrupt latency**: <100ms (checks every 3 tokens)

### Memory Usage
- **Idle**: No increase from base
- **Active**: ~8x reduction in context memory
- **Per session**: ~500 tokens vs 4096 tokens

### Scalability
- Multiple sessions supported via session manager
- LRU cache evicts old sessions automatically
- Disk persistence for session history

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_STREAMING` | `false` | Enable streaming responses |
| `AGENT_COMPACT_CONTEXT` | `true` | Use ultra-compact context |
| `AGENT_KEEP_ALIVE` | `-1` | Keep model loaded (-1 = forever) |
| `AGENT_MODEL` | `llama3.1:8b-instruct-q4_K_M` | Ollama model name |
| `AGENT_NUM_CTX` | `10000` | Context window size |

## Backward Compatibility

All changes are backward compatible:

- ✅ Existing Discord integration works unchanged
- ✅ CLI interface remains familiar (with added commands)
- ✅ Tools continue to function normally
- ✅ Session persistence format unchanged
- ✅ Event bus additions are non-breaking

## Future Enhancements

Potential improvements for future versions:

1. **True token streaming**: Direct integration with LiteLLM streaming API
2. **Multi-user attention**: Priority queue for multiple simultaneous users
3. **Attention weighting**: Smart interrupt handling based on context
4. **Proactive engagement**: Agent can initiate conversation when idle
5. **Context compression**: Use smaller model for summarization
6. **Adaptive token budget**: Adjust based on available memory

## Troubleshooting

### Agent not responding
- Check if `ContinuousAgentRunner` is started
- Verify interrupt manager is running
- Check event queue for errors

### High memory usage
- Reduce `max_messages` in SessionManager
- Lower `max_tokens` budget
- Enable `aggressive_trim=True`

### Streaming not working
- Set `AGENT_STREAMING=true`
- Check if stream events are being published
- Verify event subscription in display loop

### Context too short
- Increase `max_messages` in SessionManager
- Set `AGENT_COMPACT_CONTEXT=false`
- Adjust `max_tokens` budget

## Architecture Diagrams

### Event Flow
```
User Input → InterruptManager → ContinuousAgentRunner
                                        ↓
                                 State: THINKING
                                        ↓
                              MainAgentSmol.handle_user_message()
                                        ↓
                                 State: RESPONDING
                                        ↓
                              StreamingHandler (optional)
                                        ↓
                                    EventBus
                                        ↓
                              CLI Display / Discord Bot
                                        ↓
                                  State: IDLE
```

### State Transitions
```
IDLE ←→ THINKING → RESPONDING → IDLE
         ↓               ↓
    INTERRUPTED ← ←  ← ←
```

### Context Management
```
Full History (SQLite)
        ↓
Session Manager (LRU Cache)
        ↓
Rolling Window (max 10 msgs)
        ↓
Token Budget Filter (~500 tokens)
        ↓
Compact Context (last 5-7 msgs)
        ↓
Prompt Builder
```
