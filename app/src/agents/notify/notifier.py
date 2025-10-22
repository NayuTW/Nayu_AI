class Notifier:
    def __init__(self, speech_tool=None, voice_enabled: bool = False, speak_on_error: bool = True):
        self.speech_tool = speech_tool
        self.voice_enabled = voice_enabled
        self.speak_on_error = speak_on_error

    def set_voice(self, enabled: bool):
        self.voice_enabled = enabled

    def set_speak_on_error(self, enabled: bool):
        self.speak_on_error = enabled

    async def alert(self, text: str):
        if self.voice_enabled and self.speech_tool:
            try:
                await self.speech_tool.run(action="speak", text=text)
            except Exception:
                pass
        return text