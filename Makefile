# Simple setup and run automation for the Local Multi-Agent Orchestrator

# Variables
VENV ?= .venv
PYTHON ?= $(VENV)/bin/python
PIP ?= $(VENV)/bin/pip

# Network bind for the dashboard (override on command line if needed)
AGENT_DASH_HOST ?= 0.0.0.0
AGENT_DASH_PORT ?= 8008

# Default target
.PHONY: all
all: setup dirs playwright run

# Create venv and install dependencies
.PHONY: setup
setup:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

# Install Playwright browser (Chromium)
.PHONY: playwright
playwright:
	$(PYTHON) -m playwright install chromium

# Create required local directories
.PHONY: dirs
dirs:
	mkdir -p .cache .chroma workspace app/src/dashboard/static/exports

# Optional: pull example models with Ollama (requires Ollama installed and running on the VM)
.PHONY: pull-models
pull-models:
	-ollama pull qwen2:7b-instruct-q5_K_M
	-ollama pull llama3.1:8b-instruct-q4_K_M

# Run the app (dashboard will bind to AGENT_DASH_HOST:AGENT_DASH_PORT)
.PHONY: run
run:
	AGENT_DASH_HOST=$(AGENT_DASH_HOST) AGENT_DASH_PORT=$(AGENT_DASH_PORT) $(PYTHON) -m app.src

# Developer run bound to localhost only
.PHONY: run-local
run-local:
	AGENT_DASH_HOST=127.0.0.1 AGENT_DASH_PORT=$(AGENT_DASH_PORT) $(PYTHON) -m app.src

# Quick sanity checks for key services (best-effort)
.PHONY: check
check:
	@echo "Checking Python: " && $(PYTHON) -V
	@echo "Checking FastAPI/uvicorn import: " && $(PYTHON) -c "import fastapi, uvicorn; print('OK')"
	@echo "Checking Playwright import: " && $(PYTHON) -c "import playwright; print('OK')"
	@echo "Checking Ollama endpoint (if running):" && curl -sS http://localhost:11434/api/tags || true

# Clean caches and artifacts (does not remove vector DB)
.PHONY: clean
clean:
	rm -rf .cache app/src/dashboard/static/exports/*

# Full reset (removes venv and Chroma data)
.PHONY: reset
reset: clean
	rm -rf $(VENV) .chroma

# One-click dataset export helper (requires server running)
# Usage examples:
#   make export-labeled
#   make export-all
.PHONY: export-labeled export-all
export-labeled:
	@echo "Requesting labeled dataset export..."
	@curl -sS -X POST -d "include_unlabeled=0" http://$(AGENT_DASH_HOST):$(AGENT_DASH_PORT)/examples/export || true
	@echo "\nCheck app/src/dashboard/static/exports for the exported JSONL."

export-all:
	@echo "Requesting full dataset export (including unlabeled)..."
	@curl -sS -X POST -d "include_unlabeled=1" http://$(AGENT_DASH_HOST):$(AGENT_DASH_PORT)/examples/export || true
	@echo "\nCheck app/src/dashboard/static/exports for the exported JSONL."
