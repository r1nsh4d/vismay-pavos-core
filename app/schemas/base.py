from pydantic import BaseModel, ConfigDict

def camel_case(s: str) -> str:
    # Split by underscore and capitalize all words except the first
    parts = s.split("_")
    return "".join([parts[0]] + [p.capitalize() for p in parts[1:]])


class CamelModel(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        alias_generator=camel_case,
    )