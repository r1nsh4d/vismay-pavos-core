from pydantic import BaseModel
from typing import Optional
import uuid
from datetime import date
from app.models.order import OrderStatus, OrderType


class ReportFilter(BaseModel):
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    tenant_id: Optional[uuid.UUID] = None
    state_id: Optional[uuid.UUID] = None
    district_id: Optional[uuid.UUID] = None
    taluk_id: Optional[uuid.UUID] = None
    shop_id: Optional[uuid.UUID] = None
    distributor_id: Optional[uuid.UUID] = None
    assigned_executive: Optional[uuid.UUID] = None
    status: Optional[OrderStatus] = None
    order_type: Optional[OrderType] = None
    role_id: Optional[uuid.UUID] = None
    is_active: Optional[bool] = None
    category_id: Optional[uuid.UUID] = None
    product_id: Optional[uuid.UUID] = None