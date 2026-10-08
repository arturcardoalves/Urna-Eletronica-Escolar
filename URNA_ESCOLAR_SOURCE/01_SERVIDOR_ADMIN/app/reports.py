from io import BytesIO
from html import escape
import json
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from sqlalchemy import select
from sqlalchemy.orm import Session
from .config import APP_VERSION
from .models import AuditEvent, Election, Occurrence, Voter, Slate, Urn
from .services import DomainError, verify_zero_snapshot_integrity
from .tally_service import verify_final_tally_integrity


def _base_doc():
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=16*mm, leftMargin=16*mm, topMargin=14*mm, bottomMargin=14*mm)
    return buf, doc, getSampleStyleSheet()




def zero_pdf(db: Session) -> bytes:
    election = db.execute(select(Election).limit(1)).scalar_one()
    if not election.zero_snapshot_json:
        raise ValueError("A zerésima ainda não foi emitida.")
    try:
        verify_zero_snapshot_integrity(db)
    except DomainError as exc:
        raise ValueError(str(exc)) from exc
    snap = json.loads(election.zero_snapshot_json)
    buf, doc, styles = _base_doc()
    story = [
        Paragraph("ZERÉSIMA", styles["Title"]),
        Paragraph(snap.get("election") or election.name, styles["Heading2"]),
        Paragraph(snap.get("institution") or "Instituição não informada", styles["Normal"]),
        Spacer(1, 5*mm),
        Paragraph(f"Emitida em: {snap.get('issued_at','—')}", styles["Normal"]),
        Paragraph(f"Versão do software: {snap.get('software_version', APP_VERSION)}", styles["Normal"]),
        Paragraph(f"Identificador da eleição: {snap.get('election_uuid') or '—'}", styles["Normal"]),
        Paragraph(f"Hash da configuração: {snap.get('config_hash') or '—'}", styles["Normal"]),
        Paragraph(f"Hash do software lacrado: {snap.get('software_hash') or '—'}", styles["Normal"]),
        Paragraph(f"Impressão digital da chave interna: {snap.get('public_key_fingerprint') or '—'}", styles["Normal"]),
        Paragraph(f"Hash do retrato da zerésima: {election.zero_snapshot_hash or '—'}", styles["Normal"]),
        Paragraph(f"Âncora de auditoria pré-zerésima: {snap.get('audit_head_before_zero') or '—'}", styles["Normal"]),
        Paragraph((f"Eleitores cadastrados: {snap.get('registered_voters',0)}" if snap.get("voter_identification_enabled", True) else "Identificação nominal de eleitores: DESATIVADA"), styles["Normal"]),
        Paragraph("Urnas configuradas: " + ", ".join(f"{u['code']} ({u['name']})" for u in snap.get("urns", [])), styles["Normal"]),
        Spacer(1, 5*mm),
    ]
    data = [["Número", "Chapa", "Votos"]] + [[str(item["number"]), item["name"], str(item.get("votes",0))] for item in snap.get("slates", [])]
    if snap.get("allow_blank"):
        data.append(["—", "BRANCO", "0"])
    table = Table(data, colWidths=[30*mm, 105*mm, 25*mm])
    table.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 0.5, colors.black),
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#ECEFF1")),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("ALIGN", (0,0), (0,-1), "CENTER"),
        ("ALIGN", (-1,0), (-1,-1), "CENTER"),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("TOPPADDING", (0,0), (-1,-1), 6),
    ]))
    story.append(table)
    story += [Spacer(1, 5*mm), Paragraph(f"Total de votos registrados no momento da emissão: {snap.get('ballot_count',0)}", styles["Normal"])]
    if election.zero_signature_fields:
        story += [Spacer(1, 15*mm), Paragraph("Assinaturas", styles["Heading3"]), Spacer(1, 12*mm), Paragraph("____________________________________    ____________________________________", styles["Normal"])]
    doc.build(story)
    return buf.getvalue()


