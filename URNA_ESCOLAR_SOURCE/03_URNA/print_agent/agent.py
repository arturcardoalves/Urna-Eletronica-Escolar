from __future__ import annotations

import os
import json
import threading
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    from PIL import Image, ImageDraw, ImageFont
except Exception:
    Image = None
    ImageDraw = None
    ImageFont = None

try:
    import win32print
    import win32ui
    import win32con
except Exception as exc:  # pragma: no cover - only available on Windows
    win32print = None
    win32ui = None
    win32con = None
    IMPORT_ERROR = str(exc)
else:
    IMPORT_ERROR = None


app = FastAPI(title="Urna Escolar - Agente de Impressão", version="2.2.1")
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+)(:\d+)?$",
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

_lock = threading.Lock()
_last_failed_job: dict[str, Any] | None = None

DEFAULT_CUT_FEED_MM = 30
MIN_CUT_FEED_MM = 10
MAX_CUT_FEED_MM = 80


class PrintJob(BaseModel):
    printer: str
    text: str = ""
    title: str = "Urna Escolar"
    cut: bool = True
    copies: int = 1
    # ballot = voto físico; text = zerésima/BU/log/relatórios operacionais.
    layout: str = "text"
    paper: dict[str, Any] | None = None
    # windows = driver instalado no Windows; escpos = RAW ESC/POS.
    mode: str = "windows"
    paper_width_mm: int = 0
    # Espaço físico entre o último conteúdo e a lâmina da impressora térmica.
    cut_feed_mm: int = DEFAULT_CUT_FEED_MM


