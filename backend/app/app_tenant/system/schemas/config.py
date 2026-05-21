from pydantic import BaseModel, Field


class SystemConfigOut(BaseModel):
    key: str
    value: dict
    description: str | None = None
    is_encrypted: bool = False


class SystemConfigUpsert(BaseModel):
    value: dict
    description: str | None = None


class RuntimeInfoOut(BaseModel):
    components: dict[str, str]
    settings_preview: dict[str, str | int | bool | None]


class ConfigDefinitionOut(BaseModel):
    key: str
    label: str
    category: str
    description: str
    value_type: str = "json"
    default_value: dict | str | int | float | bool | None = None
