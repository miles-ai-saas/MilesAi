"""钩子元数据 API。"""

from miles_portal.tenant.hooks.meta import hook_meta_dict


def test_hook_meta_dict_covers_enums():
    data = hook_meta_dict()
    assert len(data["triggers"]) == 7
    assert len(data["scopes"]) == 5
    assert any(t.value == "before_call" for t in data["triggers"])
    assert all(t.label for t in data["triggers"])
