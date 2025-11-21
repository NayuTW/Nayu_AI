# GitHub Copilot Instructions for Nayu_AI

## Project Overview

Nayu_AI is a fully local, Python-based multi-agent orchestrator system designed to run on a single GPU (12GB VRAM) and 32GB RAM. The system features:

- **Main orchestrator LLM** via Ollama with structured tool/function calling
- **Sub-agents as tools**: web, desktop, vision, speech, memory, and code execution
- **FastAPI + HTMX dashboard** for live control and monitoring
- **Persistent SQLite storage** for events, metrics, settings, and fine-tune dataset curation
- **Local embeddings** using Chroma + e5/bge/MiniLM models
- **Voice synthesis** using NeuTTS-Air for error notifications

## Architecture

### Core Components

1. **Main Agent** (`src/agents/main_agent.py`)
   - Orchestrator using Ollama LLM (qwen2:7b-instruct-q5_K_M by default)
   - Manages tool registry and coordinates sub-agents
   - Maintains shared state via blackboard pattern

2. **Tool System** (`src/agents/tools/`)
   - `web.py`: Playwright-based browser automation
   - `desktop.py`: Keyboard/mouse control + screenshots
   - `vision.py`: VLM for screenshots/OCR
   - `speech.py`: Local STT/TTS with faster-whisper and NeuTTS-Air
   - `memory.py`: Chroma vector store with local embeddings
   - `writefile_smol.py`: Safe file writing to .workspace directory with guardrails
   - `webbrowser_smol.py`: Web search/fetch with Markdown conversion and embedding-based ranking

3. **Dashboard** (`src/dashboard/`)
   - FastAPI server with HTMX frontend
   - Live event logging and health monitoring
   - Tool toggle controls and circuit breaker management
   - Dataset curation interface for fine-tuning
   - Settings persistence (voice controls, speak-on-error)

4. **Core Infrastructure** (`src/agents/core/`)
   - `events.py`: Event bus for system-wide notifications
   - `registry.py`: Tool registration and management
   - `health.py`: Health check system for tools
   - `store.py`: SQLite persistence layer

5. **Sandbox & Security** (`src/agents/sandbox/`)
   - `guardrails.py`: Import allowlist, file I/O restrictions, subprocess blocking
   - Used by WriteFileTool for safe file operations within .workspace directory

## Code Conventions

### Python Style
- Python 3.10+ (3.11 recommended)
- Use type hints where appropriate
- Follow PEP 8 conventions
- Use async/await for I/O-bound operations
- Keep functions focused and modular

### Project Structure
```
src/
├── agents/
│   ├── core/          # Infrastructure (events, registry, health, store)
│   ├── embeddings/    # Local embedding models
│   ├── llm/           # Ollama LLM client
│   ├── notify/        # Notification and error speech system
│   ├── sandbox/       # Code execution guardrails
│   ├── tools/         # Individual tool implementations
│   ├── main_agent.py  # Main orchestrator
│   └── state.py       # Shared state management
├── dashboard/         # FastAPI dashboard server
└── app.py            # Application entry point
```

### Naming Conventions
- Classes: `PascalCase` (e.g., `MainAgent`, `WebTool`)
- Functions/methods: `snake_case` (e.g., `tool_specs()`, `start_dashboard()`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `SYSTEM_PROMPT`)
- Private members: prefix with underscore (e.g., `_tools`)

## Development Environment

### Prerequisites
- **Python**: 3.10+ (3.11 recommended, 3.12 supported)
- **Ollama**: Must be installed and running locally (not in requirements.txt)
  - Install from https://ollama.ai/download
  - Start with `ollama serve`
  - Pull models: `ollama pull qwen2:7b-instruct-q5_K_M`
- **GPU**: NVIDIA GPU with 12GB+ VRAM recommended for local LLM inference
- **RAM**: 32GB recommended for comfortable operation
- **OS**: Linux preferred (works in VM with GPU passthrough), also supports macOS
- **espeak**: Required for TTS functionality (system package)

### Setup
```bash
python -m venv .venv && source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
playwright install chromium
```

### Build and Run
- Use the `Makefile` for common operations:
  - `make setup`: Create venv and install dependencies
  - `make playwright`: Install Playwright browser
  - `make dirs`: Create required directories
  - `make run`: Start the application (binds to 0.0.0.0:8008)
  - `make run-local`: Start on localhost only
  - `make check`: Run sanity checks
  - `make clean`: Clean caches and artifacts

