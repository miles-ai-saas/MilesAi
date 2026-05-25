"""纯文本文件解码（TXT/MD）。"""


def parse_text(data: bytes) -> str:
    """依次尝试 utf-8/gbk/latin-1，最后 replace 兜底。"""
    for encoding in ("utf-8", "gbk", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")