def voter_list_pdf(db: Session, only_status: str | None = None, signature: bool = True, sort: str = "class", shift: str | None = None, class_code: str | None = None, class_pages: bool = False) -> bytes:
    stmt = select(Voter)
    if only_status:
        stmt = stmt.where(Voter.status == only_status)
    if shift:
        stmt = stmt.where(Voter.shift == shift)
    if class_code:
        stmt = stmt.where(Voter.class_code == class_code)
    if sort == "name":
        stmt = stmt.order_by(Voter.name)
    elif sort == "shift":
        stmt = stmt.order_by(Voter.shift, Voter.name)
    else:
        stmt = stmt.order_by(Voter.class_code, Voter.name)
    voters = db.execute(stmt).scalars().all()
    election = db.execute(select(Election).limit(1)).scalar_one()
    buf, doc, styles = _base_doc()
    title = "Relação de Eleitores"
    if only_status == "VOTED": title = "Eleitores que votaram"
    if only_status == "NOT_VOTED": title = "Eleitores que não votaram"

    headers = ["Matrícula", "Nome", "Turma", "Turno"] + (["Assinatura"] if signature else [])
    # A área útil do A4 é 178 mm. Com assinatura, matrícula/turma/turno ficam
    # compactos e a assinatura recebe 56 mm. Campos longos quebram linha em
    # vez de ultrapassar a célula. Matrículas escolares são limitadas a 10 dígitos.
    widths = ([24*mm, 56*mm, 18*mm, 24*mm, 56*mm] if signature
              else [30*mm, 85*mm, 25*mm, 38*mm])
    cell_style = ParagraphStyle("VoterTableCell", parent=styles["Normal"], fontName="Helvetica", fontSize=8, leading=9.4, spaceAfter=0, spaceBefore=0)

    def cell(value):
        return Paragraph(escape(str(value or "")), cell_style)

    def make_table(items):
        rows = [headers]
        for v in items:
            row = [cell(v.enrollment), cell(v.name), cell(v.class_code), cell(v.shift)]
            if signature:
                row.append("")
            rows.append(row)
        table = Table(rows, colWidths=widths, repeatRows=1)
        table.setStyle(TableStyle([
            ("GRID", (0,0), (-1,-1), 0.35, colors.black),
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#ECEFF1")),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE", (0,0), (-1,-1), 8),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("TOPPADDING", (0,0), (-1,-1), 7),
            ("BOTTOMPADDING", (0,0), (-1,-1), 7),
        ]))
        return table

    story = []
    if class_pages:
        groups = {}
        for v in voters:
            groups.setdefault((v.class_code or "Sem turma", v.shift or ""), []).append(v)
        for idx, ((cls, sh), items) in enumerate(sorted(groups.items(), key=lambda x: (x[0][0], x[0][1]))):
            if idx:
                story.append(PageBreak())
            story += [
                Paragraph(title, styles["Title"]),
                Paragraph(election.name, styles["Heading2"]),
                Paragraph(f"Turma {cls}" + (f" · {sh}" if sh else ""), styles["Heading2"]),
                Paragraph(f"Total nesta turma: {len(items)}", styles["Normal"]),
                Spacer(1, 4*mm),
                make_table(items),
            ]
        if not groups:
            story = [Paragraph(title, styles["Title"]), Paragraph("Nenhum eleitor encontrado.", styles["Normal"])]
    else:
        story = [Paragraph(title, styles["Title"]), Spacer(1, 4*mm), make_table(voters)]
    doc.build(story)
    return buf.getvalue()


