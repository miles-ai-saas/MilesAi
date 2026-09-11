"""敏感字段对称加密（Fernet，密钥派生自 SECRET_KEY）。"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


def _fernet() -> Fernet:
    digest = hashlib.sha256(get_settings().secret_key.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_secret(plain: str) -> str:
    """Fernet 加密明文，返回可入库的 ASCII 密文。"""
    return _fernet().encrypt(plain.encode("utf-8")).decode("ascii")


def decrypt_secret(cipher: str) -> str:
    """解密 Fernet 密文；密钥不匹配或密文损坏时抛 ``ValueError``。"""
    try:
        return _fernet().decrypt(cipher.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("密钥解密失败") from exc


def mask_secret(value: str | None, *, visible_tail: int = 4) -> str | None:
    """保留末 ``visible_tail`` 位、其余以 ``*`` 遮蔽；空值返回 None。"""
    if not value:
        return None
    if len(value) <= visible_tail:
        return "*" * len(value)
    return "*" * (len(value) - visible_tail) + value[-visible_tail:]
