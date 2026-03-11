import uuid
from typing import List, Optional, Tuple
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.states import State
from app.schemas.state import StateCreate, StateUpdate


def serialize_state(state: State) -> dict:
    return {
        "id": str(state.id),
        "name": state.name,
        "code": state.code,
        "is_active": state.is_active,
        "created_at": state.created_at.isoformat(),
        "updated_at": state.updated_at.isoformat(),
    }


async def get_state_by_id(db: AsyncSession, state_id: uuid.UUID) -> Optional[State]:
    result = await db.execute(select(State).where(State.id == state_id))
    return result.scalar_one_or_none()


async def search_states(
    db: AsyncSession,
    q: Optional[str] = None,
    is_active: Optional[bool] = None,
    page: int = 1,
    limit: int = 40,
) -> Tuple[List[State], int]:
    query = select(State)

    if q:
        query = query.where(
            State.name.ilike(f"%{q}%") | State.code.ilike(f"%{q}%")
        )
    if is_active is not None:
        query = query.where(State.is_active == is_active)

    query = query.order_by(State.name)

    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar_one()

    result = await db.execute(query.offset((page - 1) * limit).limit(limit))
    states = result.scalars().all()

    return states, total


async def create_state(db: AsyncSession, data: StateCreate) -> State:
    state = State(**data.model_dump())
    db.add(state)
    await db.flush()
    await db.refresh(state)
    return state


async def update_state(db: AsyncSession, state: State, data: StateUpdate) -> State:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(state, field, value)
    await db.flush()
    await db.refresh(state)
    return state


async def delete_state(db: AsyncSession, state: State) -> None:
    await db.delete(state)
    await db.flush()