"""智能体 API Key 明文生成与哈希（明文不落库）。"""

from __future__ import annotations

import hashlib
import secrets
import string

_ALPHABET = string.ascii_letters + string.digits


def hash_agent_api_key(plaintext: str) -> str:
    """返回明文密钥的 SHA-256 十六进制摘要（库中只保存哈希）。"""
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def _rand(n: int) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(n))


def generate_agent_api_key_secret() -> tuple[str, str, str]:
    """返回 (plaintext, prefix8, sha256_hex)。"""
    prefix = _rand(8)
    secret = _rand(32)
    plain = f"mil_{prefix}_{secret}"
    return plain, prefix, hash_agent_api_key(plain)
