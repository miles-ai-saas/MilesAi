"""字段加解密与脱敏。"""

from miles_core.field_crypto import decrypt_secret, encrypt_secret, mask_secret


def test_encrypt_roundtrip():
    plain = "minio-secret-key-12345"
    cipher = encrypt_secret(plain)
    assert cipher != plain
    assert decrypt_secret(cipher) == plain


def test_mask_secret():
    assert mask_secret("abcdefgh") == "****efgh"
