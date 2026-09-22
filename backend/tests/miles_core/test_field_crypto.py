"""字段加解密与脱敏。"""

from miles_core import field_crypto
from miles_core.field_crypto import decrypt_secret, encrypt_secret, mask_secret


def test_encrypt_roundtrip():
    plain = "minio-secret-key-12345"
    cipher = encrypt_secret(plain)
    assert cipher != plain
    assert decrypt_secret(cipher) == plain


def test_mask_secret():
    assert mask_secret("abcdefgh") == "****efgh"


def test_fernet_instance_reused(monkeypatch):
    field_crypto._fernet_singleton = None
    a = field_crypto._get_fernet()
    b = field_crypto._get_fernet()
    assert a is b
