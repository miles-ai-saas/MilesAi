"""服务线阶段模板解析单元测试。"""

from app.biz.services.service_line_template import initial_stage, parse_stage_names


def test_parse_stage_names_from_string_list():
    assert parse_stage_names(["调研", "VI 方案"]) == ["调研", "VI 方案"]


def test_parse_stage_names_from_object_list():
    stages = [{"name": "脚本", "index": 0}, {"name": "分镜", "index": 1}]
    assert parse_stage_names(stages) == ["脚本", "分镜"]


def test_initial_stage_returns_first():
    stage, index = initial_stage(["概念", "落地"])
    assert stage == "概念"
    assert index == 0


def test_initial_stage_empty():
    stage, index = initial_stage([])
    assert stage is None
    assert index == 0
