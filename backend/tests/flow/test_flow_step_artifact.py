"""流程 step 生成物字段。"""

from app.flow_runtime.step_record import build_flow_node_step


def test_build_flow_node_step_image():
    step = build_flow_node_step(
        node_id="n1",
        node_type="ImageGenerate",
        result={
            "kind": "image",
            "attachment_id": "a1111111-1111-1111-1111-111111111111",
            "mime_type": "image/png",
        },
    )
    assert step["artifact"]["kind"] == "image"
    assert step["artifact"]["attachment_id"].startswith("a111")


def test_build_flow_node_step_video():
    step = build_flow_node_step(
        node_id="n2",
        node_type="VideoGenerate",
        result={
            "kind": "video",
            "attachment_id": "b2222222-2222-2222-2222-222222222222",
            "mime_type": "video/mp4",
            "duration_sec": 5,
        },
    )
    assert step["artifact"]["kind"] == "video"


def test_build_flow_node_step_plain_text():
    step = build_flow_node_step(
        node_id="n3",
        node_type="LLMCall",
        result="hello",
    )
    assert "artifact" not in step
    assert step["output_preview"] == "hello"