def final_result_pdf(db: Session) -> bytes:
    """Gera o Boletim de Urna em A4 sem interpretar vencedor ou colocação."""
    election = db.execute(select(Election).limit(1)).scalar_one()
    if not election.final_tally_json:
        raise ValueError("Resultado ainda não apurado")
    try:
        result = verify_final_tally_integrity(db)
    except DomainError as exc:
        raise ValueError(str(exc)) from exc

    voter_count = len(db.execute(select(Voter)).scalars().all())
    voted_count = int(result.get("total", 0))
    result_by_number = {int(item.get("number", 0)): int(item.get("votes", 0)) for item in result.get("slates", [])}
    slates = db.execute(select(Slate).where(Slate.active == True).order_by(Slate.number)).scalars().all()

    buf, doc, styles = _base_doc()
    story = [
        Paragraph("BOLETIM DE URNA", styles["Title"]),
        Paragraph(election.name, styles["Heading2"]),
        Paragraph(election.institution_name or "Instituição não informada", styles["Normal"]),
        Spacer(1, 3*mm),
        Paragraph(f"Identificador da eleição: {election.election_uuid}", styles["Normal"]),
        Paragraph(f"Versão do sistema: {APP_VERSION}", styles["Normal"]),
        Paragraph(f"Data de abertura: {election.opened_at.strftime('%d/%m/%Y') if election.opened_at else '—'}", styles["Normal"]),
        Paragraph(f"Horário de abertura: {election.opened_at.strftime('%H:%M:%S') if election.opened_at else '—'}", styles["Normal"]),
        Paragraph(f"Data de fechamento: {election.closed_at.strftime('%d/%m/%Y') if election.closed_at else '—'}", styles["Normal"]),
        Paragraph(f"Horário de fechamento: {election.closed_at.strftime('%H:%M:%S') if election.closed_at else '—'}", styles["Normal"]),
        Spacer(1, 4*mm),
    ]

    if election.voter_identification_enabled:
        summary_rows = [
            ["Eleitores aptos", f"{voter_count:03d}"],
            ["Comparecimento", f"{voted_count:03d}"],
            ["Eleitores faltosos", f"{max(0, voter_count-voted_count):03d}"],
        ]
    else:
        summary_rows = [
            ["Identificação nominal", "DESATIVADA"],
            ["Total de votos registrados", f"{voted_count:03d}"],
        ]
    summary = Table(summary_rows, colWidths=[75*mm, 30*mm])
    summary.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 0.4, colors.black),
        ("BACKGROUND", (0,0), (0,-1), colors.HexColor("#F0F2F4")),
        ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
        ("ALIGN", (1,0), (1,-1), "CENTER"),
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ]))
    story += [summary, Spacer(1, 6*mm), Paragraph("CHAPAS", styles["Heading2"]), Spacer(1, 2*mm)]

    for slate in slates:
        story.append(Paragraph(f"CHAPA {slate.number:02d} - {escape(slate.name)}", styles["Heading3"]))
        member_rows = [["Função", "Nome"]]
        for member in sorted(slate.members, key=lambda m: (m.display_order, m.id)):
            member_rows.append([member.role_name or "Integrante", member.person_name])
        if len(member_rows) > 1:
            members = Table(member_rows, colWidths=[48*mm, 105*mm], repeatRows=1)
            members.setStyle(TableStyle([
                ("GRID", (0,0), (-1,-1), 0.4, colors.HexColor("#6A7178")),
                ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#ECEFF1")),
                ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
                ("VALIGN", (0,0), (-1,-1), "TOP"),
                ("TOPPADDING", (0,0), (-1,-1), 4),
                ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ]))
            story.append(members)
        votes = result_by_number.get(slate.number, 0)
        story.append(Paragraph(f"<b>Votos: {votes:03d}</b>", styles["Normal"]))
        story.append(Spacer(1, 4*mm))

    # Resumo principal das chapas em três colunas, no padrão visual do BO
    # oficial: nome totalmente à esquerda; número da chapa e votos em duas
    # colunas fixas à direita. Nomes longos quebram linha sem deslocar os
    # números nem a contagem de votos.
    summary_header = ParagraphStyle(
        "BoSummaryHeader", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=13.5, leading=16, spaceAfter=0, spaceBefore=0
    )
    summary_name_style = ParagraphStyle(
        "BoSummaryName", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=12.5, leading=14.5, spaceAfter=0, spaceBefore=0
    )
    summary_num_style = ParagraphStyle(
        "BoSummaryNum", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=12.5, leading=14.5, alignment=2, spaceAfter=0, spaceBefore=0
    )
    summary_vote_style = ParagraphStyle(
        "BoSummaryVote", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=12.5, leading=14.5, alignment=2, spaceAfter=0, spaceBefore=0
    )
    comparison_rows = [[
        Paragraph("Nome da chapa", summary_header),
        Paragraph("Num", summary_header),
        Paragraph("Votos", summary_header),
    ]]
    for slate in slates:
        comparison_rows.append([
            Paragraph(escape(slate.name), summary_name_style),
            Paragraph(f"{slate.number:02d}", summary_num_style),
            Paragraph(f"{result_by_number.get(slate.number, 0):03d}", summary_vote_style),
        ])
    comparison = Table(comparison_rows, colWidths=[123*mm, 18*mm, 22*mm], repeatRows=1)
    comparison.setStyle(TableStyle([
        ("LINEBELOW", (0,0), (-1,0), 0.8, colors.black),
        ("ALIGN", (0,0), (0,-1), "LEFT"),
        ("ALIGN", (1,0), (-1,-1), "RIGHT"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0), (-1,0), 3),
        ("BOTTOMPADDING", (0,0), (-1,0), 7),
        ("TOPPADDING", (0,1), (-1,-1), 5),
        ("BOTTOMPADDING", (0,1), (-1,-1), 5),
        ("LEFTPADDING", (0,0), (0,-1), 0),
        ("LEFTPADDING", (1,0), (-1,-1), 4),
        ("RIGHTPADDING", (0,0), (-1,-1), 0),
    ]))
    story += [
        Spacer(1, 2*mm),
        KeepTogether([
            Paragraph("RESUMO DAS CHAPAS", styles["Heading2"]),
            Spacer(1, 1*mm),
            comparison,
        ]),
        Spacer(1, 5*mm),
    ]

    apuracao_rows = []
    if election.allow_blank:
        apuracao_rows.append(["Brancos", f"{int(result.get("blank", 0)):03d}"])
    if int(result.get("invalid", 0)):
        apuracao_rows.append(["Registros inválidos", f"{int(result.get("invalid", 0)):03d}"])
    apuracao_rows.append(["Total apurado", f"{voted_count:03d}"])
    apuracao = Table(apuracao_rows, colWidths=[75*mm, 30*mm])
    apuracao.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 0.4, colors.black),
        ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
        ("ALIGN", (1,0), (1,-1), "CENTER"),
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ]))
    story += [apuracao, Spacer(1, 6*mm)]

    story += [
        Paragraph(f"Hash de integridade dos votos: {result.get('ballot_head_hash','—')}", styles["Normal"]),
        Paragraph(f"Hash da configuração lacrada: {result.get('config_hash') or election.config_hash or '—'}", styles["Normal"]),
        Paragraph(f"Hash da zerésima: {result.get('zero_snapshot_hash') or election.zero_snapshot_hash or '—'}", styles["Normal"]),
        Paragraph(f"Âncora de auditoria da apuração: {result.get('audit_head_at_tally') or '—'}", styles["Normal"]),
    ]
    doc.build(story)
    return buf.getvalue()


