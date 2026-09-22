"""flow_runtime 画布节点与 LangGraph 评分常量一致性。"""

from miles_ai.flow_runtime.constants import (
    CANVAS_NODE_TYPES,
    CONDITIONAL_NODE_TYPES,
    CanvasNodeType,
)
from miles_ai.flow_runtime.nodes.registry import NODE_REGISTRY
from miles_ai.integrations.langgraph import constants as lg_constants
from miles_ai.integrations.langgraph.constants import GRADE_BRANCH_HANDLES
from miles_portal.tenant.compliance.constants import COMPLIANCE_SCAN_MODULES


def test_node_registry_matches_canvas_node_types():
    assert set(NODE_REGISTRY.keys()) == CANVAS_NODE_TYPES
    assert len(CanvasNodeType) == len(NODE_REGISTRY)


def test_image_generate_node_registered():
    assert CanvasNodeType.IMAGE_GENERATE in NODE_REGISTRY


def test_video_generate_node_registered():
    assert CanvasNodeType.VIDEO_GENERATE in NODE_REGISTRY


def test_conditional_node_types_are_canvas_nodes():
    assert CONDITIONAL_NODE_TYPES <= CANVAS_NODE_TYPES


def test_grade_branch_handles_match_relevance_constants():
    assert GRADE_BRANCH_HANDLES == frozenset(
        {
            lg_constants.RELEVANCE_GOOD,
            lg_constants.RELEVANCE_POOR,
            lg_constants.RELEVANCE_NONE,
        }
    )


def test_compliance_scan_modules_cover_meta_options():
    from miles_portal.tenant.compliance.meta import SCAN_MODULE_OPTIONS

    assert {v for v, _, _ in SCAN_MODULE_OPTIONS} == COMPLIANCE_SCAN_MODULES
