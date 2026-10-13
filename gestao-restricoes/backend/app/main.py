import asyncio
import contextlib
import json
import logging
import io,zipfile,unicodedata
from datetime import date,datetime,timezone
from pathlib import Path
from fastapi import Depends,FastAPI,HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel,ConfigDict
from sqlalchemy import delete,func,select,text
from sqlalchemy.ext.asyncio import AsyncSession
from .auth import User,current_user,require
from .config import get_settings
from .db import SessionLocal,engine,session
from .models import AccessLog,AuditEvent,Base,IdMapping,ReportEmission,Restriction,SyncConflict,SyncQueue,SyncRun
from .report_service import criticality,pdf_bytes,safe_name,snapshot
from .excel_report_service import xlsx_bytes
from .sync_service import delete_excel_restriction,resync_authoritative_excel,retry_pending,save_restriction,synchronize_local

s=get_settings();app=FastAPI(title="Lean Control API",version="1.1.0",docs_url="/api/docs" if s.app_env!="production" else None)
app.add_middleware(CORSMiddleware,allow_origins=[s.app_origin,"http://localhost:3000","http://localhost:3001","http://127.0.0.1:3000","http://127.0.0.1:3001"],allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
SETTINGS=Path(__file__).resolve().parents[1]/"config"/"settings.json"

async def retry_worker():
 while True:
  await asyncio.sleep(max(10,s.sync_retry_seconds))
  try:
   async with SessionLocal() as db:await retry_pending(db)
  except Exception:logging.exception("Falha ao tentar novamente a fila de sincronização")

class Body(BaseModel):
 model_config=ConfigDict(extra="ignore");area:str|None=None;cwp:str|None=None;discipline:str|None=None;task:str|None=None;restriction:str;category:str|None=None;action:str|None=None;owner:str|None=None;company:str|None=None;raisedAt:str|None=None;dueAt:str|None=None;status:str="Aberta";priority:str="Média";impact:str|None=None;rowVersion:int|None=None
class SettingsBody(BaseModel):model_config=ConfigDict(extra="allow")
class RebuildBody(BaseModel):confirm:str
class ReportBody(BaseModel):
 owners:list[str]=[];company:str|None=None;area:str|None=None;cwp:str|None=None;discipline:str|None=None;category:str|None=None;status:str|None=None;priority:str|None=None;criticality:str|None=None;quick:str="Todas as Pendências";referenceDate:str;includeImpact:bool=False;general:bool=False;responseMode:bool=False
def dt(v):return date.fromisoformat(v) if v else None
def out(r):return{"id":r.external_id or r.id,"area":r.area,"cwp":r.cwp,"discipline":r.discipline,"task":r.task,"restriction":r.restriction,"category":r.category,"action":r.action,"owner":r.owner,"company":r.company,"raisedAt":r.raised_at.isoformat() if r.raised_at else None,"dueAt":r.due_at.isoformat() if r.due_at else None,"status":r.status,"completedAt":r.completed_at.isoformat() if r.completed_at else None,"priority":r.priority,"impact":r.impact,"rowVersion":r.row_version}
async def find_restriction(db,rid):return await db.scalar(select(Restriction).where(Restriction.external_id==rid))
def owner_key(value):return unicodedata.normalize('NFKD',value or '').encode('ascii','ignore').decode().casefold().strip()
def report_rows(all_rows,body,ref,owner=None):
 rows=[]
 for r in all_rows:
  if (owner and owner_key(r.owner)!=owner_key(owner)) or (body.owners and not owner and owner_key(r.owner) not in {owner_key(x) for x in body.owners}):continue
  if any(value and value!='Todos' and getattr(r,key)!=value for key,value in [('company',body.company),('area',body.area),('cwp',body.cwp),('discipline',body.discipline),('category',body.category),('status',body.status),('priority',body.priority)]):continue
  c=criticality(r,ref);d=(r.due_at-ref).days if r.due_at else 99999
  if body.criticality and body.criticality!='Todos' and c!=body.criticality:continue
  if body.quick=='Todas as Pendências' and r.status in ('Concluída','Cancelada'):continue
  if body.quick=='Somente Vencidas' and not(d<0 and r.status not in ('Concluída','Cancelada')):continue
  if body.quick=='Críticas' and c!='Crítica':continue
  if body.quick=='Alta Prioridade' and r.priority!='Alta':continue
  if body.quick=='Vencidas + Próximos 7 dias' and not(d<=7 and r.status not in ('Concluída','Cancelada')):continue
  if body.quick=='Próximos 3 dias' and not(d<=3 and r.status not in ('Concluída','Cancelada')):continue
  if body.quick=='Em Tratamento' and r.status!='Em Tratamento':continue
  rows.append(r)
 return rows

@app.on_event("startup")
async def startup():
 async with engine.begin() as c:
  await c.run_sync(Base.metadata.create_all)
  if s.database_url.startswith("sqlite"):
   columns=(await c.execute(text("PRAGMA table_info(audit_events)"))).all()
   if "excel_result" not in {row[1] for row in columns}:await c.execute(text("ALTER TABLE audit_events ADD COLUMN excel_result VARCHAR(30) NOT NULL DEFAULT 'pending'"))
   restriction_columns=(await c.execute(text("PRAGMA table_info(restrictions)"))).all();names={row[1] for row in restriction_columns}
   if "external_id" not in names:await c.execute(text("ALTER TABLE restrictions ADD COLUMN external_id VARCHAR(80)"));await c.execute(text("UPDATE restrictions SET external_id=id WHERE external_id IS NULL"))
   if "logical_hash" not in names:await c.execute(text("ALTER TABLE restrictions ADD COLUMN logical_hash VARCHAR(64)"))
   if "completed_at" not in names:await c.execute(text("ALTER TABLE restrictions ADD COLUMN completed_at DATETIME"))
   audit_names={row[1] for row in columns}
   if "restriction_external_id" not in audit_names:await c.execute(text("ALTER TABLE audit_events ADD COLUMN restriction_external_id VARCHAR(80)"))
   await c.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_restrictions_external_id ON restrictions(external_id)"));await c.execute(text("CREATE INDEX IF NOT EXISTS ix_restrictions_logical_hash ON restrictions(logical_hash)"))
 app.state.retry_task=asyncio.create_task(retry_worker())

@app.on_event("shutdown")
async def shutdown():
 task=getattr(app.state,"retry_task",None)
 if task:
  task.cancel()
  with contextlib.suppress(asyncio.CancelledError):await task
@app.get("/api/health")
async def health():return{"status":"ok","time":datetime.now(timezone.utc).isoformat()}
@app.get("/api/me")
async def me(user:User=Depends(current_user),db:AsyncSession=Depends(session)):
 db.add(AccessLog(user_name=user.name,user_email=user.email));await db.commit();return user.__dict__
@app.get("/api/restrictions")
async def restrictions(user:User=Depends(current_user),db:AsyncSession=Depends(session)):return[out(r) for r in(await db.scalars(select(Restriction).order_by(Restriction.due_at))).all()]
@app.get("/api/restrictions/{rid}")
async def restriction(rid:str,user:User=Depends(current_user),db:AsyncSession=Depends(session)):
 r=await find_restriction(db,rid)
 if not r:raise HTTPException(404,"Restrição não encontrada")
 return out(r)
@app.post("/api/restrictions",status_code=201)
async def create(body:Body,user:User=Depends(require("Administrador","Editor")),db:AsyncSession=Depends(session)):
 data=body.model_dump(exclude={"raisedAt","dueAt","rowVersion"});data.update(raised_at=dt(body.raisedAt),due_at=dt(body.dueAt));r,status,result=await save_restriction(db,data,user);return {**out(r),"excelSync":status,"syncMessage":"Restrição salva e sincronizada com Excel." if status=="synced" else "Alteração salva no Lean Control. O Excel está temporariamente indisponível e será sincronizado assim que possível."}
@app.put("/api/restrictions/{rid}")
async def update(rid:str,body:Body,user:User=Depends(require("Administrador","Editor")),db:AsyncSession=Depends(session)):
 r=await find_restriction(db,rid)
 if not r:raise HTTPException(404,"Restrição não encontrada")
 if body.rowVersion and body.rowVersion!=r.row_version:raise HTTPException(409,{"message":"Conflito de atualização encontrado","database":out(r)})
 data=body.model_dump(exclude={"raisedAt","dueAt"});data.update(raised_at=dt(body.raisedAt),due_at=dt(body.dueAt));r,status,result=await save_restriction(db,data,user,r);return {**out(r),"excelSync":status,"syncMessage":"Restrição salva e sincronizada com Excel." if status=="synced" else "Alteração salva no Lean Control. O Excel está temporariamente indisponível e será sincronizado assim que possível."}
@app.delete("/api/restrictions/{rid}",status_code=204)
async def remove(rid:str,user:User=Depends(require("Administrador")),db:AsyncSession=Depends(session)):
 r=await find_restriction(db,rid)
 if not r:raise HTTPException(404,"Restrição não encontrada")
 try:result=await asyncio.to_thread(delete_excel_restriction,r.external_id)
 except (FileNotFoundError,ValueError,IOError) as exc:raise HTTPException(409,str(exc))
 db.add(AuditEvent(restriction_id=None,restriction_external_id=r.external_id,event="deleted",field="restriction",old_value=r.restriction,new_value="Excluída definitivamente",actor_name=user.name,actor_email=user.email,origin="system",excel_result="synced"))
 await db.execute(delete(SyncQueue).where(SyncQueue.restriction_id==r.id));await db.delete(r)
 try:await db.commit()
 except Exception:
  await db.rollback()
  Path(result["path"]).write_bytes(Path(result["backup"]).read_bytes())
  raise HTTPException(500,"A exclusão no banco falhou e o Excel foi restaurado a partir do backup.")

@app.post("/api/restrictions/{rid}/complete")
async def complete(rid:str,user:User=Depends(require("Administrador","Editor")),db:AsyncSession=Depends(session)):
 r=await find_restriction(db,rid)
 if not r:raise HTTPException(404,"Restrição não encontrada")
 data={field:getattr(r,field) for field in ("area","cwp","discipline","task","restriction","category","action","owner","company","raised_at","due_at","priority","impact")};data["status"]="Concluída"
 r,status,_=await save_restriction(db,data,user,r);return {**out(r),"excelSync":status,"syncMessage":"Restrição concluída e atualizada no Excel." if status=="synced" else "Restrição concluída no Lean Control. A atualização do Excel está pendente."}

@app.post("/api/restrictions/{rid}/reopen")
async def reopen(rid:str,user:User=Depends(require("Administrador","Editor")),db:AsyncSession=Depends(session)):
 r=await find_restriction(db,rid)
 if not r:raise HTTPException(404,"Restrição não encontrada")
 data={field:getattr(r,field) for field in ("area","cwp","discipline","task","restriction","category","action","owner","company","raised_at","due_at","priority","impact")};data["status"]="Aberta"
 r,status,_=await save_restriction(db,data,user,r);return {**out(r),"excelSync":status,"syncMessage":"Restrição reaberta e atualizada no Excel." if status=="synced" else "Restrição reaberta no Lean Control. A atualização do Excel está pendente."}
@app.post("/api/sync/excel")
@app.post("/api/sync")
async def sync_excel(user:User=Depends(require("Administrador")),db:AsyncSession=Depends(session)):
 try:return await synchronize_local(db,user.email) if s.app_env=="development" or s.sync_provider=="excel-local" else {"status":"configuration_required","message":"Configure o provedor SharePoint antes da sincronização corporativa."}
 except FileNotFoundError as exc:raise HTTPException(404,str(exc))
 except Exception as exc:
  logging.exception("Falha na sincronização do Excel")
  raise HTTPException(500,"Não foi possível sincronizar o Excel. Consulte o log técnico.") from exc
@app.get("/api/history")
async def history(user:User=Depends(current_user),db:AsyncSession=Depends(session)):
 rows=(await db.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(1000))).all();current={r.id:r.external_id for r in(await db.scalars(select(Restriction))).all()};mapped={m.old_internal_id:m.new_external_id for m in(await db.scalars(select(IdMapping).order_by(IdMapping.created_at))).all()};events=[{"id":f"audit-{x.id}","date":x.created_at.isoformat(),"user":x.actor_name or x.actor_email,"email":x.actor_email,"restrictionId":x.restriction_external_id or current.get(x.restriction_id) or mapped.get(x.restriction_id) or x.restriction_id,"event":x.event,"field":x.field,"oldValue":x.old_value,"newValue":x.new_value,"origin":x.origin,"excelResult":x.excel_result}for x in rows]
 reports=(await db.scalars(select(ReportEmission).order_by(ReportEmission.created_at.desc()).limit(500))).all();events += [{"id":f"report-{x.id}","date":x.created_at.isoformat(),"user":x.actor_name or x.actor_email,"email":x.actor_email,"restrictionId":None,"event":"report_generated","field":"Relatório","oldValue":None,"newValue":f"{x.filename} - {x.record_count} registros - referência {x.reference_date.strftime('%d/%m/%Y')}","origin":"report","excelResult":"not_applicable"} for x in reports];return sorted(events,key=lambda x:x["date"],reverse=True)[:1000]

