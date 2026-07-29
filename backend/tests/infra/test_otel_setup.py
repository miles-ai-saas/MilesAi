"""OpenTelemetry 可选导出：默认关闭时不影响启动。"""

from unittest.mock import MagicMock

from app.infra import otel


def test_setup_otel_disabled_is_noop():
    settings = MagicMock(
        otel_enabled=False,
        otel_exporter_otlp_endpoint="",
        otel_service_name="milesai-api",
    )
    otel.setup_otel(settings)
    otel.shutdown_otel()


def test_setup_otel_enabled_empty_endpoint_is_noop():
    settings = MagicMock(
        otel_enabled=True,
        otel_exporter_otlp_endpoint="",
        otel_service_name="milesai-api",
    )
    otel.setup_otel(settings)
    assert otel._provider is None
    assert otel._instrumentor is None
    otel.shutdown_otel()


def test_setup_otel_enabled_missing_extra_is_noop(monkeypatch):
    settings = MagicMock(
        otel_enabled=True,
        otel_exporter_otlp_endpoint="http://localhost:4317",
        otel_service_name="milesai-api",
    )

    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("opentelemetry"):
            raise ImportError("no otel extra")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    otel.setup_otel(settings)
    assert otel._provider is None
    otel.shutdown_otel()
