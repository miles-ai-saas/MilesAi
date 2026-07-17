"""粗检回复草稿是否含高风险索取用语。"""

_FORBIDDEN = ("验证码", "密码", "银行卡号", "cvv", "身份证照片")


def run(params):
    text = str(params.get("text") or "")
    hits = [w for w in _FORBIDDEN if w in text]
    return {
        "ok": len(hits) == 0,
        "hits": hits,
        "hint": "请移除敏感索取用语后再发送" if hits else "",
    }
