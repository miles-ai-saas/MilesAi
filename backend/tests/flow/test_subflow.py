"""SubFlow 节点与校验测试。"""

from uuid import uuid4

from app.flow_runtime.constants import MAX_SUBFLOW_DEPTH
from app.flow_runtime.subflow.resolve import build_child_context, iter_subflow_nodes
from app.flow_runtime.types import RunContext
from app.integrations.langgraph.compiler import validate_graph_for_compile


def test_validate_graph_subflow_missing_id():
    graph = {
        "nodes": [
            {
                "id": "sf1",
                "type": "SubFlow",
                "data": {"type": "SubFlow", "label": "子流程"},
            }
        ],
        "edges": [],
    }
    report = validate_graph_for_compile(graph)
    assert not report.compilable
    assert any(e.get("code") == "missing_sub_flow_id" for e in report.error_details)


def test_iter_subflow_nodes():
    graph = {
        "nodes": [
            {"id": "a", "type": "TextInput", "data": {"type": "TextInput"}},
            {
                "id": "sf1",
                "type": "SubFlow",
                "data": {"type": "SubFlow", "sub_flow_id": str(uuid4())},
            },
        ],
        "edges": [],
    }
    items = iter_subflow_nodes(graph)
    assert len(items) == 1
    assert items[0][0] == "sf1"


def test_build_child_context_input_mapping():
    parent = RunContext(
        tenant_id=str(uuid4()),
        inputs={"query": "hello"},
        kb_ids=["kb-1"],
        subflow_depth=1,
        current_flow_id=str(uuid4()),
    )
    child = build_child_context(
        parent,
        {"input": "from-edge"},
        {
            "input_mapping": {"query": "input"},
            "sub_flow_id": str(uuid4()),
        },
        parent_flow_id=parent.current_flow_id,
        parent_node_id="sf1",
        child_flow_id=str(uuid4()),
    )
    assert child.inputs.get("query") == "from-edge"
    assert child.subflow_depth == 2
    assert child.kb_ids == ["kb-1"]


def test_build_child_context_forwards_resolve_model_and_usage_sink():
    """SubFlow 子 RunContext 透传 resolve_model / usage_sink（画布 LLM 注入链到子流程）。"""

    async def fake_resolve(model_config_id: str):
        return None

    usage_sink = object()
    parent = RunContext(
        tenant_id=str(uuid4()),
        inputs={"query": "hello"},
        resolve_model=fake_resolve,
        usage_sink=usage_sink,
    )
    child = build_child_context(
        parent,
        {"input": "from-edge"},
        {
            "input_mapping": {"query": "input"},
            "sub_flow_id": str(uuid4()),
        },
        parent_flow_id=parent.current_flow_id,
        parent_node_id="sf1",
        child_flow_id=str(uuid4()),
    )
    assert child.resolve_model is fake_resolve
    assert child.usage_sink is usage_sink


def test_max_subflow_depth_constant():
    assert MAX_SUBFLOW_DEPTH == 3
