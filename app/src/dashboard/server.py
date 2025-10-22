import time
import os

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.src.agents.core.events import EventBus
from app.src.agents.core.registry import ToolRegistry
from app.src.agents.core.health import HealthChecker
from app.src.agents.notify.notifier import Notifier
from app.src.agents.core.store import SQLiteStore

app = FastAPI()
app.mount("/static", StaticFiles(directory="app/src/dashboard/static"), name="static")

bus: EventBus = None
registry: ToolRegistry = None
health: HealthChecker = None
store: SQLiteStore = None
notifier: Notifier = None

EXPORT_DIR = "app/src/dashboard/static/exports"
os.makedirs(EXPORT_DIR, exist_ok=True)

@app.get("/", response_class=HTMLResponse)
async def index():
    html = open("app/src/dashboard/templates/index.html", "r", encoding="utf-8").read()
    return HTMLResponse(html)

@app.get("/tools", response_class=HTMLResponse)
async def tools_partial():
    tools = registry.list_status()
    rows = []
    for t in tools:
        toggle_btn = f'''
        <form hx-post="/tools/toggle" hx-target="#tools-table" hx-swap="outerHTML" style="display:inline">
            <input type="hidden" name="name" value="{t['name']}">
            <input type="hidden" name="enabled" value="{str(not t['enabled']).lower()}">
            <button>{"Disable" if t["enabled"] else "Enable"}</button>
        </form>
        '''
        test_btn = f'''
        <form hx-post="/tools/test" hx-target="#events" hx-swap="beforeend" style="display:inline;margin-left:6px">
            <input type="hidden" name="name" value="{t['name']}">
            <button>Test</button>
        </form>
        '''
        rows.append(f"<tr><td>{t['name']}</td><td>{t['enabled']}</td><td>{t['calls']}</td><td>{t['failures']}</td><td>{int(t['avg_latency_ms'])}</td><td>{t['last_error']}</td><td>{toggle_btn}{test_btn}</td></tr>")
    table = f'''
    <table id="tools-table" border="1" cellspacing="0" cellpadding="6">
      <tr><th>Name</th><th>Enabled</th><th>Calls</th><th>Failures</th><th>Avg ms</th><th>Last error</th><th>Actions</th></tr>
      {''.join(rows)}
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
    <div id="settings">
      <form hx-post="/settings/toggle_speak_on_error" hx-target="#settings" hx-swap="outerHTML" style="display:inline">
        <button>{'Disable' if speak_on_error else 'Enable'} "Speak on error"</button>
      </form>
      <span style="margin-left:8px">Speak on error: <b>{'ON' if speak_on_error else 'OFF'}</b></span>
      <br/>
      <form hx-post="/settings/toggle_voice" hx-target="#settings" hx-swap="outerHTML" style="display:inline">
        <button>{'Disable' if voice_enabled else 'Enable'} Voice</button>
      </form>
      <span style="margin-left:8px">Voice: <b>{'ON' if voice_enabled else 'OFF'}</b></span>
    </div>
    '''
    return HTMLResponse(html)

@app.post("/settings/toggle_speak_on_error", response_class=HTMLResponse)
async def toggle_speak_on_error():
    notifier.set_speak_on_error(not notifier.speak_on_error)
    store.set_setting("speak_on_error", "1" if notifier.speak_on_error else "0")
    await bus.publish("settings.update", {"speak_on_error": notifier.speak_on_error})
    return await settings_partial()

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
        label_disp = f'<span style="padding:2px 6px;border-radius:4px;background:{("#cfc" if label=="good" else "#fcc" if label=="bad" else "#eee")};">{label}</span>'
        btns = f'''
        <form hx-post="/examples/label" hx-target="#examples-table" hx-swap="outerHTML" style="display:inline">
          <input type="hidden" name="id" value="{ex['id']}">
          <input type="hidden" name="label" value="good">
          <button>Mark Good</button>
        </form>
        <form hx-post="/examples/label" hx-target="#examples-table" hx-swap="outerHTML" style="display:inline;margin-left:6px">
          <input type="hidden" name="id" value="{ex['id']}">
          <input type="hidden" name="label" value="bad">
          <button>Mark Bad</button>
        </form>
        '''
        rows.append(f"""
        <tr>
          <td>{ex['id']}</td>
          <td style="white-space:pre-wrap;max-width:360px">{ex['user_text']}</td>
          <td style="white-space:pre-wrap;max-width:360px">{ex['assistant_text']}</td>
          <td>{label_disp}</td>
          <td>{btns}</td>
        </tr>
        """)
    table = f'''
    <div style="margin-bottom:10px">
      <form hx-post="/examples/export" hx-target="#export-status" hx-swap="innerHTML" style="display:inline">
        <input type="hidden" name="include_unlabeled" value="0">
        <button>Export labeled JSONL</button>
      </form>
      <form hx-post="/examples/export" hx-target="#export-status" hx-swap="innerHTML" style="display:inline;margin-left:6px">
        <input type="hidden" name="include_unlabeled" value="1">
        <button>Export ALL JSONL</button>
      </form>
      <div id="export-status" style="display:inline-block;margin-left:10px;color:#555"></div>
    </div>
    <table id="examples-table" border="1" cellspacing="0" cellpadding="6">
      <tr><th>ID</th><th>User</th><th>Assistant</th><th>Label</th><th>Actions</th></tr>
      {''.join(rows)}
    </table>
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

def init_dashboard(shared_bus: EventBus, shared_registry: ToolRegistry, shared_health: HealthChecker, shared_store: SQLiteStore, shared_notifier: Notifier):
    global bus, registry, health, store, notifier
    bus = shared_bus
    registry = shared_registry
    health = shared_health
    store = shared_store
    notifier = shared_notifier