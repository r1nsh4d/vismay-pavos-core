from pydantic import BaseModel, EmailStr, ConfigDict, field_validator


# ─── Shared ───────────────────────────────────────────────────────────────────

class CamelModel(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        alias_generator=lambda s: "".join(
            w.capitalize() if i else w for i, w in enumerate(s.split("_"))
        ),
    )
