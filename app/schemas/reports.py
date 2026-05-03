import uuid
from typing import Optional
from datetime import date
from pydantic import BaseModel
from app.models.order import OrderStatus, OrderType


class ConsolidationReportFilter(BaseModel):
    tenant_id: Optional[uuid.UUID] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None


class ExecutiveWiseReportFilter(BaseModel):
    tenant_id: Optional[uuid.UUID] = None
    year: Optional[int] = None
    month: Optional[int] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None