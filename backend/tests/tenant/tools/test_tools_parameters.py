import pytest

from app.common.exceptions import BadRequestError
from app.tenant.tools.parameters import normalize_parameters, parameters_to_pydantic, validate_tool_params

SAMPLE = [
    {"name": "city", "type": "string", "description": "城市", "required": True},
    {"name": "unit", "type": "string", "enum": ["c", "f"], "required": False, "default": "c"},
]


def test_validate_ok():
    validate_tool_params(SAMPLE, {"city": "Beijing"})


def test_validate_missing_required():
    with pytest.raises(BadRequestError, match="city"):
        validate_tool_params(SAMPLE, {})


def test_pydantic_model():
    Model = parameters_to_pydantic(SAMPLE)
    m = Model(city="x")
    assert m.city == "x"
    assert m.unit == "c"


def test_duplicate_param_names():
    with pytest.raises(BadRequestError, match="重复"):
        normalize_parameters([{"name": "a", "type": "string"}, {"name": "a", "type": "string"}])
