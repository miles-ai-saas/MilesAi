"""大模型调用（OpenAI 兼容接口）。"""

import httpx

from app.common.exceptions import AppError
from app.models.model import ModelConfig


async def chat_completion(
    model: ModelConfig,
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> str:
    api_base = (model.api_base or "https://api.openai.com/v1").rstrip("/")
    url = f"{api_base}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if model.api_key_encrypted:
        headers["Authorization"] = f"Bearer {model.api_key_encrypted}"

    payload = {
        "model": model.model_name,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code >= 400:
            raise AppError(f"模型调用失败: {resp.text}", status_code=502)
        data = resp.json()
    choices = data.get("choices") or []
    if not choices:
        raise AppError("模型返回为空", status_code=502)
    return choices[0]["message"]["content"]
