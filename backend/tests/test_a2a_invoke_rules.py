from app.app_tenant.a2a.invoke import evaluate_rule_triggered_peers


class _Ref:
    def __init__(self, peer_id: str, keywords: list[str], enabled: bool = True):
        self.peer_id = peer_id
        self.enabled = enabled
        self.trigger_keywords = keywords
        self.peer = type("P", (), {"id": peer_id, "name": "ext"})()


def test_rule_keywords_match():
    refs = [_Ref("a", ["合作伙伴", "外部"])]
    hits = evaluate_rule_triggered_peers("请转合作伙伴处理", refs)
    assert len(hits) == 1

    hits2 = evaluate_rule_triggered_peers("普通问题", refs)
    assert len(hits2) == 0
