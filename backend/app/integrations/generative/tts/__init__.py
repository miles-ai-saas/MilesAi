"""TTS 语音合成 Integration Layer（re-export service 入口；模型解析见 L1 ``generative_model_resolve``）。"""

from app.integrations.generative.tts.service import generate_speech_for_model

__all__ = ["generate_speech_for_model"]
