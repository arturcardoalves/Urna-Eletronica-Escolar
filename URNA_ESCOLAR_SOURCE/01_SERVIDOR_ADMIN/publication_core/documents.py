"""Thermal-safe QR raster and public PDFs generated from the signed snapshot."""
import io
from html import escape
import qrcode
from PIL import Image
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,Image as PDFImage,KeepTogether
from .protocol import canonical,digest,qr_text

LABELS={'configuration':'Configuração e lacração','zero':'Zerésima','result':'Boletim de Urna'}
def qr_image(text,max_width=528):
    if len(text)>1000: raise ValueError('Conteúdo QR excede o limite para papel 80 mm')
    qr=qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M,border=4,box_size=4)
    qr.add_data(text);qr.make(fit=True)
    modules=qr.modules_count+8
    scale=min(6,max_width//modules)
    if scale<4: raise ValueError('QR denso demais para leitura em 80 mm')
    qr.box_size=scale
    return qr.make_image(fill_color='black',back_color='white').convert('L')

def links(document,key):
    return {'consultation':document['election']['public_url']+'/documents/'+document['id'],
            'verification':document['election']['public_url']+'/verify#'+qr_text(document,key),
            'fingerprint':digest(key.public_key().public_bytes_raw()),'document_id':document['id'],
            'revision':document['revision'],'correction':document['correction'],
            'document_digest':digest(canonical(document))}

def render_pdf(document,qr,photos):
    buf=io.BytesIO();styles=getSampleStyleSheet()
    doc=SimpleDocTemplate(buf,pagesize=A4,rightMargin=16*mm,leftMargin=16*mm,topMargin=14*mm,bottomMargin=14*mm,title=LABELS[document['kind']])
    def p(text,style='BodyText'):return Paragraph(escape(str(text)),styles[style])
    election=document['election'];urn=next((u for u in election['urns'] if u['id']==document['urn_id']),None)
    story=[p(LABELS[document['kind']],'Title'),p(election['school'],'Heading2'),p(election['name'],'Heading2'),p('Eleição: '+election['id']),p('Documento: '+document['id']),p('Emissão (UTC): '+document['created_at']),p('Revisão: '+str(document['revision']))]
    if urn:story.append(p('Urna: '+urn['code']+' — '+urn['name']))
    if document['correction']:story.append(p('Retificação: '+document['correction']))
    story.append(Spacer(1,5*mm))
    counts={s['number']:s['votes'] for s in document['totals']['slates']} if document['totals'] else None
    for slate in election['slates']:
        block=[p(f"Chapa {slate['number']:02d} — {slate['name']}",'Heading3')]
        if document['kind']=='configuration' and slate['photo']:
            block.append(PDFImage(io.BytesIO(photos[slate['photo']]),width=25*mm,height=25*mm,kind='proportional'))
        block.extend(p(m['role']+': '+m['name']) for m in slate['members'])
        if counts is not None:block.append(p('Votos: '+str(counts[slate['number']])))
        story+=block
    if document['totals']:
        t=document['totals']
        story += [p(f"Brancos: {t['blank']} · Nulos: {t['null']} · Total: {t['total']}",'Heading2'),p('Comparecimento nesta urna: '+(str(t['attendance']) if t['attendance'] is not None else 'não aferido no modo sem identificação'))]
    else:
        story += [p('Urnas previstas','Heading2')]+[p(u['code']+' — '+u['name']+' · '+u['id']) for u in election['urns']]
    story += [p('Eleitores cadastrados na eleição: '+(str(document['totals']['registered'] if document['totals'] else election['registered']) if election['registered'] is not None else 'identificação desativada')),p('Hash da configuração: '+election['config_hash']),p('SHA-256 dos dados públicos: '+qr['document_digest']),p('Chave pública — impressão digital: '+qr['fingerprint'])]
    for field,label in [('software_version','Versão do sistema'),('zero_issued_at','Zerésima emitida (UTC)'),('opened_at','Abertura (UTC)'),('closed_at','Encerramento (UTC)'),('zero_snapshot_hash','Hash da zerésima'),('ballot_set_hash','Hash do conjunto de votos')]:
        if document['evidence'][field]:story.append(p(label+': '+document['evidence'][field]))
    for label,name in [('Consulta pública','consultation'),('Verificação criptográfica independente','verification')]:
        png=io.BytesIO();qr_image(qr[name]).save(png,format='PNG')
        story.append(KeepTogether([p(label,'Heading3'),PDFImage(io.BytesIO(png.getvalue()),width=56*mm,height=56*mm),Spacer(1,3*mm)]))
    story += [p('A assinatura identifica a chave emissora. Compare sua impressão digital com uma referência obtida da comissão. Para conferir os dados, use também o manifesto assinado e compare os valores impressos.'),p('Assinaturas da comissão','Heading3'),Spacer(1,12*mm),p('_____________________     _____________________     _____________________')]
    doc.build(story)
    return buf.getvalue()
