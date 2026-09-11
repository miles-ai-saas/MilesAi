import pytest

from miles_common.exceptions import BadRequestError
from miles_core.url_security import validate_outbound_url


def test_rejects_localhost(monkeypatch):
    monkeypatch.setattr(
        "miles_core.url_security.get_settings",
        lambda: type("S", (), {"mcp_allow_private_hosts": False})(),
    )
    with pytest.raises(BadRequestError, match="本机"):
        validate_outbound_url("http://127.0.0.1/api")


def test_accepts_public_https():
    assert validate_outbound_url("https://api.example.com/v1") == "https://api.example.com/v1"
