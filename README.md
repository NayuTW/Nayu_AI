# Local Multi‑Agent Orchestrator (Fully Offline, Dashboard + Curation)

A fully local, Python multi‑agent system designed to run on a single GPU (12GB VRAM) and 32GB RAM, with:
- Main orchestrator LLM (Ollama) using structured tool/function calling
- Sub‑agents as tools (web, desktop, vision, speech, memory, code execution)
- CodeAgent with guardrails (import allowlist, file/network controls, step/output caps)
- Markdown Browser sub‑agent with embedded ranking (small local embedding model) for token‑efficient web research
- Memory with local embeddings (Chroma + e5/bge/MiniLM)
- Dashboard (FastAPI + HTMX) for live control: toggle tools, health, logs, testing, settings
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
pip install \
  aiohttp fastapi uvicorn \
  playwright pillow mss pyautogui \
  duckduckgo-search readability-lxml html2text \
  chromadb sentence-transformers fastembed \
  faster-whisper \
  transformers accelerate bitsandbytes \
  beautifulsoup4 lxml

# Playwright browser
playwright install chromium

# Optional TTS: Piper (install via your package manager), and a voice model.
# Example (varies by distro): sudo pacman -S piper-tts  (Arch-based)
```

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
  - Qwen/Qwen2-VL-2B-Instruct (transformers, 4‑bit), or LLaVA 7B via llava.cpp
- Embeddings (CPU‑friendly):
  - intfloat/e5-small-v2 or BAAI/bge-small-en-v1.5 or all-MiniLM-L6-v2
- Speech:
  - STT: faster-whisper small.en (streaming capable)
  - TTS: Piper with a local voice

## Features

- Orchestrator with structured tool calls and a shared “blackboard” state for awareness
- Sub‑agents:
  - Web: Playwright‑based browser actions
  - Desktop: keyboard/mouse + screenshots
  - Vision: VLM for screenshots/OCR
  - Speech: local STT/TTS
  - Memory: Chroma vector store, local embeddings
  - Code execution: smolagents CodeAgent, wrapped as a tool, with guardrails
  - Markdown Browser: search/fetch/browse → Markdown with citations and embedding‑based ranking
- Guardrails for CodeAgent child process:
  - Import allowlist
  - File IO disabled by default (optional read‑only jail)
  - Subprocess and shell blocked
  - Requests only allowed from approved tool modules (e.g., Markdown browser)
  - Step and stdout/err caps
  - Optional CPU and memory limits (POSIX)
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

## Env vars

- AGENT_DASH_HOST: default 0.0.0.0 (bind address)
- AGENT_DASH_PORT: default 8008

## Safety

- Code execution runs in a child process with guardrails; not a bulletproof sandbox (CPython cannot be fully sandboxed)
- Use dashboard toggles and the circuit breaker to disable risky tools quickly
- Consider VM snapshots before large experiments