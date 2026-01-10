import asyncio
import inspect
import time
from typing import Any, Dict, Optional

from src.agents.core.output_handler import AgentOutputHandler


def _ensure_jsonable(obj: Any) -> Any:
    """Recursively convert an object to a JSON-serializable form."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj

    if isinstance(obj, dict):
        return {str(k): _ensure_jsonable(v) for k, v in obj.items()}

    if isinstance(obj, (list, tuple)):
        return [_ensure_jsonable(item) for item in obj]

    try:
        if hasattr(obj, "model_dump"):
            return _ensure_jsonable(obj.model_dump())
        if hasattr(obj, "dict"):
            return _ensure_jsonable(obj.dict())
        if hasattr(obj, "__dict__"):
            return _ensure_jsonable(vars(obj))
    except Exception:
        return str(obj)

    return str(obj)


def _extract_final_text(raw_result: Any, final_answers: Any, bus: Optional[Any] = None) -> str:
    """Prefer final_answers text when available, otherwise fall back to result."""
    handler = AgentOutputHandler(bus=bus)
    extracted = handler.extract_final_answer_text(final_answers) if final_answers else None

    if raw_result is None:
        raw_text = ""
    elif isinstance(raw_result, str):
        raw_text = raw_result
    else:
        raw_text = str(raw_result)

    final_text = extracted or raw_text
    return final_text.strip() or "I processed your request."


async def dispatch_to_agent(
    target_agent: Any,
    message: str,
    source: str = "cli",
    external_metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Send a prompt directly to a specific agent, preferring the agent's own handler.

    If the agent does not implement `handle_user_message`, this will fall back to
    calling its `run` method while still emitting agent.input/agent.output events.
    """
    if target_agent is None:
        return "Agent not available."

    metadata = external_metadata or {}
    agent_name = target_agent.__class__.__name__
    handler = getattr(target_agent, "handle_user_message", None)

    if handler and inspect.iscoroutinefunction(handler):
        return await handler(
            user_text=message,
            source=source,
            external_metadata=metadata,
        )

    bus = getattr(target_agent, "bus", None)
    session_id = getattr(target_agent, "session_id", "")

    if bus:
        await bus.publish(
            "agent.input",
            {
                "text": message,
                "source": source,
                "meta": metadata,
                "session_id": session_id,
                "agent": agent_name,
            },
        )

    t0 = time.time()
    try:
        run_fn = getattr(target_agent, "run", None)
        if run_fn is None:
            raise RuntimeError("Agent cannot process messages")

        if inspect.iscoroutinefunction(run_fn):
            run_output = await run_fn(message)
        else:
            run_output = await asyncio.to_thread(run_fn, message)
        final_answers = getattr(run_output, "final_answers", None)
        raw_result = getattr(run_output, "output", run_output)
        final_text = _extract_final_text(raw_result, final_answers, bus=bus)
        latency_ms = (time.time() - t0) * 1000

        if bus:
            payload = {
                "text": final_text,
                "latency_ms": latency_ms,
                "session_id": session_id,
                "final_answers": _ensure_jsonable(final_answers)
                if final_answers is not None
                else None,
                "agent": agent_name,
            }
            await bus.publish("agent.output", payload)

        return final_text
    except Exception as e:
        error_msg = f"Error processing request: {e}"
        if bus:
            await bus.publish("agent.error", {"error": str(e), "agent": agent_name})
        return error_msg
