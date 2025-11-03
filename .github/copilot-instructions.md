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
   - `codeagent.py`: Sandboxed code execution with guardrails
   - `md_browser.py`: Web search/fetch with Markdown conversion and embedding-based ranking

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
   - Controlled execution environment for CodeAgent

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
- `TTS_REF_AUDIO`: Path to reference audio for voice cloning
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

## When Suggesting Changes

1. **Minimize modifications**: Make surgical changes to existing code
2. **Preserve tool calling**: Don't break the structured function call interface
3. **Test guardrails**: If modifying sandbox, verify security constraints
4. **Update documentation**: Keep README and docs in sync with code changes
5. **Consider resource limits**: Remember 12GB VRAM and 32GB RAM constraints
6. **Async patterns**: Use async/await for I/O operations
7. **Error handling**: Tools should fail gracefully and emit events
8. **Dashboard integration**: Consider UI impacts for user-facing changes