### Running the Application
```bash
python -m src.app
# Or via Makefile:
make run
```

Dashboard accessible at:
- Local: http://127.0.0.1:8008
- From host (if VM): http://<vm-ip>:8008

## Dependencies

### Core Dependencies
- **FastAPI + uvicorn**: Web framework for dashboard
- **Playwright**: Browser automation for web tool
- **Ollama**: LLM inference (requires separate installation)
- **ChromaDB + fastembed**: Vector store and embeddings
- **faster-whisper**: Speech-to-text
- **NeuTTS-Air**: Text-to-speech with voice cloning
- **smolagents**: Code execution framework
- **aiohttp**: For Ollama API communication (vision and LLM)

### Optional Dependencies
- **Selenium + Chrome**: For dynamic page rendering in md_browser
- **espeak**: Required by NeuTTS-Air for TTS

## Key Configuration

### Environment Variables
- `AGENT_DASH_HOST`: Dashboard bind address (default: 0.0.0.0)
- `AGENT_DASH_PORT`: Dashboard port (default: 8008)
- `TTS_REF_AUDIO`: Path to reference audio for voice cloning - supports `.pt` (pre-encoded, recommended) or `.wav` files
- `TTS_REF_TEXT`: Reference text or path to transcript file

### Ollama Models
- Main LLM: qwen2:7b-instruct-q5_K_M or llama3.1:8b-instruct-q4_K_M
- Vision: gemma3:4b-it-q4_K_M (via Ollama)
- Context window: ~8-12k tokens for 12GB VRAM

### Embeddings
- CPU-friendly models: intfloat/e5-small-v2, BAAI/bge-small-en-v1.5, all-MiniLM-L6-v2

## Security Considerations

### Code Execution Guardrails
- **Import allowlist**: Only approved modules can be imported
- **File I/O restrictions**: Disabled by default, optional read-only jail
- **Network restrictions**: Requests only allowed from approved tool modules
- **Subprocess blocking**: Shell and subprocess access disabled
- **Resource limits**: Step and stdout/err caps, optional CPU/memory limits

### Best Practices
- Always review code execution tool changes carefully
- Test guardrails when modifying sandbox code
- Use dashboard toggles to disable risky tools quickly
- Consider VM snapshots before large experiments
- Implement circuit breakers for misbehaving tools

## Testing and Validation

### Running Tests
```bash
# Run all tests
python -m pytest test/

# Run specific test file
python -m pytest test/test_integration_memory.py

# Run with verbose output
python -m pytest -v test/
```

### Test Structure
- Tests are located in the `/test` directory
- Each test file focuses on a specific component or integration
- Integration tests may require Ollama to be running locally
- Use mocks for external dependencies where appropriate

### Writing Tests
- Follow existing test patterns in the repository
- Test both success and failure cases
- Verify tool state changes and event emissions
- Mock Ollama calls for unit tests to avoid external dependencies

### Manual Testing
- Use dashboard's "Test" button for individual tools
- Monitor live event log for debugging
- Check health status indicators
- Verify circuit breaker activation on failures

### Tool Testing
- Each tool should have a `spec()` method defining its interface
- Tools should handle errors gracefully and return structured responses
- Test tools individually before integrating with orchestrator

## Common Patterns

### Adding a New Tool
1. Create tool class in `src/agents/tools/`
2. Implement `__init__`, `__call__`, and `spec()` methods
3. Register tool in `MainAgent.__init__`
4. Add tool to dashboard if UI controls needed
5. Document tool usage in README

### Event Handling
```python
# Emit events via EventBus
self.bus.emit("tool_call", {"name": "web", "status": "success"})

# Events are persisted to SQLite automatically
```

### Tool Registry
```python
# Register a tool
self.registry.register("tool_name", tool_instance, tool_spec)

# Enable/disable tools
self.registry.enable("tool_name")
self.registry.disable("tool_name")
```

### State Management
```python
# Update shared state
self.state.add_summary("key", "value")

# Read state
summary = self.state.summary()
```

## Documentation

- Main README: `/README.md` - Setup and quickstart
- TTS Setup: `/docs/TTS_SETUP.md` - NeuTTS-Air configuration
- Examples: `/examples/` - Sample usage scenarios
- Changelog: `/CHANGELOG.md` - Version history

## VM and Deployment Notes

