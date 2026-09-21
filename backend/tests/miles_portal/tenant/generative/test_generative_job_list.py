"""生成任务列表与 meta。"""

from miles_portal.tenant.generative.meta import generative_jobs_meta_dict


def test_generative_jobs_meta_has_filters():
    meta = generative_jobs_meta_dict()
    values = [o.value for o in meta["status_filters"]]
    assert "" in values
    assert "running" in values
    assert "cancelled" in values


def test_generative_jobs_meta_sources():
    meta = generative_jobs_meta_dict()
    sources = {o.value for o in meta["sources"]}
    assert "agent_tool" in sources
    assert "flow_node" in sources
