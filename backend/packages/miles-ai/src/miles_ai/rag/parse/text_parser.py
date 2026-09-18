"""纯文本文件解码（TXT/MD/Markdown），供 loaders 文本分支调用。"""


def parse_text(data: bytes) -> str:
    """依次尝试 utf-8/gbk/latin-1，最后 replace 兜底。"""
    for encoding in ("utf-8", "gbk", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            # 静默可接受：该编码解不出即试下一种（末尾还有 errors="replace" 兜底），异常本身即控制流信号。
            continue
    return data.decode("utf-8", errors="replace")