def audit_log_pdf(db: Session, event_type: str | None = None) -> bytes:
    election = db.execute(select(Election).limit(1)).scalar_one()
    stmt = select(AuditEvent).order_by(AuditEvent.id)
    if event_type:
        stmt = stmt.where(AuditEvent.event_type == event_type)
    events = db.execute(stmt).scalars().all()
    buf, doc, styles = _base_doc()
    story = [
        Paragraph("LOG OPERACIONAL", styles["Title"]),
        Paragraph(election.name, styles["Heading2"]),
        Paragraph(election.institution_name or "Instituição não informada", styles["Normal"]),
        Paragraph(f"Versão: {APP_VERSION} · Eventos: {len(events)}", styles["Normal"]),
        Spacer(1, 4*mm),
    ]
    rows = [["Data/hora", "Evento", "Responsável", "Detalhes"]]
    for e in events:
        try:
            details = json.loads(e.details_json or "{}")
            detail_text = json.dumps(details, ensure_ascii=False, sort_keys=True)
        except Exception:
            detail_text = e.details_json or "{}"
        rows.append([e.created_at.strftime("%d/%m/%Y %H:%M:%S"), e.event_type, e.actor, Paragraph(detail_text, styles["Normal"])])
    if len(rows) == 1:
        rows.append(["—", "—", "—", "Nenhum evento registrado."])
    table = Table(rows, colWidths=[34*mm, 40*mm, 34*mm, 72*mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("GRID",(0,0),(-1,-1),0.3,colors.black),
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#ECEFF1")),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
        ("FONTSIZE",(0,0),(-1,-1),7),
        ("VALIGN",(0,0),(-1,-1),"TOP"),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
    ]))
    story.append(table)
    doc.build(story)
    return buf.getvalue()

def occurrences_pdf(db: Session) -> bytes:
    election = db.execute(select(Election).limit(1)).scalar_one()
    occurrences = db.execute(select(Occurrence).order_by(Occurrence.created_at)).scalars().all()
    buf, doc, styles = _base_doc()
    story = [Paragraph("RELATÓRIO DE OCORRÊNCIAS", styles["Title"]), Paragraph(election.name, styles["Heading2"]), Spacer(1, 5*mm)]
    rows = [["Data/hora", "Responsável", "Descrição"]]
    for item in occurrences:
        rows.append([item.created_at.strftime("%d/%m/%Y %H:%M:%S"), item.author, Paragraph(item.description, styles["Normal"])])
    if len(rows) == 1:
        rows.append(["—", "—", "Nenhuma ocorrência registrada."])
    table = Table(rows, colWidths=[38*mm, 42*mm, 100*mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 0.35, colors.black),
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#ECEFF1")),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 8),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ]))
    story.append(table)
    doc.build(story)
    return buf.getvalue()
