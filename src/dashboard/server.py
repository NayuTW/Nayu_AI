import time
import os
from typing import Any, Dict, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from src.agents.core.events import EventBus
from src.agents.core.registry import ToolRegistry
from src.agents.core.health import HealthChecker
from src.agents.notify.notifier import Notifier
from src.agents.core.store import SQLiteStore
from src.agents.core.agent_dispatcher import dispatch_to_agent
from src.agents.factory import AgentFactory

app = FastAPI()
app.mount("/static", StaticFiles(directory="src/dashboard/static"), name="static")

bus: EventBus = None
registry: ToolRegistry = None
health: HealthChecker = None
store: SQLiteStore = None
notifier: Notifier = None
agent: Any = None  # MainAgent instance

EXPORT_DIR = "src/dashboard/static/exports"
os.makedirs(EXPORT_DIR, exist_ok=True)

@app.get("/", response_class=HTMLResponse)
async def index():
    html = open("src/dashboard/templates/index.html", "r", encoding="utf-8").read()
    return HTMLResponse(html)

@app.get("/agents", response_class=HTMLResponse)
async def agents_page():
    """Serve the agents management page."""
    with open("src/dashboard/templates/agents.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.get("/tools", response_class=HTMLResponse)
async def tools_partial():
    tools = registry.list_status()
    rows = []
    for t in tools:
        status_class = "status-active" if t["enabled"] else "status-inactive"
        toggle_btn = f'''
        <form hx-post="/tools/toggle" hx-target="#tools-table" hx-swap="outerHTML" style="display:inline">
            <input type="hidden" name="name" value="{t['name']}">
            <input type="hidden" name="enabled" value="{str(not t['enabled']).lower()}">
            <button class="{"btn-secondary" if t["enabled"] else "btn-primary"}">{"Disable" if t["enabled"] else "Enable"}</button>
        </form>
        '''
        test_btn = f'''
        <form hx-post="/tools/test" hx-target="#event-stream" hx-swap="beforeend" style="display:inline;margin-left:6px">
            <input type="hidden" name="name" value="{t['name']}">
            <button class="btn-primary">Test</button>
        </form>
        '''
        rows.append(f"""
            <tr>
                <td>{t['name']}</td>
                <td><span class="status-badge {status_class}">{"Enabled" if t["enabled"] else "Disabled"}</span></td>
                <td>{t['calls']}</td>
                <td>{t['failures']}</td>
                <td>{int(t['avg_latency_ms'])}ms</td>
                <td style="max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="{t['last_error']}">{t['last_error']}</td>
                <td>{toggle_btn}{test_btn}</td>
            </tr>
        """)
    
    table = f'''
    <table id="tools-table" class="data-table">
      <thead>
        <tr><th>Name</th><th>Status</th><th>Calls</th><th>Failures</th><th>Avg Latency</th><th>Last Error</th><th>Actions</th></tr>
      </thead>
      <tbody>
        {''.join(rows)}
      </tbody>
    </table>
    '''
    return HTMLResponse(table)

@app.post("/tools/toggle", response_class=HTMLResponse)
async def toggle_tool(name: str = Form(...), enabled: str = Form(...)):
    en = enabled.lower() == "true"
    registry.enable(name, en)
    await bus.publish("tool.toggle", {"name": name, "enabled": en})
    return await tools_partial()

@app.post("/tools/test", response_class=HTMLResponse)
async def test_tool(name: str = Form(...)):
    rt = registry.get(name)
    if not rt or not rt.stats.enabled:
        await bus.publish("tool.test.error", {"name": name, "error": "Tool not found or disabled"})
        return HTMLResponse(f"\nTool {name} not found or disabled.\n")
    t0 = time.time()
    try:
        if name == "web":
            res = await rt.impl.run(action="goto", url="https://example.com")
        elif name == "memory":
            await rt.impl.run(action="remember", text="This is a test memory.")
            res = await rt.impl.run(action="recall", text="test memory", k=1)
        elif name == "speech":
            res = await rt.impl.run(action="speak", text="Test.")
        else:
            await bus.publish("tool.test.error", {"name": name, "error": "No test implemented"})
            return HTMLResponse(f"\nNo test implemented for {name}.\n")
        latency = (time.time() - t0) * 1000
        registry.record_success(name, latency)
        await bus.publish("tool.test.success", {"name": name, "latency_ms": latency, "summary": res.get("summary", "")})
        return HTMLResponse(f"\nTested {name}: OK in {int(latency)}ms\n")
    except Exception as e:
        registry.record_failure(name, str(e))
        await bus.publish("tool.test.error", {"name": name, "error": str(e)})
        return HTMLResponse(f"\nTested {name}: ERROR {e}\n")

@app.get("/settings", response_class=HTMLResponse)
async def settings_partial():
    speak_on_error = notifier.speak_on_error
    voice_enabled = notifier.voice_enabled
    html = f'''
    <div id="settings" class="settings-grid">
      <div class="setting-item">
        <div class="setting-info">
          <span class="setting-label">Speak on error</span>
          <span class="status-badge {'status-active' if speak_on_error else 'status-inactive'}">
            {'ON' if speak_on_error else 'OFF'}
          </span>
        </div>
        <form hx-post="/settings/toggle_speak_on_error" hx-target="#settings" hx-swap="outerHTML">
          <button class="{'btn-secondary' if speak_on_error else 'btn-primary'}">
            {'Disable' if speak_on_error else 'Enable'}
          </button>
        </form>
      </div>
      
      <div class="setting-item">
        <div class="setting-info">
          <span class="setting-label">Voice Synthesis</span>
          <span class="status-badge {'status-active' if voice_enabled else 'status-inactive'}">
            {'ON' if voice_enabled else 'OFF'}
          </span>
        </div>
        <form hx-post="/settings/toggle_voice" hx-target="#settings" hx-swap="outerHTML">
          <button class="{'btn-secondary' if voice_enabled else 'btn-primary'}">
            {'Disable' if voice_enabled else 'Enable'}
          </button>
        </form>
      </div>
    </div>
    '''
    return HTMLResponse(html)

@app.post("/settings/toggle_speak_on_error", response_class=HTMLResponse)
async def toggle_speak_on_error():
    notifier.set_speak_on_error(not notifier.speak_on_error)
    store.set_setting("speak_on_error", "1" if notifier.speak_on_error else "0")
    await bus.publish("settings.update", {"speak_on_error": notifier.speak_on_error})
    return await settings_partial()

@app.post("/chat", response_class=HTMLResponse)
async def send_chat(message: str = Form(...), agent_name: str = Form(None)):
    """Send a chat message from the dashboard to a chosen agent (default: main)."""
    text = (message or "").strip()
    if not text:
        return HTMLResponse("Please enter a message.", status_code=400)
    if agent is None:
        return HTMLResponse("Agent not available.", status_code=503)
    target_agent = AgentFactory.resolve_instance(agent_name, default=agent)
    if target_agent is None:
        return HTMLResponse(f"Agent '{agent_name}' not found.", status_code=400)
    try:
        await dispatch_to_agent(
            target_agent,
            text,
            source="dashboard",
            external_metadata={"target_agent": agent_name or "MainAgent"},
        )
        return HTMLResponse(f"Message sent to {target_agent.__class__.__name__}.")
    except Exception as e:
        await bus.publish("agent.error", {"error": str(e), "source": "dashboard"})
        return HTMLResponse(f"Error sending message: {e}", status_code=500)

@app.post("/settings/toggle_voice", response_class=HTMLResponse)
async def toggle_voice():
    notifier.set_voice(not notifier.voice_enabled)
    store.set_setting("voice_enabled", "1" if notifier.voice_enabled else "0")
    await bus.publish("settings.update", {"voice_enabled": notifier.voice_enabled})
    return await settings_partial()

@app.get("/examples", response_class=HTMLResponse)
async def examples_partial():
    examples = store.get_recent_examples(limit=50)
    rows = []
    for ex in examples:
        label = ex["label"]
        label_class = "status-active" if label == "good" else "status-inactive" if label == "bad" else ""
        label_disp = f'<span class="status-badge {label_class}">{label or "unlabeled"}</span>'
        btns = f'''
        <div class="agent-actions">
            <form hx-post="/examples/label" hx-target="#examples-container" hx-swap="innerHTML" style="display:inline">
              <input type="hidden" name="id" value="{ex['id']}">
              <input type="hidden" name="label" value="good">
              <button class="btn-primary">Good</button>
            </form>
            <form hx-post="/examples/label" hx-target="#examples-container" hx-swap="innerHTML" style="display:inline;margin-left:4px">
              <input type="hidden" name="id" value="{ex['id']}">
              <input type="hidden" name="label" value="bad">
              <button class="btn-danger">Bad</button>
            </form>
        </div>
        '''
        rows.append(f"""
        <tr>
          <td>{ex['id']}</td>
          <td style="white-space:pre-wrap;max-width:300px;font-size:12px;">{ex['user_text']}</td>
          <td style="white-space:pre-wrap;max-width:300px;font-size:12px;">{ex['assistant_text']}</td>
          <td>{label_disp}</td>
          <td>{btns}</td>
        </tr>
        """)
    
    table = f'''
    <div style="margin-bottom:16px; display: flex; gap: 8px;">
      <form hx-post="/examples/export" hx-target="#export-status" hx-swap="innerHTML">
        <input type="hidden" name="include_unlabeled" value="0">
        <button class="btn-primary">Export Labeled JSONL</button>
      </form>
      <form hx-post="/examples/export" hx-target="#export-status" hx-swap="innerHTML">
        <input type="hidden" name="include_unlabeled" value="1">
        <button class="btn-secondary">Export All JSONL</button>
      </form>
      <div id="export-status" style="align-self: center; font-size: 12px; color: #666;"></div>
    </div>
    <div style="overflow-x: auto;">
        <table id="examples-table" class="data-table">
          <thead>
            <tr><th>ID</th><th>User</th><th>Assistant</th><th>Label</th><th>Actions</th></tr>
          </thead>
          <tbody>
            {''.join(rows)}
          </tbody>
        </table>
    </div>
    '''
    return HTMLResponse(table)

@app.post("/examples/label", response_class=HTMLResponse)
async def examples_label(id: int = Form(...), label: str = Form(...)):
    if label not in ("good", "bad"):
        return await examples_partial()
    store.label_example(id, label)
    await bus.publish("dataset.label", {"id": id, "label": label})
    return await examples_partial()

@app.post("/examples/export", response_class=HTMLResponse)
async def examples_export(include_unlabeled: str = Form("0")):
    include_all = include_unlabeled == "1"
    ts = int(time.time())
    fname = f"dataset-{ts}-{'all' if include_all else 'labeled'}.jsonl"
    fpath = os.path.join(EXPORT_DIR, fname)
    n = store.export_examples_jsonl(fpath, include_unlabeled=include_all)
    msg = f'Exported {n} example(s) to <a href="/static/exports/{fname}" download>{fname}</a>.'
    await bus.publish("dataset.export", {"count": n, "file": fname, "include_unlabeled": include_all})
    return HTMLResponse(msg)

@app.get("/health", response_class=HTMLResponse)
async def health_partial():
    return HTMLResponse('<div id="health">Waiting for health updates...</div>')

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    q = await bus.subscribe()
    try:
        init_payload = {
            "tools": registry.list_status(),
            "settings": {
                "speak_on_error": notifier.speak_on_error,
                "voice_enabled": notifier.voice_enabled,
            },
            "events": store.get_recent_events(limit=100),
        }
        await ws.send_json({"type": "init", "payload": init_payload})
        while True:
            ev = await q.get()
            await ws.send_json({"type": ev.type, "payload": ev.payload, "ts": ev.ts})
    except WebSocketDisconnect:
        await bus.unsubscribe(q)

# ============ Agent Management Routes ============
@app.get("/api/agents/types")
async def get_agent_types():
    """Get list of available agent types to create."""
    types = agent.get_available_agent_types() if agent else []
    options = "".join([f'<option value="{t}">{t.title()}</option>' for t in types])
    return HTMLResponse(f'<option value="">Select agent type...</option>{options}')

@app.post("/api/agents/create")
async def create_agent(request: Request):
    """Create a new agent instance."""
    try:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            data = await request.json()
        else:
            data = await request.form()
    except Exception as e:
        return HTMLResponse(render_managed_agents_error(f"Invalid request data: {str(e)}"))
        
    agent_type = data.get("agent_type", "").strip()
    
    if not agent_type or not agent:
        return HTMLResponse(render_managed_agents_error("No agent type specified"))
    
    try:
        # Just create the instance, it will register itself in AgentFactory
        new_inst = AgentFactory.create(
            agent_type=agent_type,
            state=agent.state,
            bus=agent.bus,
            registry=agent.registry,
            notifier=agent.notifier,
            store=agent.store,
            session_id=agent.session_id
        )
        if not new_inst:
            return HTMLResponse(render_managed_agents_error(f"Failed to create agent of type {agent_type}"))
            
        # Return updated list of delegations
        agents_info = agent.get_managed_agents_summary() if agent else []
        return HTMLResponse(render_managed_agents_list(agents_info))
    except Exception as e:
        return HTMLResponse(render_managed_agents_error(str(e)))

@app.get("/api/agents/managed")
async def get_managed_agents():
    """Get HTML for managed agents list."""
    agents_info = agent.get_managed_agents_summary() if agent else []
    return HTMLResponse(render_managed_agents_list(agents_info))

@app.post("/api/agents/remove/{agent_name}")
async def remove_agent(agent_name: str):
    """Remove a managed agent."""
    if not agent:
        return HTMLResponse(render_managed_agents_error("Agent not available"))
    
    success = agent.remove_managed_agent(agent_name)
    agents_info = agent.get_managed_agents_summary()
    
    return HTMLResponse(render_managed_agents_list(agents_info))

@app.get("/api/agents/instances")
async def get_agent_instances():
    """Get list of all active agent instances."""
    instances = AgentFactory.all_instances().keys()
    options = ['<option value="">MainAgent (default)</option>']
    options.extend([f'<option value="{name}">{name}</option>' for name in instances])
    return HTMLResponse("".join(options))

@app.post("/api/agents/delegate")
async def delegate_agent(request: Request):
    """Delegate an agent to another."""
    try:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            data = await request.json()
        else:
            data = await request.form()
    except Exception as e:
        return HTMLResponse(render_managed_agents_error(f"Invalid request data: {str(e)}"))
        
    parent_name = data.get("parent_name", "").strip()
    child_name = data.get("child_name", "").strip()
    
    if not parent_name or not child_name:
        return HTMLResponse(render_managed_agents_error("Parent and child names required"))
    
    parent = AgentFactory.get_instance(parent_name)
    if not parent:
        return HTMLResponse(render_managed_agents_error(f"Parent agent '{parent_name}' not found"))
    
    success = parent.delegate_agent(child_name)
    
    # Return updated list for the main agent (usually what's displayed)
    agents_info = agent.get_managed_agents_summary() if agent else []
    return HTMLResponse(render_managed_agents_list(agents_info))

@app.post("/api/agents/undelegate/{parent_name}/{child_name}")
async def undelegate_agent(parent_name: str, child_name: str):
    """Remove delegation between agents."""
    parent = AgentFactory.get_instance(parent_name)
    if not parent:
        return HTMLResponse(render_managed_agents_error(f"Parent agent '{parent_name}' not found"))
    
    success = parent.undelegate_agent(child_name)
    
    # Return updated list for the main agent
    agents_info = agent.get_managed_agents_summary() if agent else []
    return HTMLResponse(render_managed_agents_list(agents_info))

# ============ Helper Functions ============
def render_managed_agents_list(agents_info: List[Dict[str, Any]]) -> str:
    """Render all delegations across all agent instances."""
    instances = AgentFactory.all_instances()
    sections = []
    
    for parent_name, inst in instances.items():
        managed = inst.get_managed_agents_info()
        if not managed:
            continue
            
        cards = ""
        for m in managed:
            child_name = m.get("name", "Unknown")
            desc = m.get("description", "No description")
            if len(desc) > 60:
                desc = desc[:60] + "..."
                
            cards += f"""
            <div class="agent-card">
                <div class="agent-info">
                    <h3>{child_name} <span class="status-badge status-active">MANAGED</span></h3>
                    <p>{desc}</p>
                </div>
                <div class="agent-actions">
                    <button class="btn-danger" hx-post="/api/agents/undelegate/{parent_name}/{child_name}" hx-target="#managed-agents-list" hx-swap="outerHTML">
                        Undelegate
                    </button>
                </div>
            </div>
            """
        
        sections.append(f"""
        <div class="parent-section" style="margin-bottom: 20px;">
            <h4 style="font-size: 14px; color: #0066cc; margin-bottom: 8px; border-bottom: 1px solid #eee;">Parent: {parent_name}</h4>
            {cards}
        </div>
        """)
    
    if not sections:
        return """
        <div id="managed-agents-list" hx-get="/api/agents/managed" hx-trigger="load">
            <p class="empty-state">No delegations established yet</p>
        </div>
        """
    
    return f'<div id="managed-agents-list" hx-get="/api/agents/managed" hx-trigger="load">{"".join(sections)}</div>'


def render_managed_agents_error(error: str) -> str:
    """Render error message."""
    return f"""
    <div id="managed-agents-list" hx-get="/api/agents/managed" hx-trigger="load">
        <p style="color: #a00; padding: 12px; background: #f5e5e5; border-radius: 4px;">Error: {error}</p>
    </div>
    """

def init_dashboard(shared_bus: EventBus, shared_registry: ToolRegistry, shared_health: HealthChecker, shared_store: SQLiteStore, shared_notifier: Notifier, shared_agent: Any = None):
    global bus, registry, health, store, notifier, agent
    bus = shared_bus
    registry = shared_registry
    health = shared_health
    store = shared_store
    notifier = shared_notifier
    agent = shared_agent
