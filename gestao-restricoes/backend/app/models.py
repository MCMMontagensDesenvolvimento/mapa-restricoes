import uuid
from datetime import date, datetime, timezone
from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

def now(): return datetime.now(timezone.utc)
class Base(DeclarativeBase): pass

class Restriction(Base):
    __tablename__ = "restrictions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda:str(uuid.uuid4()))
    external_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    logical_hash: Mapped[str|None] = mapped_column(String(64), index=True)
    area: Mapped[str|None] = mapped_column(String(180)); cwp: Mapped[str|None] = mapped_column(String(120))
    discipline: Mapped[str|None] = mapped_column(String(120)); task: Mapped[str|None] = mapped_column(Text)
    restriction: Mapped[str] = mapped_column(Text); category: Mapped[str|None] = mapped_column(String(180))
    action: Mapped[str|None] = mapped_column(Text); owner: Mapped[str|None] = mapped_column(String(180))
    company: Mapped[str|None] = mapped_column(String(180)); raised_at: Mapped[date|None] = mapped_column(Date)
    due_at: Mapped[date|None] = mapped_column(Date); status: Mapped[str] = mapped_column(String(40), default="Aberta")
    completed_at: Mapped[datetime|None] = mapped_column(DateTime(timezone=True))
    priority: Mapped[str] = mapped_column(String(30), default="Média"); impact: Mapped[str|None] = mapped_column(Text)
    source_etag: Mapped[str|None] = mapped_column(String(255)); row_version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    updated_by: Mapped[str|None] = mapped_column(String(255)); update_origin: Mapped[str] = mapped_column(String(30), default="system")
    __table_args__=(Index("idx_restrictions_status_due", "status", "due_at"),Index("idx_restrictions_owner", "owner"),)

class AuditEvent(Base):
    __tablename__="audit_events"
    id: Mapped[int]=mapped_column(primary_key=True,autoincrement=True)
    restriction_id: Mapped[str|None]=mapped_column(ForeignKey("restrictions.id",ondelete="SET NULL"),index=True)
    restriction_external_id: Mapped[str|None]=mapped_column(String(80),index=True)
    event: Mapped[str]=mapped_column(String(80)); field: Mapped[str|None]=mapped_column(String(80))
    old_value: Mapped[str|None]=mapped_column(Text); new_value: Mapped[str|None]=mapped_column(Text)
    actor_name: Mapped[str|None]=mapped_column(String(255)); actor_email: Mapped[str]=mapped_column(String(255))
    origin: Mapped[str]=mapped_column(String(30),default="web"); created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    excel_result: Mapped[str]=mapped_column(String(30),default="pending")

class AccessLog(Base):
    __tablename__="access_logs"
    id: Mapped[int]=mapped_column(primary_key=True,autoincrement=True); user_name: Mapped[str|None]=mapped_column(String(255))
    user_email: Mapped[str]=mapped_column(String(255),index=True); accessed_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class SyncRun(Base):
    __tablename__="sync_runs"
    id: Mapped[int]=mapped_column(primary_key=True,autoincrement=True); provider: Mapped[str]=mapped_column(String(30))
    status: Mapped[str]=mapped_column(String(30)); item_etag: Mapped[str|None]=mapped_column(String(255)); summary: Mapped[str|None]=mapped_column(Text)
    started_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now); finished_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    actor_email: Mapped[str]=mapped_column(String(255))

class SyncConflict(Base):
    __tablename__="sync_conflicts"
    id: Mapped[int]=mapped_column(primary_key=True,autoincrement=True); restriction_id: Mapped[str]=mapped_column(String(36),index=True)
    field: Mapped[str]=mapped_column(String(80)); database_value: Mapped[str|None]=mapped_column(Text); external_value: Mapped[str|None]=mapped_column(Text)
    status: Mapped[str]=mapped_column(String(30),default="pending"); created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class SyncQueue(Base):
    __tablename__="sync_queue"
    id: Mapped[int]=mapped_column(primary_key=True,autoincrement=True)
    restriction_id: Mapped[str]=mapped_column(String(36),index=True)
    operation: Mapped[str]=mapped_column(String(20),default="upsert")
    payload: Mapped[str]=mapped_column(Text)
    status: Mapped[str]=mapped_column(String(30),default="pending",index=True)
    attempts: Mapped[int]=mapped_column(Integer,default=0)
    last_error: Mapped[str|None]=mapped_column(Text)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    synced_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    actor_email: Mapped[str]=mapped_column(String(255))

class IdMapping(Base):
    __tablename__="id_mappings"
    id: Mapped[int]=mapped_column(primary_key=True,autoincrement=True)
    old_internal_id: Mapped[str]=mapped_column(String(36),index=True)
    old_external_id: Mapped[str|None]=mapped_column(String(80))
    new_internal_id: Mapped[str]=mapped_column(String(36),index=True)
    new_external_id: Mapped[str]=mapped_column(String(80),index=True)
    confidence: Mapped[str]=mapped_column(String(30),default="high")
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class ReportEmission(Base):
    __tablename__="report_emissions"
    id: Mapped[int]=mapped_column(primary_key=True,autoincrement=True)
    report_type: Mapped[str]=mapped_column(String(50),index=True)
    responsible: Mapped[str|None]=mapped_column(String(180),index=True)
    actor_name: Mapped[str|None]=mapped_column(String(255))
    actor_email: Mapped[str]=mapped_column(String(255),index=True)
    reference_date: Mapped[date]=mapped_column(Date,index=True)
    filters_json: Mapped[str]=mapped_column(Text)
    record_count: Mapped[int]=mapped_column(Integer)
    filename: Mapped[str]=mapped_column(String(255))
    snapshot_json: Mapped[str]=mapped_column(Text)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,index=True)
