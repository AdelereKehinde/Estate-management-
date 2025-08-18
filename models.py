from datetime import date, datetime
from sqlalchemy import (
    Column, Integer, String, Date, DateTime, ForeignKey, Float, Boolean, UniqueConstraint
)
from sqlalchemy.orm import relationship, Mapped
from database import Base

# ---- Auth / Users ----
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    email: Mapped[str] = Column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = Column(String(255), nullable=False)
    password_hash: Mapped[str] = Column(String(255), nullable=False)
    role: Mapped[str] = Column(String(50), default="manager")  # admin, manager, accountant, facility, security, resident

# ---- Estate Structure ----
class Estate(Base):
    __tablename__ = "estates"
    id: Mapped[int] = Column(Integer, primary_key=True)
    name: Mapped[str] = Column(String(200), unique=True, index=True, nullable=False)
    location: Mapped[str] = Column(String(255), nullable=False)
    properties = relationship("Property", back_populates="estate", cascade="all,delete")

class Property(Base):
    __tablename__ = "properties"
    id: Mapped[int] = Column(Integer, primary_key=True)
    code: Mapped[str] = Column(String(50), unique=True, index=True, nullable=False)  # e.g. PH1-BLK3
    address: Mapped[str] = Column(String(255), nullable=False)
    estate_id: Mapped[int] = Column(Integer, ForeignKey("estates.id", ondelete="CASCADE"), nullable=False)
    estate = relationship("Estate", back_populates="properties")
    units = relationship("Unit", back_populates="property", cascade="all,delete")

class Unit(Base):
    __tablename__ = "units"
    id: Mapped[int] = Column(Integer, primary_key=True)
    property_id: Mapped[int] = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False)
    label: Mapped[str] = Column(String(50), nullable=False)  # e.g. Flat A
    bedrooms: Mapped[int] = Column(Integer, default=2)
    occupied: Mapped[bool] = Column(Boolean, default=False)
    property = relationship("Property", back_populates="units")
    leases = relationship("Lease", back_populates="unit")
    __table_args__ = (UniqueConstraint("property_id", "label", name="uq_unit_per_property"),)

# ---- Tenants / Leases / Billing ----
class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[int] = Column(Integer, primary_key=True)
    full_name: Mapped[str] = Column(String(255), nullable=False)
    email: Mapped[str] = Column(String(255), unique=True, index=True, nullable=False)
    phone: Mapped[str] = Column(String(30), nullable=True)
    leases = relationship("Lease", back_populates="tenant")

class Lease(Base):
    __tablename__ = "leases"
    id: Mapped[int] = Column(Integer, primary_key=True)
    unit_id: Mapped[int] = Column(Integer, ForeignKey("units.id"), nullable=False)
    tenant_id: Mapped[int] = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    start_date: Mapped[date] = Column(Date, nullable=False)
    end_date: Mapped[date] = Column(Date, nullable=False)
    rent_amount: Mapped[float] = Column(Float, nullable=False)  # per period
    frequency_months: Mapped[int] = Column(Integer, default=12)  # 1=monthly, 3=quarterly, 12=yearly
    active: Mapped[bool] = Column(Boolean, default=True)

    unit = relationship("Unit", back_populates="leases")
    tenant = relationship("Tenant", back_populates="leases")
    invoices = relationship("Invoice", back_populates="lease", cascade="all,delete")

class Invoice(Base):
    __tablename__ = "invoices"
    id: Mapped[int] = Column(Integer, primary_key=True)
    lease_id: Mapped[int] = Column(Integer, ForeignKey("leases.id"), nullable=False)
    due_date: Mapped[date] = Column(Date, nullable=False)
    amount: Mapped[float] = Column(Float, nullable=False)
    status: Mapped[str] = Column(String(20), default="pending")  # pending, paid, overdue
    ref: Mapped[str] = Column(String(64), unique=True, nullable=True)

    lease = relationship("Lease", back_populates="invoices")
    payments = relationship("Payment", back_populates="invoice", cascade="all,delete")

class Payment(Base):
    __tablename__ = "payments"
    id: Mapped[int] = Column(Integer, primary_key=True)
    invoice_id: Mapped[int] = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    amount: Mapped[float] = Column(Float, nullable=False)
    paid_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    txn_ref: Mapped[str] = Column(String(64), unique=True, nullable=False)
    invoice = relationship("Invoice", back_populates="payments")

# ---- Maintenance ----
class MaintenanceTicket(Base):
    __tablename__ = "maintenance_tickets"
    id: Mapped[int] = Column(Integer, primary_key=True)
    unit_id: Mapped[int] = Column(Integer, ForeignKey("units.id"), nullable=False)
    title: Mapped[str] = Column(String(200), nullable=False)
    description: Mapped[str] = Column(String(1000), default="")
    priority: Mapped[str] = Column(String(20), default="medium")  # low, medium, high
    status: Mapped[str] = Column(String(20), default="open")      # open, assigned, closed
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)