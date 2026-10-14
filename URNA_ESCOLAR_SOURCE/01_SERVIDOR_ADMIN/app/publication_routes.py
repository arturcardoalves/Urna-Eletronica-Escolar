"""Authenticated administrative and local-desktop publication endpoints."""
from fastapi import Depends,Form,HTTPException,Request
from fastapi.responses import Response,RedirectResponse
from sqlalchemy import select
from .auth import get_db,require_role,current_user
from .models import PublicationDocument
from .services import get_election,DomainError
from .deployment import local_control,write_lock
from . import publication as pub
from publication_core.media import removable_drives
from publication_core.protocol import verify_package,InvalidPackage

def register(app,templates):
    admin= require_role('ADMIN')
    @app.get('/admin/publication')
    def page(request:Request,user=Depends(admin),db=Depends(get_db)):
        election=get_election(db)
        rows=db.scalars(select(PublicationDocument).where(PublicationDocument.election_id==election.election_uuid).order_by(PublicationDocument.created_at)).all()
        return templates.TemplateResponse(request=request,name='publication.html',context={'election':election,'config':pub.config(db,election.election_uuid),'documents':rows,'drives':[str(p) for p in removable_drives()]})

    @app.post('/admin/publication/configure')
    def configure(url:str=Form(...),user=Depends(admin),db=Depends(get_db)):
        try:
            with write_lock:
                pub.configure(db,get_election(db),url,user.username);db.commit()
        except (ValueError,DomainError) as e:
            db.rollback();raise HTTPException(409,str(e)) from e
        return RedirectResponse('/admin/publication',303)

    @app.get('/admin/publication/{document_id}/package')
    def package(document_id:str,user=Depends(admin),db=Depends(get_db)):
        row=db.get(PublicationDocument,document_id)
        if not row:raise HTTPException(404,'Documento não encontrado')
        verify_package(row.package)
        return Response(row.package,media_type='application/octet-stream',headers={'Content-Disposition':f'attachment; filename="{row.id}.uepkg"'})

    @app.get('/admin/publication/{document_id}/pdf')
    def pdf(document_id:str,user=Depends(admin),db=Depends(get_db)):
        row=db.get(PublicationDocument,document_id)
        if not row:raise HTTPException(404,'Documento não encontrado')
        data=verify_package(row.package)['assets']['document.pdf']
        return Response(data,media_type='application/pdf',headers={'Content-Disposition':f'inline; filename="{row.id}.pdf"'})

    @app.post('/admin/publication/{document_id}/rectify')
    def rectify(document_id:str,reason:str=Form(...),user=Depends(admin),db=Depends(get_db)):
        row=db.get(PublicationDocument,document_id)
        if not row or row.election_id!=get_election(db).election_uuid:raise HTTPException(404,'Documento não disponível para retificação')
        if not 10<=len(reason.strip())<=500:raise HTTPException(400,'Descreva o motivo em 10 a 500 caracteres')
        try:
            with write_lock:
                if pub.latest(db,row.election_id,row.kind,row.urn_code).id!=row.id:raise DomainError('Retifique a versão mais recente')
                pub.prepare(db,row.kind,user.username,reason.strip(),row.urn_code)
                if row.kind in ('zero','result'):
                    from .main import _queue_device_document,_zero_thermal_text,_result_thermal_text
                    render=_zero_thermal_text if row.kind=='zero' else _result_thermal_text
                    _queue_device_document(db,row.kind,lambda urn:render(db,urn),1,{row.urn_code})
                db.commit()
        except (ValueError,DomainError) as e:db.rollback();raise HTTPException(409,str(e)) from e
        return RedirectResponse('/admin/publication',303)

    @app.post('/admin/publication/export')
    def export(drive:str=Form(...),user=Depends(admin),db=Depends(get_db)):
        rows=db.scalars(select(PublicationDocument).where(PublicationDocument.election_id==get_election(db).election_uuid)).all()
        try:
            pub.export_rows(db,[r for r in rows if pub.ready_to_export(db,r)],drive,user.username)
        except (ValueError,OSError) as e:db.rollback();raise HTTPException(409,str(e)) from e
        return RedirectResponse('/admin/publication',303)

    @app.get('/api/publication/status')
    def status(user=Depends(current_user),db=Depends(get_db)):
        if user.role not in ('ADMIN','MESARIO'):raise HTTPException(403,'Operação não autorizada')
        rows=pub.pending(db)
        label='Insira a mídia USB para exportar a Zerésima' if any(r.kind=='zero' for r in rows) else 'Insira a mídia USB na Central para exportar os documentos assinados' if rows else ''
        return {'pending':len(rows),'message':label}

    @app.get('/api/local/publication',dependencies=[Depends(local_control)])
    def local_status(db=Depends(get_db)):
        rows=pub.pending(db)
        return {'pending':len(rows),'kinds':sorted({r.kind for r in rows}),'drives':[str(p) for p in removable_drives()]}

    @app.post('/api/local/publication/export',dependencies=[Depends(local_control)])
    def local_export(drive:str=Form(...),db=Depends(get_db)):
        try:
            with write_lock:return {'files':pub.export_rows(db,pub.pending(db),drive,'CENTRAL_LOCAL')}
        except (ValueError,OSError) as e:db.rollback();raise HTTPException(409,str(e)) from e
