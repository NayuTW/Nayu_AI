# Changelog: Fix Duplicate Tool Calls Issue

**Date:** November 3, 2025  
**Issue:** Sometimes tools would be called twice and there would be multiple final_answer calls  
**PR Branch:** `copilot/fix-101481767-1073517878-66d927f7-7dd7-4d83-a4c6-694f809d079c`

## Summary

Fixed the issue where Discord tool calls would be duplicated and multiple final_answer responses would be generated. The root cause was a nested agent architecture where a ToolCallingAgent was wrapped inside a Tool called by the main CodeAgent.

## Changes

### Files Added

1. **`src/agents/tools/discord_tool_smol.py`** (149 lines)
   - Direct Discord tool implementation following smolagents Tool pattern
   - No nested agent architecture
   - Proper async handling using `asyncio.run_coroutine_threadsafe()`
   - Configurable timeout (10 seconds)
   - Consistent error messages

2. **`test_discord_tool_fix.py`** (155 lines)
   - Comprehensive test suite
   - AST-based code analysis for robustness
   - Verifies no nested agent architecture
   - All tests pass

3. **`docs/FIX_DUPLICATE_TOOL_CALLS.md`** (192 lines)
   - Detailed problem explanation
   - Root cause analysis
   - Solution documentation
   - Best practices for future tool development
   - Example flows

4. **`CHANGELOG_DUPLICATE_FIX.md`** (this file)
   - Summary of all changes

### Files Modified

1. **`src/agents/sub_agents/main_agent.py`** (24 lines changed)
   - Changed `add_discord_tool()` to use `DiscordSmolTool` instead of `DiscordAgentTool`
   - Updated system prompt to reference "discord tool" instead of "discord_agent"
   - Changed registry name from "discord_agent" to "discord"

2. **`src/agents/tools/discord_agent_tool.py`** (21 lines added)
   - Added comprehensive deprecation warnings
   - Updated docstring with explanation of the issue
   - Kept file for reference only

## Commits

1. `17d9940` - Fix duplicate tool calls by removing nested agent architecture
2. `6384055` - Add test to verify Discord tool fix eliminates nested agent
3. `ab7d1c2` - Add deprecation warnings to old DiscordAgentTool
4. `ba33c87` - Fix async handling in Discord tool using run_coroutine_threadsafe
5. `452312e` - Improve error handling and message consistency in Discord tool
6. `33a6b00` - Address code review feedback: improve timeout handling and test robustness

## Impact

### Before (Broken)

```
User: "Send a DM to @alice"
  ↓
Main CodeAgent calls discord_agent tool
  ↓
discord_agent (ToolCallingAgent) calls discord tool
  ↓
Discord tool sends message
  ↓
discord_agent generates final_answer #1: "DM sent"
  ↓
Main CodeAgent sees "DM sent" as observations
  ↓
Main CodeAgent generates final_answer #2: "I sent a DM"
```

**Result:** Potentially duplicate messages, definitely duplicate final_answers ❌

### After (Fixed)

```
User: "Send a DM to @alice"
  ↓
Main CodeAgent calls discord tool directly
  ↓
Discord tool sends message
  ↓
Main CodeAgent generates single final_answer: "I sent a DM"
```

**Result:** Single message, single final_answer ✓

## Statistics

- **Lines Added:** 527
- **Lines Removed:** 14
- **Net Change:** +513 lines
- **Files Changed:** 5
- **Tests Added:** 1 comprehensive test suite
- **Security Alerts:** 0 (CodeQL passed)
- **Code Reviews:** 3 (all feedback addressed)

## Testing

All tests pass:
- ✓ DiscordSmolTool structure is correct
- ✓ DiscordSmolTool can be instantiated
- ✓ DiscordSmolTool.forward() works without nested agents
- ✓ MainAgentSmol uses DiscordSmolTool directly (no nested agent)
- ✓ Tool description is clear and complete

## Security

- CodeQL scan completed: 0 vulnerabilities found
- No secrets exposed
- Proper async handling prevents race conditions
- Timeout prevents hanging operations

## Documentation

- Created comprehensive fix documentation in `docs/FIX_DUPLICATE_TOOL_CALLS.md`
- Added inline comments explaining async handling
- Documented best practices for future tool development
- Clear deprecation warnings on old implementation

## Backward Compatibility

- Old `DiscordAgentTool` kept for reference with deprecation warnings
- No breaking changes to public APIs
- Existing code will see deprecation warnings if using old tool

## Best Practices Established

For future tool development:

### ✅ DO: Create Direct Tools
```python
class MyTool(Tool):
    def forward(self, param: str) -> str:
        return do_the_work(param)
```

### ❌ DON'T: Wrap Agents in Tools
```python
class MyAgentTool(Tool):
    def __init__(self):
        self.agent = ToolCallingAgent(...)  # ❌ Causes nested agent issue
```

## Verification

To verify the fix works:
1. Run `python test_discord_tool_fix.py` - All tests should pass
2. Start the application with Discord integration
3. Send a command like "DM @user hello"
4. Verify only one message is sent
5. Verify only one final_answer is generated

## References

- Issue: "Sometimes tools will be called doubled and there will be multiple final_answer calls"
- [smolagents Documentation](https://huggingface.co/docs/smolagents)
- [Fix Documentation](docs/FIX_DUPLICATE_TOOL_CALLS.md)

## Contributors

- AI Agent (Copilot)
- NayuTW (Repository Owner)