@app.post("/api/reports/pdf")
async def report_pdf(body:ReportBody,user:User=Depends(require("Administrador","Editor")),db:AsyncSession=Depends(session)):
 ref=date.fromisoformat(body.referenceDate);all_rows=(await db.scalars(select(Restriction))).all();rows=report_rows(all_rows,body,ref);owner=', '.join(body.owners) if body.owners else None
 config=json.loads(SETTINGS.read_text(encoding='utf-8'));filename=('Relatorio_Geral_' if body.general else f'Restricoes_{safe_name(owner)}_')+ref.isoformat()+'.pdf';snaps=[snapshot(r,ref) for r in rows]
 db.add(ReportEmission(report_type='general' if body.general else 'responsible',responsible=owner,actor_name=user.name,actor_email=user.email,reference_date=ref,filters_json=body.model_dump_json(),record_count=len(rows),filename=filename,snapshot_json=json.dumps(snaps,ensure_ascii=False)));await db.commit()
 data=pdf_bytes(rows,ref,config.get('projectName','NEXA-MT'),owner,body.includeImpact,body.general)
 return StreamingResponse(io.BytesIO(data),media_type='application/pdf',headers={'Content-Disposition':f'attachment; filename="{filename}"','X-Report-Count':str(len(rows))})

@app.post("/api/reports/batch")
async def report_batch(body:ReportBody,user:User=Depends(require("Administrador","Editor")),db:AsyncSession=Depends(session)):
 ref=date.fromisoformat(body.referenceDate);all_rows=(await db.scalars(select(Restriction))).all();owner_map={}
 for r in all_rows:
  if r.owner and r.status not in ('Concluída','Cancelada'):
   key=owner_key(r.owner);current=owner_map.get(key);owner_map[key]=r.owner if not current or (r.owner[:1].isupper() and not r.owner.isupper()) else current
 owners=sorted(owner_map.values(),key=str.casefold);config=json.loads(SETTINGS.read_text(encoding='utf-8'));buf=io.BytesIO()
 with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as archive:
  for owner in owners:
   rows=report_rows(all_rows,body,ref,owner);filename=f'Relatorios/{ref.isoformat()}/Restricoes_{safe_name(owner)}.pdf';snaps=[snapshot(r,ref) for r in rows]
   archive.writestr(filename,pdf_bytes(rows,ref,config.get('projectName','NEXA-MT'),owner,body.includeImpact));db.add(ReportEmission(report_type='responsible_batch',responsible=owner,actor_name=user.name,actor_email=user.email,reference_date=ref,filters_json=body.model_dump_json(),record_count=len(rows),filename=filename,snapshot_json=json.dumps(snaps,ensure_ascii=False)))
 await db.commit();buf.seek(0);return StreamingResponse(buf,media_type='application/zip',headers={'Content-Disposition':f'attachment; filename="Relatorios_{ref.isoformat()}.zip"','X-Report-Owners':str(len(owners))})

