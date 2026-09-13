"""各域 /meta 字典。"""

import pytest

from miles_common.schemas.enum_meta import META_SCHEMA_VERSION
from miles_portal.tenant.a2a.meta import a2a_meta_dict
from miles_portal.tenant.agents.meta import agents_meta_dict
from miles_portal.tenant.attachments.meta import attachments_meta_dict
from miles_portal.tenant.audit_log.meta import audit_meta_dict
from miles_portal.tenant.categories.meta import categories_meta_dict
from miles_portal.tenant.compliance.meta import compliance_meta_dict
from miles_portal.tenant.flows.meta import flow_meta_dict
from miles_portal.tenant.hooks.meta import hook_meta_dict
from miles_portal.tenant.kb.meta import kb_meta_dict
from miles_portal.tenant.marketplace.meta import marketplace_meta_dict
from miles_portal.tenant.mcp.meta import mcp_meta_dict
from miles_portal.tenant.monitor.meta import monitor_meta_dict
from miles_portal.tenant.prompts.meta import prompts_meta_dict
from miles_portal.tenant.skills.meta import skills_meta_dict
from miles_portal.tenant.tags.meta import tags_meta_dict
from miles_portal.tenant.tasks.meta import tasks_meta_dict
from miles_portal.tenant.tools.meta import tools_meta_dict

_ALL_META_DICTS = [
    a2a_meta_dict,
    audit_meta_dict,
    categories_meta_dict,
    agents_meta_dict,
    attachments_meta_dict,
    compliance_meta_dict,
    marketplace_meta_dict,
    mcp_meta_dict,
    monitor_meta_dict,
    skills_meta_dict,
    tags_meta_dict,
    tasks_meta_dict,
    flow_meta_dict,
    hook_meta_dict,
    kb_meta_dict,
    prompts_meta_dict,
    tools_meta_dict,
]


@pytest.mark.parametrize("meta_fn", _ALL_META_DICTS, ids=lambda f: f.__name__)
def test_meta_dict_has_schema_version(meta_fn):
    assert meta_fn()["schema_version"] == META_SCHEMA_VERSION


def test_compliance_meta():
    data = compliance_meta_dict()
    assert {a.value for a in data["sensitive_actions"]} == {"warn", "block"}
    assert {m.value for m in data["scan_modules"]} == {"agent_chat", "flow_run", "generative"}


def test_flow_meta():
    data = flow_meta_dict()
    assert {s.value for s in data["statuses"]} == {"draft", "published"}


def test_kb_meta():
    data = kb_meta_dict()
    assert {m.value for m in data["retrieval_modes"]} == {"vector", "hybrid"}
    assert {t.value for t in data["media_types"]} == {"text", "image", "audio", "video"}
    assert {s.value for s in data["document_statuses"]} == {
        "pending",
        "parsing",
        "embedding",
        "ready",
        "parse_failed",
        "embed_failed",
    }


def test_tools_meta():
    data = tools_meta_dict()
    assert {t.value for t in data["tool_types"]} == {"http", "script"}


def test_hook_meta_still_valid():
    data = hook_meta_dict()
    assert len(data["triggers"]) == 7


def test_agents_meta():
    data = agents_meta_dict()
    assert {s.value for s in data["statuses"]} == {"enabled", "disabled"}
    assert {t.value for t in data["agent_types"]} == {"custom", "a2a"}
    assert any(r.value == "retrieval" for r in data["sub_agent_role_hints"])
    assert len(data["primary_paths"]) >= 8
    assert {m.value for m in data["runtime_modes"]} == {"legacy", "autonomous", "workflow"}
    assert {p.value for p in data["planners"]} == {"deepagents", "platform", "a2a_orchestrator"}


def test_prompts_meta():
    data = prompts_meta_dict()
    assert {s.value for s in data["active_states"]} == {"active", "inactive"}


def test_marketplace_meta():
    data = marketplace_meta_dict()
    assert {s.value for s in data["app_statuses"]} == {
        "draft",
        "pending_review",
        "published",
        "rejected",
        "archived",
    }
    assert {s.value for s in data["catalog_sorts"]} == {"installs", "rating"}


def test_mcp_meta():
    data = mcp_meta_dict()
    assert {s.value for s in data["statuses"]} == {"active", "inactive", "error"}
    assert any(t.value == "sse" for t in data["transport_types"])


def test_attachments_meta():
    data = attachments_meta_dict()
    assert {p.value for p in data["purposes"]} == {
        "general",
        "chat",
        "agent",
        "flow",
        "chat_generated",
        "flow_generated",
    }
    assert data["purpose_filters"][0].value == ""
    assert len(data["purpose_filters"]) == len(data["purposes"]) + 1


def test_skills_meta():
    data = skills_meta_dict()
    assert {s.value for s in data["source_types"]} == {"manual", "local", "zip", "git"}


def test_a2a_meta():
    data = a2a_meta_dict()
    assert {s.value for s in data["peer_statuses"]} == {"pending", "active", "error", "inactive"}
    assert any(p.value == "rules_then_plan" for p in data["invoke_policies"])


def test_monitor_meta():
    data = monitor_meta_dict()
    assert any(c.value == "postgres" for c in data["health_components"])
    values = {c.value for c in data["health_components"]}
    assert values == {"postgres", "redis", "vector_store", "object_storage"}


def test_tasks_meta():
    data = tasks_meta_dict()
    assert {s.value for s in data["statuses"]} == {
        "pending",
        "running",
        "success",
        "failed",
        "cancelled",
    }


def test_categories_meta():
    data = categories_meta_dict()
    assert {d.value for d in data["domains"]} == {"agent", "prompt", "skill", "tool"}


def test_tags_meta():
    data = tags_meta_dict()
    assert {e.value for e in data["entity_types"]} == {
        "agent",
        "prompt",
        "skill",
        "tool",
        "flow",
        "marketplace_app",
    }


def test_audit_meta():
    data = audit_meta_dict()
    assert data["resource_type_filters"][0].value == ""
    assert any(a.value == "agent.create" for a in data["action_filters"])
