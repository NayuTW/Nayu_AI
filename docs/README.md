# Local Multi‑Agent Orchestrator (Fully Offline, Dashboard + Curation)

A fully local, Python multi‑agent system designed to run on a single GPU (12GB VRAM) and 32GB RAM, with:
- Main orchestrator using smolagents CodeAgent with Ollama LLM backend for structured tool/function calling
- Sub‑agents as smolagents-compatible tools (web, desktop, vision, speech, memory, code execution)
- Nested CodeAgent for sandboxed code execution with guardrails (import allowlist, file/network controls, step/output caps)
- Markdown Browser sub‑agent with embedding-based ranking (local embedding model) for token‑efficient web research
- Memory with local embeddings (Chroma + fastembed/sentence-transformers)
- Dashboard (FastAPI + HTMX) for live control: toggle tools, health, logs, testing, settings
- Discord integration for reading and responding to messages in guilds and DMs
- Persistent SQLite store for events, tool metrics, user settings, and fine‑tune dataset curation
- One‑click export of curated examples to JSONL
- Voice error notifications (“There is a problem with my AI.”) with a repeater loop
- VM‑friendly network setup (bind 0.0.0.0 to access dashboard from host)

## Quickstart

Requirements:
- Linux preferred (works in a Linux VM with GPU passthrough)
- Python 3.10+ (3.11 recommended)
- GPU with ~12GB VRAM for a 7–8B model (quantized)
- Ollama running locally
- Chrome + chromedriver if using Selenium for dynamic pages (optional)

Install:
```bash
python -m venv .venv && source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Playwright browser
playwright install chromium

# Optional TTS: Install espeak (required by NeuTTS-Air), then install NeuTTS-Air dependencies.
# Example (varies by distro): 
# Ubuntu/Debian: sudo apt install espeak
# Arch-based: sudo pacman -S espeak
# Mac OS: brew install espeak
```

## Configuring NeuTTS-Air for Voice Synthesis

NeuTTS-Air provides state-of-the-art voice cloning. To use TTS features:

1. **Reference audio is required** for voice cloning. Prepare:
   - A 3-15 second mono .wav file (16-44 kHz sample rate)
   - Clear, natural speech with minimal background noise
   - A text file with the exact transcript

2. **Configure via environment variables**:
   ```bash
   # Option 1: Use pre-encoded .pt file (recommended for best performance)
   export TTS_REF_AUDIO=/path/to/reference.pt
   export TTS_REF_TEXT=/path/to/transcript.txt
   
   # Option 2: Use raw audio file (will be encoded on first use)
   export TTS_REF_AUDIO=/path/to/reference.wav
   export TTS_REF_TEXT=/path/to/transcript.txt
   
   # Or provide text directly:
   export TTS_REF_TEXT="The exact transcript of the reference audio"
   ```