def _normalized_cut_feed_mm(value: Any) -> int:
    """Limita o avanço a uma faixa segura, inclusive para clientes antigos."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = DEFAULT_CUT_FEED_MM
    return max(MIN_CUT_FEED_MM, min(parsed, MAX_CUT_FEED_MM))


def _escpos_finish(job: PrintJob) -> bytes:
    """Avança o papel pela distância configurada e só então aciona o corte.

    ESC J usa unidades verticais de aproximadamente 1/203 de polegada nas
    térmicas ESC/POS usuais. O comando é dividido porque cada avanço aceita
    no máximo 255 unidades.
    """
    if not job.cut:
        return b""
    remaining = round(_normalized_cut_feed_mm(job.cut_feed_mm) * 203 / 25.4)
    output = bytearray()
    while remaining > 0:
        step = min(remaining, 255)
        output.extend(b"\x1bJ" + bytes([step]))
        remaining -= step
    output.extend(b"\x1dV\x01")
    return bytes(output)


def _require_windows():
    if os.name != "nt" or win32print is None or win32ui is None:
        raise HTTPException(503, f"Agente requer Windows + pywin32. {IMPORT_ERROR or ''}".strip())



def _atkinson_font_paths() -> tuple[str, str]:
    """Localiza Atkinson Hyperlegible instalada pelo instalador oficial do projeto."""
    candidates = []
    local = os.environ.get("LOCALAPPDATA")
    windir = os.environ.get("WINDIR", r"C:\Windows")
    if local:
        candidates.append(os.path.join(local, "Microsoft", "Windows", "Fonts"))
    candidates.append(os.path.join(windir, "Fonts"))

    regular_names = [
        "AtkinsonHyperlegible-Regular.otf",
        "AtkinsonHyperlegible-Regular.ttf",
    ]
    bold_names = [
        "AtkinsonHyperlegible-Bold.otf",
        "AtkinsonHyperlegible-Bold.ttf",
    ]

    regular = None
    bold = None
    for folder in candidates:
        for name in regular_names:
            p = os.path.join(folder, name)
            if os.path.exists(p):
                regular = p
                break
        for name in bold_names:
            p = os.path.join(folder, name)
            if os.path.exists(p):
                bold = p
                break
        if regular and bold:
            break

    if not regular or not bold:
        raise RuntimeError(
            "Fonte Atkinson Hyperlegible não encontrada neste computador. "
            "Instale Regular + Bold antes de imprimir votos."
        )
    return regular, bold


def _atkinson_installed() -> bool:
    try:
        _atkinson_font_paths()
        return True
    except Exception:
        return False


def _pil_font(size_px: int, bold: bool = False):
    if ImageFont is None:
        raise RuntimeError(
            "Pillow não está instalado no agente de impressão. "
            "Execute novamente 'Preparar agente'."
        )
    regular, bold_path = _atkinson_font_paths()
    return ImageFont.truetype(bold_path if bold else regular, size=max(8, int(size_px)))


def _wrap_pil(draw, text: str, font, max_width: int) -> list[str]:
    text = " ".join((text or "").upper().split())
    if not text:
        return []
    words = text.split(" ")
    lines: list[str] = []
    line = ""

    def width(value: str) -> int:
        box = draw.textbbox((0, 0), value, font=font)
        return box[2] - box[0]

    def split_word(word: str) -> list[str]:
        parts: list[str] = []
        piece = ""
        for ch in word:
            candidate = piece + ch
            if piece and width(candidate) > max_width:
                parts.append(piece)
                piece = ch
            else:
                piece = candidate
        if piece:
            parts.append(piece)
        return parts or [word]

    for word in words:
        if width(word) > max_width:
            if line:
                lines.append(line)
                line = ""
            pieces = split_word(word)
            lines.extend(pieces[:-1])
            line = pieces[-1]
            continue

        candidate = word if not line else line + " " + word
        if width(candidate) <= max_width:
            line = candidate
        else:
            if line:
                lines.append(line)
            line = word

    if line:
        lines.append(line)
    return lines


def _draw_center_pil(draw, text: str, font, center_x: int, y: int) -> int:
    box = draw.textbbox((0, 0), text, font=font)
    w = box[2] - box[0]
    h = box[3] - box[1]
    draw.text((center_x - w // 2, y - box[1]), text, font=font, fill=0)
    return h


def _escpos_raster_bytes(image) -> bytes:
    """Converte imagem monocromática para GS v 0 (raster ESC/POS)."""
    if Image is None:
        raise RuntimeError("Pillow não está instalado.")
    img = image.convert("L")
    width, height = img.size
    width_bytes = (width + 7) // 8
    data = bytearray(width_bytes * height)
    pix = img.load()
    for y in range(height):
        row = y * width_bytes
        for x in range(width):
            if pix[x, y] < 128:
                data[row + (x // 8)] |= 0x80 >> (x % 8)

    xL = width_bytes & 0xFF
    xH = (width_bytes >> 8) & 0xFF
    yL = height & 0xFF
    yH = (height >> 8) & 0xFF
    return b"\x1d\x76\x30\x00" + bytes([xL, xH, yL, yH]) + bytes(data)


def _enc(value: str) -> bytes:
    try:
        return value.encode("cp850", errors="replace")
    except LookupError:
        return value.encode("latin-1", errors="replace")


def _center_text(text: str, columns: int = 42) -> bytes:
    return _enc(text[:columns].center(columns)) + b"\n"


def _escpos_ballot(job: PrintJob) -> bytes:
    """Cédula ESC/POS rasterizada integralmente em Atkinson Hyperlegible.

    A térmica não usa a fonte residente da impressora. O agente monta a cédula
    como imagem usando Atkinson Hyperlegible e envia o bitmap ao equipamento.
    Assim Windows/driver e ESC/POS preservam a mesma tipografia visual.
    """
    if Image is None or ImageDraw is None or ImageFont is None:
        raise RuntimeError(
            "Pillow não está disponível. Execute novamente 'Preparar agente'."
        )
    _atkinson_font_paths()  # falha claramente se a fonte não estiver instalada

    paper = job.paper or {}
    institution = str(paper.get("institution") or "").strip()
    election = str(paper.get("election") or "").strip()
    number = paper.get("number")
    slate = str(paper.get("slate") or "").strip()
    instruction = str(paper.get("instruction") or "DOBRE E COLOQUE NA URNA").strip()

    # 576 dots = aproximadamente 72 mm úteis a 203 dpi.
    width = 576
    height = 720
    fold_y = height // 2
    margin = 24
    inner_left = margin
    inner_right = width - margin
    inner_w = inner_right - inner_left
    cx = width // 2

    image = Image.new("L", (width, height), 255)
    draw = ImageDraw.Draw(image)

    regular_22 = _pil_font(22, False)
    bold_28 = _pil_font(28, True)
    label_24 = _pil_font(24, False)
    number_font = _pil_font(112, True)
    instruction_font = _pil_font(28, True)

    # Contorno com margem de segurança: várias térmicas não imprimem
    # perfeitamente até a borda extrema do raster.
    border = 12
    draw.rectangle((border, 4, width - border - 1, height - 5), outline=0, width=3)
    fold_y = 4 + ((height - 5) - 4) // 2
    draw.line((border, fold_y, width - border - 1, fold_y), fill=0, width=3)

    y = 20

    if institution:
        for line in _wrap_pil(draw, institution, regular_22, inner_w)[:2]:
            y += _draw_center_pil(draw, line, regular_22, cx, y) + 4

    if election:
        for line in _wrap_pil(draw, election, bold_28, inner_w)[:2]:
            y += _draw_center_pil(draw, line, bold_28, cx, y) + 4

    y += 4
    draw.line((inner_left, y, inner_right, y), fill=0, width=2)
    y += 10

    if number is not None:
        y += _draw_center_pil(draw, "CHAPA", label_24, cx, y) + 2
        y += _draw_center_pil(draw, f"{int(number):02d}", number_font, cx, y) + 2

    if slate:
        # Mantém o nome o maior possível sem perder palavras.
        chosen_font = None
        chosen_lines = []
        for size in [50, 46, 42, 38, 34, 30, 27, 24, 21, 18]:
            fnt = _pil_font(size, True)
            lines = _wrap_pil(draw, slate, fnt, inner_w)
            block_h = 0
            for line in lines:
                box = draw.textbbox((0, 0), line, font=fnt)
                block_h += (box[3] - box[1]) + 3
            if y + block_h <= fold_y - 14:
                chosen_font = fnt
                chosen_lines = lines
                break

        if chosen_font is None:
            chosen_font = _pil_font(16, True)
            chosen_lines = _wrap_pil(draw, slate, chosen_font, inner_w)

        for line in chosen_lines:
            y += _draw_center_pil(draw, line, chosen_font, cx, y) + 3

    # Instrução na metade inferior.
    if instruction:
        iy = fold_y + 34
        for line in _wrap_pil(draw, instruction, instruction_font, inner_w)[:2]:
            iy += _draw_center_pil(draw, line, instruction_font, cx, iy) + 4

    return b"\x1b@" + _escpos_raster_bytes(image) + _escpos_finish(job)




def _receipt_rule(draw, y: int, left: int = 18, right: int = 558, width: int = 2):
    draw.line((left, y, right, y), fill=0, width=width)


def _receipt_wrap_height(draw, text: str, font, max_width: int, x: int, y: int, gap: int = 4) -> int:
    lines = _wrap_pil(draw, text, font, max_width)
    yy = y
    for line in lines:
        box = draw.textbbox((0, 0), line, font=font)
        draw.text((x, yy - box[1]), line, font=font, fill=0)
        yy += (box[3] - box[1]) + gap
    return yy


def _receipt_center_rect(draw, text: str, font, x: int, y: int, w: int, h: int):
    box = draw.textbbox((0, 0), text, font=font)
    tw = box[2] - box[0]
    th = box[3] - box[1]
    draw.text((x + max(0, (w - tw) // 2), y + max(0, (h - th) // 2) - box[1]), text, font=font, fill=0)


def _receipt_section_title(draw, title: str, y: int, width: int = 576) -> int:
    _receipt_rule(draw, y - 7)
    _draw_center_pil(draw, title, _pil_font(24, True), width // 2, y)
    _receipt_rule(draw, y + 34, width=1)
    return y + 52


def _receipt_kv(draw, pairs: list[tuple[str, str]], y: int, label_x: int = 24, value_x: int = 220, value_font_size: int = 24) -> int:
    label_font = _pil_font(24, True)
    value_font = _pil_font(value_font_size, False)
    for label, value in pairs:
        draw.text((label_x, y), label, font=label_font, fill=0)
        draw.text((value_x, y), value, font=value_font, fill=0)
        y += 38
    return y


def _render_zero_receipt_image(paper: dict[str, Any]):
    width = 576
    image = Image.new("L", (width, 5200), 255)
    draw = ImageDraw.Draw(image)
    y = 18

    y += _draw_center_pil(draw, "ZERÉSIMA", _pil_font(42, True), width // 2, y) + 10
    y += _draw_center_pil(draw, str(paper.get("institution") or "").upper(), _pil_font(19, True), width // 2, y) + 6
    y += _draw_center_pil(draw, str(paper.get("election") or "").upper(), _pil_font(18, False), width // 2, y) + 12
    _receipt_rule(draw, y); y += 18

    issued_at = str(paper.get("issued_at") or "")
    if 'T' in issued_at and len(issued_at) >= 19:
        issued_at = issued_at[:19].replace('T', ' ')

    eleitores_txt = (f"{int(paper.get('registered_voters') or 0)} cadastrados" if paper.get('registered_voters') is not None else "Identificação nominal: desativada")
    y = _receipt_kv(draw, [
        ("ESTAÇÃO", str(paper.get("station_label") or "")),
        ("EMISSÃO", issued_at),
        ("VERSÃO", str(paper.get("version") or "")),
        ("ELEITORES", eleitores_txt),
    ], y, value_font_size=23)
    draw.text((24, y), f"ID: {paper.get('election_uuid') or '—'}", font=_pil_font(14, False), fill=0); y += 34

    y = _receipt_section_title(draw, "CHAPAS CADASTRADAS", y)
    for slate in paper.get('slates') or []:
        draw.text((24, y), f"CHAPA {int(slate.get('number', 0)):02d}", font=_pil_font(30, True), fill=0); y += 38
        y = _receipt_wrap_height(draw, str(slate.get('name') or ''), _pil_font(24, True), 528, 24, y, gap=3)
        for member in slate.get('members') or []:
            line = f"{member.get('role')}: {member.get('name')}"
            y = _receipt_wrap_height(draw, line, _pil_font(19, False), 528, 24, y, gap=2)
        draw.text((24, y), f"VOTOS: {int(slate.get('votes', 0)):03d}", font=_pil_font(36, True), fill=0); y += 46
        _receipt_rule(draw, y, 24, 552, 2); y += 16

    if paper.get('allow_blank'):
        draw.text((24, y), 'BRANCO', font=_pil_font(24, True), fill=0); y += 32
        draw.text((24, y), 'VOTOS: 000', font=_pil_font(36, True), fill=0); y += 50

    y = _receipt_section_title(draw, 'RESUMO DA ZERÉSIMA', y)
    header_font = _pil_font(18, True)
    draw.text((22, y), 'NOME DA CHAPA', font=header_font, fill=0)
    draw.text((424, y), 'NUM', font=header_font, fill=0)
    draw.text((493, y), 'VOTOS', font=header_font, fill=0)
    y += 30; _receipt_rule(draw, y, width=1); y += 12
    name_font = _pil_font(22, True)
    num_font = _pil_font(36, True)
    votes_font = _pil_font(36, True)
    for slate in paper.get('slates') or []:
        lines = _wrap_pil(draw, str(slate.get('name') or ''), name_font, 376)
        yy = y
        for line in lines:
            box = draw.textbbox((0,0), line, font=name_font)
            draw.text((22, yy - box[1]), line, font=name_font, fill=0)
            yy += (box[3]-box[1]) + 6
        draw.text((420, y), f"{int(slate.get('number', 0)):02d}", font=num_font, fill=0)
        draw.text((498, y-2), f"{int(slate.get('votes', 0)):03d}", font=votes_font, fill=0)
        y = max(yy, y + 46) + 10
    if paper.get('allow_blank'):
        draw.text((22, y), 'BRANCO', font=name_font, fill=0)
        draw.text((420, y), '--', font=num_font, fill=0)
        draw.text((498, y-2), '000', font=votes_font, fill=0)
        y += 56

    _receipt_rule(draw, y); y += 16
    draw.rectangle((20, y, 556, y + 104), outline=0, width=2)
    _receipt_center_rect(draw, 'TOTAL DE VOTOS REGISTRADOS', _pil_font(23, True), 20, y + 8, 536, 30)
    _receipt_center_rect(draw, '000', _pil_font(50, True), 20, y + 43, 536, 52)
    y += 124

    y = _receipt_section_title(draw, 'INTEGRIDADE', y)
    draw.text((24, y), 'Hash da configuração:', font=_pil_font(20, True), fill=0); y += 31
    conf = str(paper.get('config_hash') or '—')
    for i in range(0, len(conf), 32):
        draw.text((24, y), conf[i:i+32], font=_pil_font(18, False), fill=0); y += 27
    y += 9
    draw.text((24, y), 'Hash da zerésima:', font=_pil_font(20, True), fill=0); y += 31
    hz = str(paper.get('zero_snapshot_hash') or '—')
    for i in range(0, len(hz), 32):
        draw.text((24, y), hz[i:i+32], font=_pil_font(18, False), fill=0); y += 27
    y += 13

    y = _receipt_section_title(draw, 'ASSINATURAS', y)
    for idx in range(1, 4):
        _receipt_rule(draw, y + 112, 60, 516, 1)
        draw.text((60, y + 122), f'Assinatura {idx}', font=_pil_font(21, True), fill=0)
        y += 166

    cropped = image.crop((0, 0, width, min(image.size[1], y + 20)))
    return cropped


def _render_result_receipt_image(paper: dict[str, Any]):
    width = 576
    image = Image.new('L', (width, 7000), 255)
    draw = ImageDraw.Draw(image)
    y = 18

    y += _draw_center_pil(draw, 'BOLETIM DE URNA', _pil_font(38, True), width // 2, y) + 12
    y += _draw_center_pil(draw, str(paper.get('institution') or '').upper(), _pil_font(19, True), width // 2, y) + 6
    y += _draw_center_pil(draw, str(paper.get('election') or '').upper(), _pil_font(18, False), width // 2, y) + 12
    _receipt_rule(draw, y); y += 18

    y = _receipt_kv(draw, [
        ('URNA', str(paper.get('urn_label') or '')),
        ('DATA', str(paper.get('date') or '')),
        ('ABERTURA', str(paper.get('opening') or '')),
        ('FECHAMENTO', str(paper.get('closing') or '')),
        ('VERSÃO', str(paper.get('version') or '')),
    ], y, value_font_size=23)

    y = _receipt_section_title(draw, 'MOVIMENTO DE ELEITORES', y)
    cells = [('APTOS', f"{int(paper.get('registered') or 0):03d}", 150, 20), ('COMPARECERAM', f"{int(paper.get('total') or 0):03d}", 206, 17), ('FALTOSOS', f"{int(paper.get('absent') or 0):03d}", 150, 20)]
    x = 25
    for label, value, cw, label_sz in cells:
        draw.rectangle((x, y, x + cw, y + 96), outline=0, width=2)
        _receipt_center_rect(draw, label, _pil_font(label_sz, True), x, y + 9, cw, 28)
        _receipt_center_rect(draw, value, _pil_font(40, True), x, y + 42, cw, 42)
        x += cw + 10
    y += 122

    y = _receipt_section_title(draw, 'DETALHAMENTO DAS CHAPAS', y)
    for slate in paper.get('slates') or []:
        draw.text((24, y), f"CHAPA {int(slate.get('number', 0)):02d}", font=_pil_font(30, True), fill=0); y += 38
        y = _receipt_wrap_height(draw, str(slate.get('name') or ''), _pil_font(24, True), 528, 24, y, gap=3)
        for member in slate.get('members') or []:
            line = f"{member.get('role')}: {member.get('name')}"
            y = _receipt_wrap_height(draw, line, _pil_font(19, False), 528, 24, y, gap=2)
        draw.text((24, y), f"VOTOS: {int(slate.get('votes', 0)):03d}", font=_pil_font(36, True), fill=0); y += 46
        _receipt_rule(draw, y, 24, 552, 2); y += 16

    y = _receipt_section_title(draw, 'RESUMO DAS CHAPAS', y)
    header_font = _pil_font(18, True)
    draw.text((22, y), 'NOME DA CHAPA', font=header_font, fill=0)
    draw.text((424, y), 'NUM', font=header_font, fill=0)
    draw.text((493, y), 'VOTOS', font=header_font, fill=0)
    y += 30; _receipt_rule(draw, y, width=1); y += 12
    name_font = _pil_font(22, True)
    num_font = _pil_font(36, True)
    votes_font = _pil_font(36, True)
    for slate in paper.get('slates') or []:
        lines = _wrap_pil(draw, str(slate.get('name') or ''), name_font, 376)
        yy = y
        for line in lines:
            box = draw.textbbox((0,0), line, font=name_font)
            draw.text((22, yy - box[1]), line, font=name_font, fill=0)
            yy += (box[3]-box[1]) + 6
        draw.text((420, y), f"{int(slate.get('number', 0)):02d}", font=num_font, fill=0)
        draw.text((498, y-2), f"{int(slate.get('votes', 0)):03d}", font=votes_font, fill=0)
        y = max(yy, y + 46) + 10

    y = _receipt_section_title(draw, 'RESULTADO EM DESTAQUE', y + 8)
    for slate in paper.get('slates') or []:
        lines = _wrap_pil(draw, str(slate.get('name') or ''), _pil_font(24, True), 330)
        box_h = max(110, 66 + len(lines) * 30)
        draw.rectangle((20, y, 556, y + box_h), outline=0, width=2)
        draw.text((30, y + 10), f"CHAPA {int(slate.get('number', 0)):02d}", font=_pil_font(18, True), fill=0)
        yy = y + 40
        for line in lines:
            box = draw.textbbox((0,0), line, font=_pil_font(24, True))
            draw.text((30, yy - box[1]), line, font=_pil_font(24, True), fill=0)
            yy += (box[3]-box[1]) + 6
        _receipt_center_rect(draw, f"{int(slate.get('votes', 0)):03d}", _pil_font(48, True), 386, y + 16, 155, 46)
        _receipt_center_rect(draw, 'VOTOS', _pil_font(18, True), 386, y + 76, 155, 20)
        y += box_h + 10

    _receipt_rule(draw, y); y += 16
    if paper.get('allow_blank'):
        draw.text((24, y), f"BRANCOS: {int(paper.get('blank_count') or 0):03d}", font=_pil_font(28, True), fill=0)
        y += 44
    draw.text((24, y), f"TOTAL APURADO: {int(paper.get('total') or 0):03d}", font=_pil_font(28, True), fill=0)
    y += 60

    y = _receipt_section_title(draw, 'INTEGRIDADE E AUDITORIA', y)
    for label, value in [('ID da eleição:', str(paper.get('election_uuid') or '—')), ('Hash final dos votos:', str(paper.get('ballot_head_hash') or '—')), ('Hash da configuração:', str(paper.get('config_hash') or '—')), ('Hash da zerésima:', str(paper.get('zero_snapshot_hash') or '—'))]:
        draw.text((24, y), label, font=_pil_font(20, True), fill=0); y += 31
        for i in range(0, len(value), 32):
            draw.text((24, y), value[i:i+32], font=_pil_font(18, False), fill=0); y += 27
        y += 10

    y = _receipt_section_title(draw, 'ASSINATURAS', y)
    for idx in range(1, 4):
        _receipt_rule(draw, y + 112, 60, 516, 1)
        draw.text((60, y + 122), f'Assinatura {idx}', font=_pil_font(21, True), fill=0)
        y += 166

    cropped = image.crop((0, 0, width, min(image.size[1], y + 20)))
    return cropped


def _escpos_receipt(job: PrintJob) -> bytes:
    if Image is None or ImageDraw is None or ImageFont is None:
        raise RuntimeError("Pillow não está disponível. Execute novamente 'Preparar agente'.")
    if job.layout == 'zero_receipt' and job.paper:
        image = _render_zero_receipt_image(job.paper)
    elif job.layout == 'result_receipt' and job.paper:
        image = _render_result_receipt_image(job.paper)
    else:
        raise RuntimeError('Layout de recibo não suportado.')

    return b"\x1b@" + _escpos_raster_bytes(image) + _escpos_finish(job)


def _escpos_bytes(job: PrintJob | str, cut: bool = True, layout: str = "text", paper: dict[str, Any] | None = None) -> bytes:
    # Keep the older helper signature for local diagnostics/tests while the
    # application itself passes a PrintJob object.
    if not isinstance(job, PrintJob):
        job = PrintJob(printer="TEST", text=str(job), cut=cut, layout=layout, paper=paper, mode="escpos", paper_width_mm=80)
    if job.layout == "ballot" and job.paper:
        return _escpos_ballot(job)
    if job.layout in {"zero_receipt", "result_receipt"} and job.paper:
        return _escpos_receipt(job)

    body = job.text.replace("\r\n", "\n").replace("\r", "\n")
    return b"\x1b@\x1bt\x02\x1ba\x00" + _enc(body) + b"\n" + _escpos_finish(job)


def _escpos_print(job: PrintJob):
    _require_windows()
    h = win32print.OpenPrinter(job.printer)
    try:
        for _ in range(max(1, min(job.copies, 20))):
            win32print.StartDocPrinter(h, 1, (job.title, None, "RAW"))
            try:
                win32print.StartPagePrinter(h)
                win32print.WritePrinter(h, _escpos_bytes(job))
                win32print.EndPagePrinter(h)
            finally:
                win32print.EndDocPrinter(h)
    finally:
        win32print.ClosePrinter(h)


def _wrap_line(dc, text: str, max_width: int) -> list[str]:
    """Quebra texto por palavras e também palavras excepcionalmente longas."""
    if not text:
        return [""]
    words = " ".join(text.split()).split(" ")
    lines: list[str] = []
    line = ""

    def split_word(word: str) -> list[str]:
        parts: list[str] = []
        piece = ""
        for ch in word:
            candidate = piece + ch
            if piece and dc.GetTextExtent(candidate)[0] > max_width:
                parts.append(piece)
                piece = ch
            else:
                piece = candidate
        if piece:
            parts.append(piece)
        return parts or [word]

    for word in words:
        if dc.GetTextExtent(word)[0] > max_width:
            if line:
                lines.append(line)
                line = ""
            pieces = split_word(word)
            lines.extend(pieces[:-1])
            line = pieces[-1]
            continue

        candidate = word if not line else line + " " + word
        if dc.GetTextExtent(candidate)[0] <= max_width:
            line = candidate
        else:
            if line:
                lines.append(line)
            line = word

    if line:
        lines.append(line)
    return lines or [""]


def _font(dpi_y: int, points: float, weight: int = 400):
    # A cédula e os textos produzidos pelo agente usam a fonte oficial do projeto.
    _atkinson_font_paths()
    return win32ui.CreateFont({
        "name": "Atkinson Hyperlegible",
        "height": -max(12, int(points * dpi_y / 72)),
        "weight": weight,
    })

def _mono_font(dpi_y: int, points: float = 9.2, weight: int = 400):
    """Fonte monoespaçada para relatórios e BOs.

    A cédula física continua usando Atkinson Hyperlegible. O BO textual usa
    Consolas para garantir que nome / número / votos fiquem em colunas reais
    também quando impresso pelo driver do Windows.
    """
    return win32ui.CreateFont({
        "name": "Consolas",
        "height": -max(12, int(points * dpi_y / 72)),
        "weight": weight,
    })



def _draw_centered(dc, text: str, fnt, left: int, right: int, y: int) -> int:
    old = dc.SelectObject(fnt)
    try:
        w, h = dc.GetTextExtent(text)
        dc.TextOut(max(left, left + (right - left - w) // 2), y, text)
        return h
    finally:
        dc.SelectObject(old)


def _draw_line(dc, x1: int, y1: int, x2: int, y2: int):
    dc.MoveTo((x1, y1))
    dc.LineTo((x2, y2))


def _draw_outline(dc, left: int, top: int, right: int, bottom: int):
    """Contorno sem falhas nos cantos.

    O GDI LineTo não pinta o último ponto da linha. As linhas abaixo se
    sobrepõem 1 pixel nos cantos para impedir os pequenos cortes/gaps que
    apareceram na impressão física.
    """
    _draw_line(dc, left, top, right + 1, top)
    _draw_line(dc, right, top, right, bottom + 1)
    _draw_line(dc, right, bottom, left - 1, bottom)
    _draw_line(dc, left, bottom, left, top - 1)


def _draw_ballot_frame(dc, left: int, top: int, right: int, bottom: int, fold_y: int, mmx: float, mmy: float):
    """Desenha as duas metades com uma caneta levemente mais espessa.

    Os limites ficam completamente dentro da área imprimível e os cantos
    recebem sobreposição. Isso evita laterais/parte inferior visualmente
    "cortadas" em drivers de jato de tinta e térmicos.
    """
    pen_width = max(1, int(0.30 * min(mmx, mmy)))
    pen = win32ui.CreatePen(win32con.PS_SOLID, pen_width, 0x000000)
    old_pen = dc.SelectObject(pen)
    try:
        # Mantém o quadro alguns pixels para dentro, inclusive a borda inferior.
        l = left + pen_width
        r = right - pen_width - 1
        t = top + pen_width
        b = bottom - pen_width - 1
        # divisão geométrica exata do quadro efetivamente desenhado
        f = t + (b - t) // 2
        _draw_outline(dc, l, t, r, b)
        _draw_line(dc, l, f, r + 1, f)
        return l, t, r, b, f
    finally:
        dc.SelectObject(old_pen)



def _windows_ballot_page(dc, job: PrintJob, printable_w: int, printable_h: int, dpi_x: int, dpi_y: int):
    """Cédula para A4/Carta ou térmica via driver, com duas metades iguais."""
    paper = job.paper or {}
    mmx = dpi_x / 25.4
    mmy = dpi_y / 25.4
    printable_mm = printable_w / mmx if mmx else 0
    sheet_printer = printable_mm >= 120

    if sheet_printer:
        ballot_w_mm = 80.0
        ballot_h_mm = 100.0
        top_mm = 10.0
    else:
        ballot_w_mm = max(50.0, min(72.0, printable_mm - 2.0 if printable_mm else 72.0))
        ballot_h_mm = ballot_w_mm * 1.25
        top_mm = 2.0

    target_w = min(printable_w - 8, int(ballot_w_mm * mmx))
    target_h = min(printable_h - int(top_mm * mmy) - 4, int(ballot_h_mm * mmy))

    left = max(4, (printable_w - target_w) // 2)
    right = min(printable_w - 4, left + target_w)
    top = max(4, int(top_mm * mmy))
    bottom = min(printable_h - 4, top + target_h)

    # Divisão exatamente ao meio.
    fold_y = top + (bottom - top) // 2

    institution = str(paper.get("institution") or "").strip()
    election = str(paper.get("election") or "").strip()
    number = paper.get("number")
    slate = str(paper.get("slate") or "").strip()
    instruction = str(paper.get("instruction") or "Dobre e coloque na urna.").strip()

    try:
        dc.SetTextColor(0x000000)
        dc.SetBkMode(win32con.TRANSPARENT)
    except Exception:
        pass

    normal = _font(dpi_y, 8.5, 500)
    title_font = _font(dpi_y, 10.5, 800)
    chapa_label_font = _font(dpi_y, 8.5, 550)
    number_font = _font(dpi_y, 36, 900)
    instruction_font = _font(dpi_y, 10.0, 800)

    left, top, right, bottom, fold_y = _draw_ballot_frame(
        dc, left, top, right, bottom, fold_y, mmx, mmy
    )

    pad_x = int(4.5 * mmx)
    inner_left = left + pad_x
    inner_right = right - pad_x
    inner_w = inner_right - inner_left

    # Metade superior.
    y = top + int(3.0 * mmy)

    if institution:
        old = dc.SelectObject(normal)
        try:
            for line in _wrap_line(dc, institution.upper(), inner_w)[:2]:
                y += _draw_centered(dc, line, normal, inner_left, inner_right, y) + int(0.35 * mmy)
        finally:
            dc.SelectObject(old)

    if election:
        old = dc.SelectObject(title_font)
        try:
            for line in _wrap_line(dc, election.upper(), inner_w)[:2]:
                y += _draw_centered(dc, line, title_font, inner_left, inner_right, y) + int(0.35 * mmy)
        finally:
            dc.SelectObject(old)

    y += int(0.8 * mmy)
    _draw_line(dc, inner_left, y, inner_right, y)
    y += int(1.4 * mmy)

    if number is not None:
        y += _draw_centered(dc, "CHAPA", chapa_label_font, inner_left, inner_right, y) + int(0.2 * mmy)
        y += _draw_centered(dc, f"{int(number):02d}", number_font, inner_left, inner_right, y) + int(0.2 * mmy)

    if slate:
        max_name_bottom = fold_y - int(1.5 * mmy)
        chosen_font = None
        chosen_lines: list[str] = []
        gap = int(0.15 * mmy)

        # Nunca elimina palavras do nome. Começa grande e reduz gradualmente
        # até que TODAS as linhas caibam na metade superior.
        for size in [18.0, 17.0, 16.0, 15.0, 14.0, 13.0, 12.0, 11.0, 10.0, 9.0, 8.0]:
            fnt = _font(dpi_y, size, 850)
            old = dc.SelectObject(fnt)
            try:
                lines = _wrap_line(dc, slate.upper(), inner_w)
                heights = [dc.GetTextExtent(line)[1] for line in lines] or [0]
                block_h = sum(heights) + max(0, len(lines)-1) * gap
                if y + block_h <= max_name_bottom:
                    chosen_font = fnt
                    chosen_lines = lines
                    break
            finally:
                dc.SelectObject(old)

        # Nome de chapa é limitado pelo sistema; este fallback é apenas defensivo.
        if chosen_font is None:
            chosen_font = _font(dpi_y, 7.0, 800)
            old = dc.SelectObject(chosen_font)
            try:
                chosen_lines = _wrap_line(dc, slate.upper(), inner_w)
            finally:
                dc.SelectObject(old)

        old = dc.SelectObject(chosen_font)
        try:
            for line in chosen_lines:
                y += _draw_centered(dc, line, chosen_font, inner_left, inner_right, y) + gap
        finally:
            dc.SelectObject(old)

    # Metade inferior: somente a instrução pedida, abaixo da linha central.
    if instruction:
        instr_y = fold_y + int(4.0 * mmy)
        old = dc.SelectObject(instruction_font)
        try:
            for line in _wrap_line(dc, instruction.upper(), inner_w)[:2]:
                instr_y += _draw_centered(dc, line, instruction_font, inner_left, inner_right, instr_y) + int(0.4 * mmy)
        finally:
            dc.SelectObject(old)

    return bottom


def _windows_print(job: PrintJob):
    """Print via the normal Windows driver (GDI)."""
    _require_windows()
    for _ in range(max(1, min(job.copies, 20))):
        dc = win32ui.CreateDC()
        try:
            dc.CreatePrinterDC(job.printer)
            dpi_x = max(96, dc.GetDeviceCaps(win32con.LOGPIXELSX))
            dpi_y = max(96, dc.GetDeviceCaps(win32con.LOGPIXELSY))
            printable_w = dc.GetDeviceCaps(win32con.HORZRES)
            printable_h = dc.GetDeviceCaps(win32con.VERTRES)
            mmx = dpi_x / 25.4
            mmy = dpi_y / 25.4
            # Designed around 80 mm receipt paper, while still usable on A4 test printers.
            if job.paper_width_mm > 0:
                requested_mm = max(58, min(job.paper_width_mm, 210))
                useful_mm = 72 if 79 <= requested_mm <= 81 else requested_mm
                max_paper_px = int(useful_mm * mmx)
                content_w = min(printable_w, max_paper_px)
            else:
                content_w = printable_w
            margin_x = max(4, (printable_w - content_w) // 2)
            right = min(printable_w - 4, margin_x + content_w)
            max_width = max(100, right - margin_x)
            margin_y = max(4, int(3 * mmy))
            fnt = _mono_font(dpi_y, 9.2, 400)
            old_font = dc.SelectObject(fnt)
            dc.StartDoc(job.title)
            dc.StartPage()
            try:
                if job.layout == "ballot" and job.paper:
                    content_bottom = _windows_ballot_page(dc, job, printable_w, printable_h, dpi_x, dpi_y)
                else:
                    y = margin_y
                    line_height = max(15, int(4.2 * mmy))
                    for paragraph in job.text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
                        for line in _wrap_line(dc, paragraph, max_width):
                            if y + line_height >= printable_h - margin_y:
                                dc.EndPage(); dc.StartPage(); y = margin_y
                            dc.TextOut(margin_x, y, line)
                            y += line_height
                    content_bottom = y

                # Alguns drivers de térmica calculam o fim do documento pelo
                # último comando GDI. Um espaço no ponto final força o driver a
                # manter a margem configurada sem deixar marca no papel.
                feed_bottom = content_bottom + int(_normalized_cut_feed_mm(job.cut_feed_mm) * mmy)
                safe_bottom = min(feed_bottom, printable_h - margin_y - 1)
                if safe_bottom > content_bottom:
                    dc.TextOut(margin_x, safe_bottom, " ")
                dc.EndPage()
                dc.EndDoc()
            finally:
                dc.SelectObject(old_font)
        finally:
            try:
                dc.DeleteDC()
            except Exception:
                pass


def _print(job: PrintJob):
    mode = (job.mode or "windows").lower()
    if mode == "escpos":
        return _escpos_print(job)
    return _windows_print(job)


@app.get("/health")
def health():
    return {
        "ok": True,
        "windows": os.name == "nt",
        "pywin32": win32print is not None,
        "version": "2.2.1",
        "modes": ["windows", "escpos"],
        "paper_width_mm": "A4/Carta: cédula 80x100 mm; térmica 80 mm: até 72 mm úteis",
        "escpos_cut": "partial",
        "cut_feed_mm": {"default": DEFAULT_CUT_FEED_MM, "min": MIN_CUT_FEED_MM, "max": MAX_CUT_FEED_MM},
        "ballot_layout": "Atkinson Hyperlegible; equal halves; instruction below fold; automatic wrapping",
        "receipt_layouts": ["zero_receipt", "result_receipt"],
        "escpos_codepage": "raster image",
        "font": "Atkinson Hyperlegible",
        "report_font": "Consolas",
        "atkinson_installed": _atkinson_installed(),
    }


def _device_setup() -> dict[str, Any]:
    path = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "UrnaEscolar" / "device_setup.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


@app.get("/device-config")
def device_config():
    data = _device_setup()
    return {
        "ok": True,
        "version": "2.2.1",
        "role": data.get("role", ""),
        "printer_name": data.get("printer_name", ""),
        "printer_mode": data.get("printer_mode", "escpos"),
        "server_url": data.get("server_url", ""),
        "urn_code": data.get("urn_code", "U01"),
    }


@app.get("/printers")
def printers():
    _require_windows()
    flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
    names = sorted({p[2] for p in win32print.EnumPrinters(flags)})
    default = None
    try:
        default = win32print.GetDefaultPrinter()
    except Exception:
        pass
    return {"printers": names, "default": default, "recommended_mode": "escpos", "thermal_80mm": {"paper_mm": 80, "printable_mm": 72, "cut": "partial"}}


@app.post("/print")
def print_job(job: PrintJob):
    global _last_failed_job
    with _lock:
        try:
            _print(job)
            _last_failed_job = None
            return {"ok": True, "mode": job.mode, "paper_width_mm": job.paper_width_mm}
        except Exception as exc:
            _last_failed_job = job.model_dump()
            raise HTTPException(500, f"Falha de impressão: {exc}")


@app.post("/reprint-last")
def reprint_last():
    global _last_failed_job
    with _lock:
        if not _last_failed_job:
            raise HTTPException(409, "Não há impressão com falha disponível para reimpressão.")
        try:
            job = PrintJob(**_last_failed_job)
            _print(job)
            _last_failed_job = None
            return {"ok": True, "mode": job.mode}
        except Exception as exc:
            raise HTTPException(500, f"Falha de reimpressão: {exc}")
