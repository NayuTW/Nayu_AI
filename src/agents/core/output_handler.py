from typing import Any, Optional

from src.agents.core.events import EventBus


class AgentOutputHandler:
    """
    Encapsulates agent output handling so it can be reused across agents.
    Responsible for extracting final answers and publishing agent.output events.
    """

    ANSWER_KEYS = ("final_answer", "answer", "output", "content", "text")

    def __init__(self, bus: EventBus):
        self.bus = bus

    def extract_final_answer_text(self, final_answers: Any) -> Optional[str]:
        """
        Extract readable text from smolagents final_answers structures.
        Key priority: final_answer > answer > output > content > text
        """
        texts: list[str] = []

        def _extract_from_item(item: Any) -> Optional[str]:
            if item is None:
                return None
            if isinstance(item, dict):
                for key in self.ANSWER_KEYS:
                    if key in item and item[key] is not None:
                        return str(item[key])
                return None
            return str(item)

        if isinstance(final_answers, (list, tuple)):
            for ans in final_answers:
                val = _extract_from_item(ans)
                if val is not None:
                    texts.append(val)
        else:
            val = _extract_from_item(final_answers)
            if val is not None:
                texts.append(val)

        stripped_texts = [t.strip() for t in texts]
        combined = "\n\n".join([t for t in stripped_texts if t])
        return combined or None

    async def publish_output(
        self,
        text: str,
        latency_ms: float,
        session_id: str,
        final_answers: Any,
        ensure_jsonable,
    ) -> None:
        """
        Publish agent.output event with optional final_answers payload.
        """
        payload = {
            "text": text,
            "latency_ms": latency_ms,
            "session_id": session_id,
            "final_answers": ensure_jsonable(final_answers) if final_answers else None,
        }
        await self.bus.publish("agent.output", payload)
