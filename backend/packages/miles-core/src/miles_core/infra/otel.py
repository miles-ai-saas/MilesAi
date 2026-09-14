"""OpenTelemetry OTLP 导出（默认关闭；依赖在 miles-server 无条件声明，导入失败时 no-op）。"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)

_provider: Any = None
_instrumentor: Any = None


def _server_request_hook(span, scope) -> None:
    if span is None or not span.is_recording():
        return
    for key, value in scope.get("headers", ()):
        if key.lower() == b"x-trace-id":
            span.set_attribute("miles.trace_id", value.decode("latin-1"))
            return


def setup_otel(settings, app: FastAPI | None = None) -> None:
    """启用 OTLP span 导出并可选 instrument FastAPI app。"""
    global _provider, _instrumentor

    if not settings.otel_enabled:
        return

    endpoint = (settings.otel_exporter_otlp_endpoint or "").strip()
    if not endpoint:
        logger.warning("OTel 已启用但 OTEL_EXPORTER_OTLP_ENDPOINT 为空，跳过导出")
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        logger.warning(
            "OTEL_ENABLED=true 但未安装 OpenTelemetry（应由 miles-server 依赖提供），跳过导出",
        )
        return

    service_name = settings.otel_service_name or "milesai-api"
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
    trace.set_tracer_provider(provider)
    _provider = provider

    if app is not None:
        instrumentor = FastAPIInstrumentor()
        instrumentor.instrument_app(app, server_request_hook=_server_request_hook)
        _instrumentor = instrumentor

    logger.info("OpenTelemetry OTLP 导出已启用: endpoint=%s service=%s", endpoint, service_name)


def shutdown_otel() -> None:
    """刷新并关闭 TracerProvider，反注册 FastAPI instrumentation。"""
    global _provider, _instrumentor

    if _instrumentor is not None:
        try:
            _instrumentor.uninstrument()
        except Exception:
            logger.exception("OTel FastAPI 反注册失败")
        _instrumentor = None

    if _provider is not None:
        try:
            _provider.force_flush()
            _provider.shutdown()
        except Exception:
            logger.exception("OTel TracerProvider 关闭失败")
        _provider = None
