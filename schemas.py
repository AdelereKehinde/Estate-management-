from datetime import date, datetime
from pydantic import BaseModel, EmailStr
from typing import Optional


class ORM(BaseModel):
    class Config:
        orm_mode = True


# ---- Auth ----
class RegisterReq(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    role: str = "admin"


class LoginReq(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---- Estates / Properties / Units ----
class EstateIn(BaseModel):
    name: str
    location: str


class EstateOut(ORM):
    id: int
    name: str
    location: str


class PropertyIn(BaseModel):
    code: str
    address: str
    estate_id: int


class PropertyOut(ORM):
    id: int
    code: str
    address: str
    estate_id: int


class UnitIn(BaseModel):
    property_id: int
    label: str
    bedrooms: int = 2


class UnitOut(ORM):
    id: int
    property_id: int
    label: str
    bedrooms: int
    occupied: bool


# ---- Tenants / Leases / Billing ----
class TenantIn(BaseModel):
    full_name: str
    email: EmailStr
    phone: Optional[str] = None


class TenantOut(ORM):
    id: int
    full_name: str
    email: EmailStr
    phone: Optional[str] = None


class LeaseIn(BaseModel):
    unit_id: int
    tenant_id: int
    start_date: date
    end_date: date
    rent_amount: float
    frequency_months: int = 12


class LeaseOut(ORM):
    id: int
    unit_id: int
    tenant_id: int
    start_date: date
    end_date: date
    rent_amount: float
    frequency_months: int
    active: bool


class InvoiceOut(ORM):
    id: int
    lease_id: int
    due_date: date
    amount: float
    status: str
    ref: Optional[str] = None  # <-- FIXED for Python 3.7


class PaymentIn(BaseModel):
    invoice_id: int
    amount: float
    txn_ref: str


class PaymentOut(ORM):
    id: int
    invoice_id: int
    amount: float
    paid_at: datetime
    txn_ref: str


# ---- Maintenance ----
class TicketIn(BaseModel):
    unit_id: int
    title: str
    description: str = ""
    priority: str = "medium"


class TicketOut(ORM):
    id: int
    unit_id: int
    title: str
    description: str
    priority: str
    status: str
