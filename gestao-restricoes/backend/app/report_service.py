import io,re,unicodedata
from datetime import date,datetime
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4,landscape
from reportlab.lib.styles import ParagraphStyle,getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import BaseDocTemplate,Frame,PageTemplate,Paragraph,Spacer,Table,TableStyle,Image

LOGO_PATH=__import__('pathlib').Path(__file__).parent/'assets'/'logo-mcm-horizontal.png'
ORANGE=colors.HexColor('#ff5a14');CHARCOAL=colors.HexColor('#4f4f4f');LIGHT_ORANGE=colors.HexColor('#fff3ec')

DONE={"Concluída","Cancelada"}
def safe_name(value):
 value=unicodedata.normalize('NFKD',value or 'Geral').encode('ascii','ignore').decode()
 return re.sub(r'[^A-Za-z0-9_-]+','_',value).strip('_') or 'Geral'
def day_delta(r,ref):return (r.due_at-ref).days if r.due_at else 99999
def aging(r,ref):return max(0,(ref-r.raised_at).days) if r.raised_at and r.status!='Concluída' else 0
def criticality(r,ref):
 if r.status in DONE:return 'Baixa'
 d=day_delta(r,ref);score=40 if d<0 else 35 if d==0 else 30 if d<=2 else 20 if d<=5 else 10 if d<=10 else 0
 score+=30 if r.priority=='Alta' else 15 if r.priority=='Média' else 5
 a=aging(r,ref);score+=20 if a>20 else 15 if a>=10 else 10 if a>=5 else 0
 if re.search(r'imped|paralisa|caminho crítico|atraso|impossibilidade|não iniciar|bloqueio',r.impact or '',re.I):score+=15
 return 'Crítica' if score>=70 else 'Alta' if score>=50 else 'Média' if score>=25 else 'Baixa'
def situation(r,ref):
 if r.status=='Concluída':return 'CONCLUÍDA'
 if not r.due_at:return 'SEM PRAZO'
 d=day_delta(r,ref)
 return f'VENCIDA HÁ {abs(d)} DIA'+('' if abs(d)==1 else 'S') if d<0 else 'VENCE HOJE' if d==0 else 'VENCE AMANHÃ' if d==1 else f'VENCE EM {d} DIAS' if d<=7 else 'PRAZO: '+r.due_at.strftime('%d/%m/%Y')
def sorted_rows(rows,ref):
 rank={'Crítica':0,'Alta':1,'Média':2,'Baixa':3};priority={'Alta':0,'Média':1,'Baixa':2}
 return sorted(rows,key=lambda r:(0 if day_delta(r,ref)<0 else 1,rank[criticality(r,ref)],priority.get(r.priority,3),day_delta(r,ref),-aging(r,ref)))
def snapshot(r,ref):return {'id':r.external_id,'area':r.area,'cwp':r.cwp,'discipline':r.discipline,'task':r.task,'restriction':r.restriction,'action':r.action,'owner':r.owner,'company':r.company,'dueAt':r.due_at.isoformat() if r.due_at else None,'status':r.status,'priority':r.priority,'criticality':criticality(r,ref),'situation':situation(r,ref),'impact':r.impact,'aging':aging(r,ref)}
def summary(rows,ref):
 return {'total':len(rows),'overdue':sum(day_delta(r,ref)<0 and r.status not in DONE for r in rows),'critical':sum(criticality(r,ref)=='Crítica' for r in rows),'high':sum(r.priority=='Alta' for r in rows),'soon':sum(0<=day_delta(r,ref)<=7 and r.status not in DONE for r in rows)}
