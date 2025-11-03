# Fix: Duplicate Tool Calls and Multiple final_answer Issue

## Problem Statement

When using Discord integration, the system would sometimes send duplicate messages and provide multiple final answers. For example:
- Sending 2 duplicate DMs to the same user
- Providing 2 final answers: first showing "observations" and second showing the actual main agent response

## Root Cause

The issue was caused by a **nested agent architecture**:

```
User Request
    ↓
Main CodeAgent
    ↓
discord_agent tool (wraps ToolCallingAgent)
    ↓
discord_tool (actual Discord API calls)
    ↓
ToolCallingAgent generates final_answer #1
    ↓
Main CodeAgent sees this as "observations"
    ↓
Main CodeAgent generates final_answer #2
```

### Why This Happened

1. The `DiscordAgentTool` wrapped a `ToolCallingAgent` internally
2. When the main `CodeAgent` called the `discord_agent` tool:
   - The inner `ToolCallingAgent` executed the Discord tool
   - The inner agent generated its own `final_answer` (e.g., "I sent the message")
   - This final_answer was returned as the tool's output to the main CodeAgent
   - The main CodeAgent interpreted this as "observations" from the tool
   - The main CodeAgent then generated its own `final_answer`
3. Additionally, retry logic in the agents could cause tools to be called twice

## Solution

Replace the nested agent architecture with a **direct tool implementation**:

```
User Request
    ↓
Main CodeAgent
    ↓
discord tool (direct Discord API wrapper)
    ↓
Main CodeAgent generates single final_answer
```

### Changes Made

#### 1. Created `discord_tool_smol.py`

A direct smolagents Tool that wraps the Discord service without using a nested agent:

```python
class DiscordSmolTool(Tool):
    """Direct Discord messaging tool."""
    name = "discord"
    description = "Send messages to Discord channels or direct messages..."
    
    def forward(self, action: str, target: str, message: str, ...):
        """Directly calls Discord service methods."""
        # No nested agent - just direct service calls
        if action == "dm":
            await self.discord_service.send_dm_target(target, message)
        elif action == "channel":
            await self.discord_service.send_channel_target(target, message)
```

#### 2. Updated `main_agent_smol.py`

Changed `add_discord_tool()` to use the direct tool instead of the nested agent wrapper:

```python
# OLD (nested agent):
from src.agents.tools.discord_agent_tool import DiscordAgentTool
discord_agent_tool = DiscordAgentTool(discord_service, self.model)

# NEW (direct tool):
from src.agents.tools.discord_tool_smol import DiscordSmolTool
discord_tool = DiscordSmolTool(discord_service)
```

#### 3. Deprecated Old Implementation

Added deprecation warnings to `discord_agent_tool.py` to prevent future use:

```python
warnings.warn(
    "DiscordAgentTool is deprecated and causes duplicate tool calls. "
    "Use DiscordSmolTool from discord_tool_smol.py instead.",
    DeprecationWarning
)
```

## Why This Fix Works

### The CodeAgent is Sufficient

The main `CodeAgent` is already capable of:
- Understanding natural language requests
- Parsing tool parameters from context
- Making appropriate tool calls
- Generating a final answer

**There's no need for a nested agent** - it just adds complexity and causes the duplicate final_answer issue.

### Direct Tool Benefits

1. **Single final_answer**: Only the main CodeAgent generates a final answer
2. **No duplicate calls**: Tools are called exactly once
3. **Cleaner flow**: Simpler architecture is easier to debug
4. **Better performance**: Less LLM overhead from nested agent

## Example Flow (After Fix)

User: "Send a DM to @alice saying hello"

```
1. Main CodeAgent receives request
2. Main CodeAgent generates code to call discord tool:
   discord(action="dm", target="@alice", message="hello")
3. discord tool executes and returns: "DM sent to @alice: hello..."
4. Main CodeAgent generates single final_answer: "I sent a DM to alice saying hello."
```

**Result**: Single message sent, single final answer provided.

## Testing

Run the test suite to verify the fix:

```bash
python test_discord_tool_fix.py
```

Tests verify:
- ✓ DiscordSmolTool is a proper Tool subclass
- ✓ Tool can be instantiated without nested agents
- ✓ forward() method works correctly
- ✓ MainAgentSmol uses direct tool (not nested agent)
- ✓ Tool description is clear and complete

## Best Practices for Future Tools

When creating new tools for the CodeAgent:

### ✅ DO: Create Direct Tools

```python
class MyTool(Tool):
    name = "my_tool"
    
    def forward(self, param: str) -> str:
        # Direct implementation
        return do_the_work(param)
```

### ❌ DON'T: Wrap Agents in Tools

```python
class MyAgentTool(Tool):
    def __init__(self, model):
        self.agent = ToolCallingAgent(...)  # ❌ Causes nested agent issue
    
    def forward(self, task: str):
        return self.agent.run(task)  # ❌ Generates duplicate final_answer
```

### Why?

- The main CodeAgent is **already an agent** with reasoning capabilities
- Nesting agents creates confusion about who generates the final answer
- Direct tools are simpler, faster, and more predictable

## Related Files

- `src/agents/tools/discord_tool_smol.py` - Direct Discord tool (✓ use this)
- `src/agents/tools/discord_agent_tool.py` - Deprecated nested agent (❌ don't use)
- `src/agents/main_agent_smol.py` - Main agent using direct tools
- `test_discord_tool_fix.py` - Test suite for the fix

## References

- [smolagents Documentation](https://huggingface.co/docs/smolagents)
- [smolagents Tool Class](https://huggingface.co/docs/smolagents/main/en/reference/tools)
- Issue: "Sometimes tools will be called doubled and there will be multiple final_answer calls"
