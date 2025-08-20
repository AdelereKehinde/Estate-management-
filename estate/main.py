from datetime import date
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from typing import List, Optional
from database import Base, engine, get_db
from models import (
    User, Estate, Property, Unit, Tenant, Lease, Invoice, Payment, MaintenanceTicket
)
from schemas import *
from auth import hash_password, verify_password, create_access_token, require_role

app = FastAPI(title="Amen Estate API (5-file compact)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

# Create tables (simple auto-migrate for demo)
Base.metadata.create_all(bind=engine)

# ---------- AUTH ----------
@app.post("/auth/register", response_model=TokenOut, tags=["Auth"])
def register(body: RegisterReq, db: Session = Depends(get_db)):
    exists = db.scalar(select(func.count()).select_from(User).where(User.email == body.email))
    if exists:
        raise HTTPException(400, "Email already registered")
    u = User(email=body.email, full_name=body.full_name, password_hash=hash_password(body.password), role=body.role)
    db.add(u); db.commit(); db.refresh(u)
    token = create_access_token(str(u.id), u.role)
    return TokenOut(access_token=token)

@app.post("/auth/login", response_model=TokenOut, tags=["Auth"])
def login(body: LoginReq, db: Session = Depends(get_db)):
    u = db.scalar(select(User).where(User.email == body.email))
    if not u or not verify_password(body.password, u.password_hash):
        raise HTTPException(401, "Invalid credentials")
    return TokenOut(access_token=create_access_token(str(u.id), u.role))

# ---------- ESTATE / PROPERTY / UNIT ----------
@app.post("/estates", response_model=EstateOut, tags=["Estates"])
def create_estate(body: EstateIn, db: Session = Depends(get_db), _=Depends(require_role("admin","manager"))):
    e = Estate(name=body.name, location=body.location)
    db.add(e); db.commit(); db.refresh(e)
    return e

@app.get("/estates", response_model=List[EstateOut], tags=["Estates"])
def list_estates(db: Session = Depends(get_db), _=Depends(require_role("admin","manager","accountant","facility","security"))):
    return list(db.scalars(select(Estate)).all())

@app.post("/properties", response_model=PropertyOut, tags=["Properties"])
def create_property(body: PropertyIn, db: Session = Depends(get_db), _=Depends(require_role("admin","manager"))):
    p = Property(code=body.code, address=body.address, estate_id=body.estate_id)
    db.add(p); db.commit(); db.refresh(p)
    return p

@app.get("/properties", response_model=List[PropertyOut], tags=["Properties"])
def list_properties(estate_id: Optional[int] = None, db: Session = Depends(get_db),
                    _=Depends(require_role("admin","manager","accountant","facility","security"))):
    stmt = select(Property)
    if estate_id: stmt = stmt.where(Property.estate_id == estate_id)
    return list(db.scalars(stmt).all())

@app.post("/units", response_model=UnitOut, tags=["Units"])
def create_unit(body: UnitIn, db: Session = Depends(get_db), _=Depends(require_role("admin","manager"))):
    u = Unit(property_id=body.property_id, label=body.label, bedrooms=body.bedrooms)
    db.add(u); db.commit(); db.refresh(u)
    return u

@app.get("/units", response_model=List[UnitOut], tags=["Units"])
def list_units(property_id: Optional[int] = None, occupied: Optional[bool] = None,
               limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
               db: Session = Depends(get_db),
               _=Depends(require_role("admin","manager","accountant","facility","security"))):
    stmt = select(Unit)
    if property_id is not None: stmt = stmt.where(Unit.property_id == property_id)
    if occupied is not None: stmt = stmt.where(Unit.occupied == occupied)
    stmt = stmt.offset(offset).limit(limit)
    return list(db.scalars(stmt).all())

# ---------- TENANTS ----------
@app.post("/tenants", response_model=TenantOut, tags=["Tenants"])
def create_tenant(body: TenantIn, db: Session = Depends(get_db), _=Depends(require_role("admin","manager"))):
    if db.scalar(select(func.count()).select_from(Tenant).where(Tenant.email == body.email)):
        raise HTTPException(400, "Tenant email already exists")
    t = Tenant(**body.dict())
    db.add(t); db.commit(); db.refresh(t)
    return t

@app.get("/tenants", response_model=List[TenantOut], tags=["Tenants"])
def list_tenants(q: Optional[str] = None, db: Session = Depends(get_db),
                 _=Depends(require_role("admin","manager","accountant","facility","security"))):
    stmt = select(Tenant)
    if q:
        stmt = stmt.where((Tenant.full_name.ilike(f"%{q}%")) | (Tenant.email.ilike(f"%{q}%")))
    return list(db.scalars(stmt).all())

# ---------- LEASES / INVOICES / PAYMENTS ----------
def _add_months(d: date, months: int) -> date:
    m = d.month - 1 + months
    y = d.year + m // 12
    m = m % 12 + 1
    # handle end-of-month safely
    days = [31, 29 if (y%4==0 and (y%100!=0 or y%400==0)) else 28,31,30,31,30,31,31,30,31,30,31][m-1]
    day = min(d.day, days)
    return date(y, m, day)

@app.post("/leases", response_model=LeaseOut, tags=["Leases"])
def create_lease(body: LeaseIn, db: Session = Depends(get_db), _=Depends(require_role("admin","manager"))):
    unit = db.get(Unit, body.unit_id)
    if not unit: raise HTTPException(404, "Unit not found")
    if unit.occupied: raise HTTPException(400, "Unit already occupied")
    lease = Lease(**body.dict())
    unit.occupied = True
    db.add(lease); db.commit(); db.refresh(lease)
    return lease

@app.post("/leases/{lease_id}/generate-invoices", tags=["Leases"])
def generate_invoices(lease_id: int, db: Session = Depends(get_db), _=Depends(require_role("admin","manager","accountant"))):
    lease = db.get(Lease, lease_id)
    if not lease: raise HTTPException(404, "Lease not found")
    created = 0
    i = 0
    due = lease.start_date
    while due <= lease.end_date:
        inv = Invoice(lease_id=lease.id, due_date=due, amount=lease.rent_amount, status="pending")
        db.add(inv); created += 1
        i += lease.frequency_months
        due = _add_months(lease.start_date, i)
    db.commit()
    return {"created": created}

@app.get("/invoices", response_model=List[InvoiceOut], tags=["Invoices"])
def list_invoices(status: Optional[str] = None, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                  _=Depends(require_role("admin","manager","accountant"))):
    stmt = select(Invoice).join(Lease)
    if status: stmt = stmt.where(Invoice.status == status)
    if tenant_id: stmt = stmt.where(Lease.tenant_id == tenant_id)
    return list(db.scalars(stmt).all())

@app.post("/payments", response_model=PaymentOut, tags=["Payments"])
def record_payment(body: PaymentIn, db: Session = Depends(get_db), _=Depends(require_role("admin","manager","accountant"))):
    inv = db.get(Invoice, body.invoice_id)
    if not inv: raise HTTPException(404, "Invoice not found")
    if body.amount < inv.amount:
        raise HTTPException(400, "Amount less than invoice")
    pay = Payment(invoice_id=inv.id, amount=body.amount, txn_ref=body.txn_ref)
    inv.status = "paid"
    db.add(pay); db.commit(); db.refresh(pay)
    return pay

# ---------- MAINTENANCE ----------
@app.post("/maintenance/tickets", response_model=TicketOut, tags=["Maintenance"])
def create_ticket(body: TicketIn, db: Session = Depends(get_db),
                  _=Depends(require_role("admin","manager","facility","resident"))):
    if not db.get(Unit, body.unit_id): raise HTTPException(404, "Unit not found")
    t = MaintenanceTicket(**body.dict())
    db.add(t); db.commit(); db.refresh(t)
    return t

@app.patch("/maintenance/tickets/{ticket_id}", response_model=TicketOut, tags=["Maintenance"])
def update_ticket(ticket_id: int, status: Optional[str] = None, priority: Optional[str] = None,
                  db: Session = Depends(get_db), _=Depends(require_role("admin","manager","facility"))):
    t = db.get(MaintenanceTicket, ticket_id)
    if not t: raise HTTPException(404, "Ticket not found")
    if status: t.status = status
    if priority: t.priority = priority
    db.commit(); db.refresh(t)
    return t

@app.get("/", tags=["Health"])
def health():
    return {"name": "Amen Estate", "status": "ok"}


import uvicorn
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0", port=8000, log_level="info")