@app.post('/api/reports/excel')
async def report_excel(body:ReportBody,user:User=Depends(require('Administrador','Editor')),db:AsyncSession=Depends(session)):
 ref=date.fromisoformat(body.referenceDate);all_rows=(await db.scalars(select(Restriction))).all();rows=report_rows(all_rows,body,ref);owner=', '.join(body.owners) if body.owners else None
 config=json.loads(SETTINGS.read_text(encoding='utf-8'));filename=('Relatorio_Geral_' if body.general else f'Restricoes_{safe_name(owner)}_')+ref.isoformat()+'.xlsx';snaps=[snapshot(r,ref) for r in rows]
 db.add(ReportEmission(report_type='excel_general' if body.general else 'excel_responsible',responsible=owner,actor_name=user.name,actor_email=user.email,reference_date=ref,filters_json=body.model_dump_json(),record_count=len(rows),filename=filename,snapshot_json=json.dumps(snaps,ensure_ascii=False)));await db.commit()
 data=xlsx_bytes(rows,ref,config.get('projectName','NEXA-MT'),owner,body.responseMode,body.general)
 return StreamingResponse(io.BytesIO(data),media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers={'Content-Disposition':f'attachment; filename="{filename}"','X-Report-Count':str(len(rows))})

@app.post('/api/reports/excel/batch')
async def report_excel_batch(body:ReportBody,user:User=Depends(require('Administrador','Editor')),db:AsyncSession=Depends(session)):
 ref=date.fromisoformat(body.referenceDate);all_rows=(await db.scalars(select(Restriction))).all();owner_map={}
 for r in all_rows:
  if r.owner and r.status not in ('Concluída','Cancelada'):
   key=owner_key(r.owner);current=owner_map.get(key);owner_map[key]=r.owner if not current or (r.owner[:1].isupper() and not r.owner.isupper()) else current
 owners=sorted(owner_map.values(),key=str.casefold);config=json.loads(SETTINGS.read_text(encoding='utf-8'));buf=io.BytesIO()
 with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as archive:
  for owner in owners:
   rows=report_rows(all_rows,body,ref,owner);filename=f'Relatorios/{ref.isoformat()}/Restricoes_{safe_name(owner)}.xlsx';snaps=[snapshot(r,ref) for r in rows]
   archive.writestr(filename,xlsx_bytes(rows,ref,config.get('projectName','NEXA-MT'),owner,body.responseMode));db.add(ReportEmission(report_type='excel_responsible_batch',responsible=owner,actor_name=user.name,actor_email=user.email,reference_date=ref,filters_json=body.model_dump_json(),record_count=len(rows),filename=filename,snapshot_json=json.dumps(snaps,ensure_ascii=False)))
 await db.commit();buf.seek(0);return StreamingResponse(buf,media_type='application/zip',headers={'Content-Disposition':f'attachment; filename="Relatorios_Excel_{ref.isoformat()}.zip"','X-Report-Owners':str(len(owners))})

