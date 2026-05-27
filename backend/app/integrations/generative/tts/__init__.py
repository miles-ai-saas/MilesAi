"""TTS 语音合成 Integration Layer（re-export service 入口）。"""

from app.integrations.generative.tts.service import (
    generate_speech_for_model,
    resolve_tts_model,
)

__all__ = [
    "generate_speech_for_model",
    "resolve_tts_model",
]
