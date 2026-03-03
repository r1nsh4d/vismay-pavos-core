"""
services/districts.py
All district business logic.
"""
from sqlalchemy.orm import Session
from typing import List
import uuid

from app.models import District
from app.schemas.district import DistrictCreate


# ── Queries ────────────────────────────────────────────────────────────────────

def get_district_by_id(db: Session, district_id: uuid.UUID) -> District | None:
    return db.query(District).filter(District.id == district_id).first()


def get_all_districts(db: Session, state: str | None = None) -> List[District]:
    query = db.query(District)
    if state:
        query = query.filter(District.state.ilike(f"%{state}%"))
    return query.all()


# ── Mutations ──────────────────────────────────────────────────────────────────

def create_district(db: Session, dist_in: DistrictCreate) -> District:
    dist = District(name=dist_in.name, state=dist_in.state)
    db.add(dist)
    db.commit()
    db.refresh(dist)
    return dist


def update_district(db: Session, dist: District, dist_in: DistrictCreate) -> District:
    dist.name = dist_in.name
    dist.state = dist_in.state
    db.commit()
    db.refresh(dist)
    return dist


def delete_district(db: Session, dist: District) -> None:
    db.delete(dist)
    db.commit()