def pdf_bytes(rows,ref,project,owner,include_impact=False,general=False):
 rows=sorted_rows(rows,ref);stats=summary(rows,ref);buf=io.BytesIO();styles=getSampleStyleSheet();page=landscape(A4)
 doc=BaseDocTemplate(buf,pagesize=page,leftMargin=12*mm,rightMargin=12*mm,topMargin=12*mm,bottomMargin=12*mm)
 frame=Frame(doc.leftMargin,doc.bottomMargin,doc.width,doc.height,id='body');doc.addPageTemplates(PageTemplate(id='report',frames=frame,onPage=lambda c,d:(c.setFont('Helvetica',7),c.drawRightString(page[0]-12*mm,7*mm,f'Página {d.page}'))))
 small=ParagraphStyle('small',parent=styles['BodyText'],fontName='Helvetica',fontSize=7.2,leading=9,textColor=CHARCOAL);head=ParagraphStyle('head',parent=small,fontName='Helvetica-Bold',textColor=colors.white,alignment=TA_CENTER)
 logo=Image(str(LOGO_PATH),width=48*mm,height=12.7*mm) if LOGO_PATH.exists() else Paragraph('<b>MCM</b>',styles['Title']);report_title='RELATÓRIO GERAL DE RESTRIÇÕES' if general else 'RELATÓRIO DE RESTRIÇÕES';title=Paragraph(f'<font color="#ff5a14"><b>LEAN CONTROL</b></font><br/><font size="15" color="#4f4f4f"><b>{report_title}</b></font>',ParagraphStyle('title',parent=styles['Title'],alignment=2,leading=18));header=Table([[logo,title]],colWidths=[65*mm,doc.width-65*mm]);header.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LINEBELOW',(0,0),(-1,-1),1.5,ORANGE),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
 story=[header,Spacer(1,3*mm),Paragraph(f'<b>Projeto:</b> {project} &nbsp;&nbsp; <b>Responsável:</b> {owner or "Todos"} &nbsp;&nbsp; <b>Emissão:</b> {datetime.now().strftime("%d/%m/%Y %H:%M")} &nbsp;&nbsp; <b>Data de referência:</b> {ref.strftime("%d/%m/%Y")}',small),Spacer(1,4*mm)]
 cards=Table([[f'Total de pendências\n{stats["total"]}',f'Vencidas\n{stats["overdue"]}',f'Críticas\n{stats["critical"]}',f'Alta prioridade\n{stats["high"]}',f'Próximas 7 dias\n{stats["soon"]}']],colWidths=[52*mm]*5);cards.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),LIGHT_ORANGE),('BOX',(0,0),(-1,-1),.5,ORANGE),('INNERGRID',(0,0),(-1,-1),.3,colors.HexColor('#dfc7ba')),('TEXTCOLOR',(0,0),(-1,-1),CHARCOAL),('FONTNAME',(0,0),(-1,-1),'Helvetica-Bold'),('ALIGN',(0,0),(-1,-1),'CENTER'),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]));story += [cards,Spacer(1,4*mm)]
 who=f' sob responsabilidade de {owner}' if owner else ''
 story += [Paragraph(f'Na data de emissão deste relatório, constam {stats["total"]} restrições{who}, sendo {stats["overdue"]} vencidas, {stats["critical"]} classificadas como críticas e {stats["soon"]} com vencimento nos próximos 7 dias. Recomenda-se priorizar os itens destacados de acordo com prazo e impacto nas atividades.',small),Spacer(1,4*mm)]
 headers=['ID','Área/CWA','Disciplina','Tarefa','Restrição','Ação para Liberação','Prazo','Situação','Prioridade']+(['Impacto / Observação'] if include_impact else [])
 data=[[Paragraph(x,head) for x in headers]]
 for r in rows:
  vals=[r.external_id or '',r.area or '—',r.discipline or '—',r.task or '—',r.restriction or '—',r.action or '—',r.due_at.strftime('%d/%m/%Y') if r.due_at else '—',situation(r,ref),r.priority or '—']+([r.impact or '—'] if include_impact else [])
  data.append([Paragraph(str(x),small) for x in vals])
 widths=[9,18,19,38,42,48,17,27,16]+([38] if include_impact else []);scale=doc.width/sum(widths)
 table=Table(data,repeatRows=1,colWidths=[x*scale for x in widths]);commands=[('BACKGROUND',(0,0),(-1,0),CHARCOAL),('LINEBELOW',(0,0),(-1,0),2,ORANGE),('GRID',(0,0),(-1,-1),.3,colors.HexColor('#c9c9c9')),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),3),('RIGHTPADDING',(0,0),(-1,-1),3),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4)]
 for i,r in enumerate(rows,1):
  bg=colors.HexColor('#fdeaea') if day_delta(r,ref)<0 else colors.HexColor('#fff0dc') if day_delta(r,ref)<=1 else colors.HexColor('#fff8d8') if day_delta(r,ref)<=7 else colors.white
  if r.status=='Concluída':bg=colors.HexColor('#edf4f1')
  commands.append(('BACKGROUND',(0,i),(-1,i),bg))
 table.setStyle(TableStyle(commands));story.append(table);doc.build(story);return buf.getvalue()
