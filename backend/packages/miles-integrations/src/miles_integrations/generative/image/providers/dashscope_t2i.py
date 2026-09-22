"""阿里云 DashScope 文生图（万相）。"""

from __future__ import annotations

import httpx

from miles_common.exceptions import AppError, BadRequestError
from miles_core.models.model import ModelConfig
from miles_core.models.model.catalog import DEFAULT_API_BASES, ModelVendor
from miles_integrations.generative.constants import DEFAULT_IMAGE_SIZE
from miles_integrations.generative.image.providers._decoding import decode_b64_image
from miles_integrations.http_constants import HTTP_DEFAULT_TIMEOUT_SEC


def _dashscope_size(size: str) -> str:
    """OpenAI 1024x1024 → DashScope 1024*1024。"""
    return size.replace("x", "*").replace("X", "*")


async def generate_dashscope_t2i(
    model: ModelConfig,
    *,
    prompt: str,
    size: str,
    n: int = 1,
    reference_image_data_url: str | None = None,
    progress: object | None = None,
) -> list[bytes]:
    """与 openai/volcengine Provider 对齐：参考图参数名为 ``reference_image_data_url``。"""
    api_key = model.api_key_encrypted
    if not api_key:
        raise BadRequestError(f"模型「{model.name}」未配置 API Key")

    api_base = (model.api_base or DEFAULT_API_BASES.get(ModelVendor.QWEN.value) or "https://dashscope.aliyuncs.com/api/v1").rstrip("/")
    url = f"{api_base}/services/aigc/text2image/image-synthesis"

    wan_model = model.model_name or "wanx-v1"
    input_body: dict = {"prompt": prompt}
    if reference_image_data_url:
        # wanx-v1 等：垫图 ref_image（URL 或 data URL）
        input_body["ref_image"] = reference_image_data_url
    body = {
        "model": wan_model,
        "input": input_body,
        "parameters": {
            "size": _dashscope_size(size or DEFAULT_IMAGE_SIZE),
            "n": min(max(n, 1), 4),
        },
    }
    if reference_image_data_url:
        body["parameters"]["ref_strength"] = 0.85
        body["parameters"]["ref_mode"] = "repaint"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    import logging

    _log = logging.getLogger(__name__)

    should_cancel = progress.is_cancelled if progress and hasattr(progress, "is_cancelled") else None

    async with httpx.AsyncClient(timeout=HTTP_DEFAULT_TIMEOUT_SEC) as client:
        # 只记可安全观察的请求特征：Authorization 是凭据，body 里可能带整段 base64 垫图。
        _log.info("万相生图请求 → POST %s model=%s", url, wan_model)
        submit = await client.post(url, headers=headers, json=body)
        if submit.status_code >= 400:
            _log.warning("万相生图失败 (%s): %s", submit.status_code, submit.text[:1000])
            raise AppError(f"万相生图失败 ({submit.status_code}): {submit.text[:500]}", status_code=502)

        task = submit.json()
        task_id = (task.get("output") or {}).get("task_id") or task.get("task_id")
        if not task_id:
            return await _parse_results_async(task, client)

        task_url = f"{api_base}/tasks/{task_id}"
        import asyncio

        for _ in range(120):
            if should_cancel and await should_cancel():
                from miles_integrations.generative.jobs.errors import GenerativeJobCancelled

                raise GenerativeJobCancelled()
            await asyncio.sleep(2)
            poll = await client.get(task_url, headers={"Authorization": f"Bearer {api_key}"})
            if poll.status_code >= 400:
                raise AppError(f"万相任务查询失败: {poll.text[:300]}", status_code=502)
            data = poll.json()
            status = (data.get("output") or {}).get("task_status") or data.get("task_status")
            if status == "SUCCEEDED":
                return await _parse_results_async(data, client)
            if status in ("FAILED", "CANCELED"):
                msg = (data.get("output") or {}).get("message") or data.get("message") or status
                raise AppError(f"万相生图失败: {msg}", status_code=502)

    raise AppError("万相生图任务超时", status_code=504)


async def _parse_results_async(payload: dict, client: httpx.AsyncClient) -> list[bytes]:
    """同步返回体 → 图片字节；脏 base64 跳过，全部失败才报「无图片数据」。"""
    output = payload.get("output") or payload
    results = output.get("results") or output.get("images") or []
    if not results and "results" in payload:
        results = payload["results"]
    out: list[bytes] = []
    for item in results:
        if isinstance(item, dict):
            b64 = item.get("b64_image") or item.get("b64_json")
            if b64:
                blob = decode_b64_image(b64)
                if blob is not None:
                    out.append(blob)
                continue
            img_url = item.get("url")
            if img_url:
                resp = await client.get(img_url)
                if resp.status_code < 400:
                    out.append(resp.content)
    if not out:
        raise AppError("万相返回中无图片数据", status_code=502)
    return out
