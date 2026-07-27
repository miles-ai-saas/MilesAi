"""生图 prompt 护栏测试。"""

from app.integrations.generative.image.prompt_guard import (
    sanitize_image_prompt,
    user_requests_image_collage,
)


def test_user_requests_collage_keywords():
    assert user_requests_image_collage("请做一张四宫格组图")
    assert user_requests_image_collage("给我拼接展示")
    assert not user_requests_image_collage("生成 4 张商品主图")
    assert not user_requests_image_collage("白色背景产品图")


def test_sanitize_strips_collage_and_appends_single_shot():
    raw = "红色运动鞋，请生成四宫格布局展示正面侧面"
    out = sanitize_image_prompt(raw, allow_collage=False)
    assert "请生成四宫格" not in out
    assert "独立完整画面" in out
    assert "红色运动鞋" in out
    assert "正面侧面" in out


def test_sanitize_keeps_collage_when_allowed():
    raw = "红色运动鞋四宫格拼接"
    out = sanitize_image_prompt(raw, allow_collage=True)
    assert out == raw
