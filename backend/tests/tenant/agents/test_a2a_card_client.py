from app.tenant.a2a.card_client import card_display_name, count_card_skills, resolve_agent_card_url


def test_resolve_from_base_url():
    url = resolve_agent_card_url("https://agent.example.com")
    assert url == "https://agent.example.com/.well-known/agent-card.json"


def test_resolve_full_card_url():
    raw = "https://agent.example.com/.well-known/agent-card.json"
    assert resolve_agent_card_url(raw) == raw


def test_resolve_adds_https():
    url = resolve_agent_card_url("agent.example.com")
    assert url.endswith("/.well-known/agent-card.json")


def test_card_display_name_and_skills():
    card = {"name": "Demo Agent", "skills": [{"id": "a"}, {"id": "b"}]}
    assert card_display_name(card) == "Demo Agent"
    assert count_card_skills(card) == 2