@app.post("/api/sync/excel/authoritative-rebuild")
async def authoritative_rebuild(body:RebuildBody,user:User=Depends(require("Administrador")),db:AsyncSession=Depends(session)):
 if body.confirm!="RECONSTRUIR":raise HTTPException(400,"Confirmação inválida para reconstrução autoritativa.")
 try:return await resync_authoritative_excel(db,user.email)
 except ValueError as exc:raise HTTPException(409,str(exc))

@app.get("/api/sync/status")
async def sync_status(user:User=Depends(current_user),db:AsyncSession=Depends(session)):
 pending=await db.scalar(select(func.count()).select_from(SyncQueue).where(SyncQueue.status=="pending"));latest=await db.scalar(select(SyncQueue).where(SyncQueue.status=="pending").order_by(SyncQueue.created_at.desc()));return {"pending":pending or 0,"lastError":latest.last_error if latest else None}

@app.post("/api/sync/retry")
async def retry_excel(user:User=Depends(require("Administrador","Editor")),db:AsyncSession=Depends(session)):return await retry_pending(db)
@app.get("/api/settings")
async def settings(user:User=Depends(current_user)):return json.loads(SETTINGS.read_text(encoding="utf-8"))
@app.put("/api/settings")
async def save_settings(body:SettingsBody,user:User=Depends(require("Administrador"))):SETTINGS.write_text(json.dumps(body.model_dump(),ensure_ascii=False,indent=2),encoding="utf-8");return body.model_dump()
@app.get("/api/conflicts")
async def conflicts(user:User=Depends(require("Administrador","Editor")),db:AsyncSession=Depends(session)):
 rows=(await db.scalars(select(SyncConflict).where(SyncConflict.status=="pending"))).all();return[{"id":x.id,"restrictionId":x.restriction_id,"field":x.field,"databaseValue":x.database_value,"excelValue":x.external_value,"status":x.status}for x in rows]
@app.get("/api/dashboard")
@app.get("/api/responsibles")
@app.get("/api/disciplines")
@app.get("/api/areas")
@app.get("/api/weekly-analysis")
async def analytical(user:User=Depends(current_user),db:AsyncSession=Depends(session)):return{"records":[out(r)for r in(await db.scalars(select(Restriction))).all()],"generatedAt":datetime.now(timezone.utc).isoformat()}