- Designed for Linux VMs with GPU passthrough
- Dashboard binds to 0.0.0.0 for host access by default
- Use libvirt NAT for host→guest connectivity
- Ollama can be exposed similarly (OLLAMA_HOST=0.0.0.0:11434)
- Consider firewall rules to restrict access

## Fine-tuning and Dataset Curation

- Use dashboard to label assistant responses (good/bad)
- Export curated examples to JSONL format
- Include tool-calling examples to preserve function calling
- QLoRA/Unsloth feasible on 12GB VRAM with 7-8B models

## Error Handling

### Tool Error Patterns
All tools should follow this error handling pattern:

```python
try:
    # Tool operation
    result = perform_operation()
    self.bus.emit("tool_call", {
        "name": self.name,
        "status": "success",
        "result": result
    })
    return {"status": "success", "data": result}
except Exception as e:
    self.bus.emit("tool_call", {
        "name": self.name,
        "status": "error",
        "error": str(e)
    })
    return {"status": "error", "error": str(e)}
```

### Circuit Breaker
- Tools automatically disable after repeated failures (default: 3 failures)
- Check `tool_metrics` table for failure counts
- Use dashboard to manually reset circuit breakers
- Implement proper error recovery before re-enabling failed tools

### Voice Notifications
- Critical errors trigger TTS notifications if enabled
- Configure via `TTS_REF_AUDIO` and `TTS_REF_TEXT` environment variables
- Toggle speak-on-error in dashboard settings

## Contributing Workflow

### Making Changes
1. **Understand the scope**: Read relevant documentation and code
2. **Make minimal changes**: Only modify what's necessary
3. **Test locally**: Verify changes work as expected
4. **Check dashboard**: Ensure UI reflects changes correctly
5. **Run existing tests**: Ensure no regressions
6. **Update documentation**: Keep docs in sync with code

### Code Review Checklist
- [ ] Changes are minimal and focused
- [ ] Tool interfaces remain compatible
- [ ] Async patterns used for I/O operations
- [ ] Error handling follows project patterns
- [ ] Events emitted for important state changes
- [ ] Dashboard updated if tool behavior changes
- [ ] Documentation updated if interfaces change
- [ ] Security guardrails maintained

## Troubleshooting

### Common Issues

**Ollama Connection Errors**
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama service
ollama serve

# Check model availability
ollama list
```

**Playwright Browser Issues**
```bash
# Reinstall Chromium
playwright install chromium

# Check Playwright installation
python -c "import playwright; print('OK')"
```

**Dashboard Not Accessible**
- Check firewall rules allow port 8008
- Verify `AGENT_DASH_HOST=0.0.0.0` for VM access
- Use `make run-local` for localhost-only binding
- Check dashboard logs for startup errors

**Tool Disabled/Circuit Breaker**
- Check dashboard health status for tool state
- Review event log for failure patterns
- Reset circuit breaker via dashboard
- Fix underlying issue before re-enabling

**Memory/ChromaDB Issues**
```bash
# Reset vector database
rm -rf .chroma

# Verify embeddings model
python -c "from fastembed import TextEmbedding; print('OK')"
```

**TTS Not Working**
- Verify espeak is installed: `which espeak`
- Check reference audio configuration
- Ensure audio file paths are absolute
- Review TTS setup documentation: `docs/TTS_SETUP.md`

### Performance Issues

**High Memory Usage**
- Reduce Ollama context window (num_ctx parameter)
- Use smaller embedding model
- Limit concurrent tool executions
- Monitor ChromaDB index size

**Slow Tool Response**
- Check network latency to Ollama
- Profile slow operations in tool code
- Consider caching for repeated operations
- Review dashboard metrics for bottlenecks

**GPU Memory Exhaustion**
- Use more aggressively quantized models (Q4 vs Q5)
- Reduce batch size for embeddings
- Unload unused models from Ollama
- Monitor VRAM with `nvidia-smi`

## When Suggesting Changes

1. **Minimize modifications**: Make surgical changes to existing code
2. **Preserve tool calling**: Don't break the structured function call interface
3. **Test guardrails**: If modifying sandbox, verify security constraints
4. **Update documentation**: Keep README and docs in sync with code changes
5. **Consider resource limits**: Remember 12GB VRAM and 32GB RAM constraints
6. **Async patterns**: Use async/await for I/O operations
7. **Error handling**: Tools should fail gracefully and emit events
8. **Dashboard integration**: Consider UI impacts for user-facing changes
9. **Run tests**: Verify no regressions with existing test suite
10. **Check dependencies**: Avoid adding new dependencies unless necessary
