"""纯文本文件解码（TXT/MD/Markdown），供 loaders 文本分支调用。"""


def parse_text(data: bytes) -> str:
    """依次尝试 utf-8/gbk/latin-1，最后 replace 兜底。"""
    for encoding in ("utf-8", "gbk", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")
