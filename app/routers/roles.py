from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
import uuid

from app.database import get_db
from app.schemas.common import CommonResponse, ErrorResponseModel, ResponseModel
from app.schemas.role import RoleCreate
from app.services import roles as role_mgmt

router = APIRouter(prefix="/roles", tags=["Roles"])


@router.post("", response_model=CommonResponse)
def create_role(role_in: RoleCreate, db: Session = Depends(get_db)):
    if role_mgmt.get_role_by_name(db, role_in.name):
        return ErrorResponseModel(code=400, message="Role name already exists", error={})

    role = role_mgmt.create_role(db, role_in)
    return ResponseModel(data=role_mgmt.serialize_role(role), message="Role created successfully")


@router.get("", response_model=CommonResponse)
def list_roles(db: Session = Depends(get_db)):
    roles = role_mgmt.get_all_roles(db)
    return ResponseModel(data=[role_mgmt.serialize_role(r) for r in roles], message="Roles fetched successfully")


@router.get("/{role_id}", response_model=CommonResponse)
def get_role(role_id: uuid.UUID, db: Session = Depends(get_db)):
    role = role_mgmt.get_role_by_id(db, role_id)
    if not role:
        return ErrorResponseModel(code=404, message="Role not found", error={})
    return ResponseModel(data=role_mgmt.serialize_role(role), message="Role fetched successfully")


@router.put("/{role_id}", response_model=CommonResponse)
def update_role(role_id: uuid.UUID, role_in: RoleCreate, db: Session = Depends(get_db)):
    role = role_mgmt.get_role_by_id(db, role_id)
    if not role:
        return ErrorResponseModel(code=404, message="Role not found", error={})

    role = role_mgmt.update_role(db, role, role_in)
    return ResponseModel(data=role_mgmt.serialize_role(role), message="Role updated successfully")


@router.delete("/{role_id}", response_model=CommonResponse)
def delete_role(role_id: uuid.UUID, db: Session = Depends(get_db)):
    role = role_mgmt.get_role_by_id(db, role_id)
    if not role:
        return ErrorResponseModel(code=404, message="Role not found", error={})

    role_mgmt.delete_role(db, role)
    return ResponseModel(data=None, message="Role deleted successfully")


@router.post("/{role_id}/permissions", response_model=CommonResponse)
def assign_permissions(role_id: uuid.UUID, permission_ids: List[uuid.UUID], db: Session = Depends(get_db)):
    role = role_mgmt.get_role_by_id(db, role_id)
    if not role:
        return ErrorResponseModel(code=404, message="Role not found", error={})

    result = role_mgmt.assign_permissions_to_role(db, role, permission_ids)
    return ResponseModel(data={**result, "role": role_mgmt.serialize_role(role)}, message="Permissions assigned")


@router.delete("/{role_id}/permissions/{permission_id}", response_model=CommonResponse)
def remove_permission(role_id: uuid.UUID, permission_id: uuid.UUID, db: Session = Depends(get_db)):
    removed = role_mgmt.remove_permission_from_role(db, role_id, permission_id)
    if not removed:
        return ErrorResponseModel(code=404, message="Permission assignment not found", error={})
    return ResponseModel(data=None, message="Permission removed from role")