3. **Example reference files** are available in the [NeuTTS-Air samples](https://github.com/neuphonic/neutts-air/tree/main/samples).

Without reference audio configured, the speech tool will print text instead of generating audio.

For detailed TTS setup instructions, see [docs/TTS_SETUP.md](docs/TTS_SETUP.md).

Start services (dashboard binds 0.0.0.0 by default so your host can access the VM’s dashboard):
```bash
python -m src.app
```
Open the dashboard at:
- From inside VM: http://127.0.0.1:8008
- From host: http://<vm-ip>:8008

Tip: On libvirt’s default NAT, find the VM IP:
```bash
virsh domifaddr <vm-name>
# or
virsh net-dhcp-leases default
```

## Models and suggested configs

- Main LLM (Ollama):
  - qwen2:7b-instruct-q5_K_M (good tool calling), or llama3.1:8b-instruct-q4_K_M
  - Set num_ctx ~8–12k for 12GB VRAM comfort
- Vision:
  - **ImageRAG**: Fast CLIP-based image embeddings + OCR for efficient screenshot search (new!)
    - OpenCLIP ViT-B/32 for image-text similarity without VLM inference
    - Tile-based indexing (3x3 grid) for fine-grained region analysis
    - RapidOCR for local text extraction
    - ChromaDB for vector storage and retrieval
  - **VLM**: gemma3:4b-it-q4_K_M via Ollama (fallback for complex analysis)
- Embeddings (CPU‑friendly):
  - intfloat/e5-small-v2 or BAAI/bge-small-en-v1.5 or all-MiniLM-L6-v2
- Speech:
  - STT: faster-whisper small.en (streaming capable)
  - TTS: NeuTTS-Air with instant voice cloning (requires reference audio)

## Features

- Main orchestrator built on smolagents CodeAgent with structured tool calls and a shared “blackboard” state for awareness
- Sub‑agents (smolagents-compatible tools):
  - Web: Playwright‑based browser automation and Selenium fallback
  - Desktop: keyboard/mouse control + screenshots with OS-aware shortcuts
  - Vision: 
    - **ImageRAG** tools for fast image search (image_index, image_search, image_compare, image_find_ui)
    - Traditional VLM tool for detailed analysis (vision)
  - Speech: local STT with faster-whisper and TTS with NeuTTS-Air voice cloning
  - Memory: Chroma vector store with local embeddings (fastembed/sentence-transformers)
  - WriteFile: Safe file writing to .workspace directory with guardrails
  - Markdown Browser: DuckDuckGo search/fetch/browse → Markdown with citations and embedding‑based ranking
- Guardrails for WriteFile tool:
  - Restricted to .workspace directory only
  - Limited to safe file extensions (.py, .txt, .md, .csv, .json, .yaml, etc.)
  - Scans Python files for harmful code patterns (os.system, subprocess, eval, exec)
  - Warns about sensitive data patterns (passwords, API keys, secrets)
  - Blocks path traversal attempts
- Dashboard:
  - Toggle tools ON/OFF (feature flags)
  - Circuit breaker auto‑disables misbehaving tools
  - Live event log and health status
  - Per‑tool “Test” button
  - Settings: voice ON/OFF, speak‑on‑error toggle (persisted)
  - Dataset curation: label assistant responses “good/bad”
  - One‑click export curated examples to JSONL (served for download)

## SQLite persistence

- events: all agent/tool events (for audit and analytics)
- tool_metrics: calls, failures, latency, breaker state
- settings: voice_enabled, speak_on_error (persist across restarts)
- fine_tune_examples: turn‑level user/assistant pairs + label (“good”, “bad”, “unlabeled”)
- Export curated data:
  - Buttons in UI: “Export labeled JSONL” or “Export ALL JSONL”
  - Files appear under src/dashboard/static/exports/ and are downloadable directly

## VM and networking notes

- Default libvirt NAT allows host→guest access on VM’s 192.168.122.x IP
- Dashboard binds 0.0.0.0:8008 so the host can reach it
- Consider firewall rules to restrict access to your host only
- You can similarly expose Ollama (OLLAMA_HOST=0.0.0.0:11434) if needed, but lock it down

## Fine‑tuning guidance (LoRA persona)

- QLoRA/Unsloth on 7–8B is feasible on 12GB VRAM (int4)
- Include tool‑calling examples in your dataset to preserve function calling discipline
- Use the dataset curation screen to label “good/bad” turns and export JSONL

## Common issues

- Selenium/Chrome not installed: md_browser dynamic mode will fail; it will still work in static mode
- bitsandbytes missing GPU wheels: ensure compatible CUDA or run CPU inference for the VLM
- Desktop control in VM controls the VM desktop, not the host desktop (by design)
- Desktop tool automatically detects OS and desktop environment (e.g., KDE Plasma, GNOME) and provides OS-specific keyboard shortcut guidance to prevent cross-platform issues

## Discord Integration

The agent can integrate with Discord to read and respond to messages in guilds (servers) and DMs.

**Setup:**
1. Create a Discord application and bot at https://discord.com/developers/applications
2. Enable "Message Content Intent" in the Bot settings
3. Invite the bot to your server with appropriate permissions (Read Messages, Send Messages)
4. Set the bot token via environment variable:
   ```bash
   export DISCORD_BOT_TOKEN=your_bot_token_here
   ```

**Configuration via environment variables:**
- `DISCORD_BOT_TOKEN`: Your Discord bot token (required to enable Discord integration)
- `DISCORD_RESPOND_MODE`: How the bot responds (default: "mention")
  - `passive`: Only log messages, never reply
  - `mention`: Reply when mentioned or in DMs
  - `prefix`: Reply when message starts with command prefix or in DMs
  - `all`: Reply to every message (use with caution!)
- `DISCORD_COMMAND_PREFIX`: Command prefix for prefix mode (default: "!")
- `DISCORD_READ_ONLY`: Set to "true" to only log messages without ever replying (default: "false")

**Features:**
- Reads all messages in guilds and DMs (when bot has access)
- Publishes events to the dashboard event stream
- Uses the same AI pipeline as CLI interactions
- Supports DMs and guild channel messages
- Provides programmatic send methods (`send_dm`, `send_channel_message`)

## Vision System

The agent has two complementary vision systems for different use cases:

### ImageRAG (Fast, Embedding-based)

ImageRAG provides fast image understanding using CLIP embeddings and OCR, without requiring VLM inference:

**Tools:**
- `image_index(image_path, action_id=None)`: Index a screenshot with embeddings and OCR
- `image_search(question, image_id=None, k=6)`: Search indexed images using natural language
- `image_compare(image_a, image_b)`: Find text differences between two images
- `image_find_ui(query, k=5)`: Find UI elements from a prototype library

**How it works:**
1. Images are split into a 3x3 grid of tiles
2. Each tile is embedded using OpenCLIP (ViT-B/32)
3. OCR text is extracted with RapidOCR
4. Everything is stored in ChromaDB for fast retrieval
5. Natural language queries retrieve relevant regions instantly

**Benefits:**
- 10-100x faster than VLM for simple queries
- No GPU memory overhead (CLIP stays resident)
- Perfect for desktop automation and UI element tracking
- Can search across all indexed screenshots

**Example workflow:**
```python
# Index a screenshot
image_index("/path/to/screenshot.png", action_id="after_click")

# Search for specific content
image_search("find the submit button")

# Compare before/after states
image_compare("before.png", "after.png")
```

### VLM (Detailed, LLM-based)

Traditional VLM tool using Ollama for complex visual reasoning:

**Tool:**
- `vision(path, prompt=None)`: Analyze image with VLM (gemma3:4b-it-q4_K_M)

**Use when:**
- ImageRAG confidence is low
- Complex reasoning is needed
- Detailed image descriptions are required

**Best practices:**
- Use ImageRAG first for speed
- Escalate to VLM only when needed
- Keep the main agent's context window free

## Env vars

- AGENT_MODEL: Ollama model name for the main LLM (default: llama3.1:8b-instruct-q4_K_M)
- AGENT_DASH_HOST: default 0.0.0.0 (bind address)
- AGENT_DASH_PORT: default 8008
- TTS_REF_AUDIO: path to reference audio file for NeuTTS-Air voice cloning - supports `.pt` (pre-encoded, recommended) or `.wav` files (optional)
- TTS_REF_TEXT: text content or path to text file for the reference audio (optional)
- DISCORD_BOT_TOKEN: Discord bot token to enable Discord integration (optional)
- DISCORD_RESPOND_MODE: Bot response mode - passive/mention/prefix/all (default: mention)
- DISCORD_COMMAND_PREFIX: Command prefix for Discord bot (default: !)
- DISCORD_READ_ONLY: Set to "true" for read-only mode (default: false)

## Safety

- Code execution runs in a child process with guardrails; not a bulletproof sandbox (CPython cannot be fully sandboxed)
- Use dashboard toggles and the circuit breaker to disable risky tools quickly
- Consider VM snapshots before large experiments
