"""2.4.0 regression: real raster, simulated Windows driver, isolated database."""
from types import SimpleNamespace
import pytest
from PIL import Image, ImageFont
from sqlalchemy import select
from print_agent import agent


@pytest.mark.parametrize('layout,render', [
    ('zero_receipt', agent._render_zero_receipt_image),
    ('result_receipt', agent._render_result_receipt_image),
])
def test_windows_prints_complete_graphic_receipt_instead_of_old_text(monkeypatch, layout, render):
    monkeypatch.setattr(agent, '_pil_font', lambda size, bold=False: ImageFont.load_default(size=size))
    paper = dict(institution='ESCOLA TESTE', election='ELEICAO FICTICIA', version='2.4.0',
                 total=7, registered=160, registered_voters=160, absent=153,
                 allow_blank=True, blank_count=1,
                 slates=[dict(number=10, name='CHAPA EXEMPLO', votes=6, members=[])])
    expected = render(paper).convert('RGB')
    pieces, events, positions = [], [], []

    class DC:
        def CreatePrinterDC(self, name): pass
        def GetDeviceCaps(self, key):
            return {agent.win32con.LOGPIXELSX:203, agent.win32con.LOGPIXELSY:203,
                    agent.win32con.HORZRES:576, agent.win32con.VERTRES:1500}[key]
        def SelectObject(self, obj): return obj
        def StartDoc(self, title): events.append('doc')
        def StartPage(self): events.append('page')
        def EndPage(self): events.append('end-page')
        def EndDoc(self): events.append('end-doc')
        def AbortDoc(self): events.append('abort')
        def DeleteDC(self): events.append('delete')
        def GetHandleOutput(self): return 1
        def TextOut(self, x, y, text):
            assert text == ' ', 'Old plain-text receipt was printed'
            positions.append(y)

    class Dib:
        def __init__(self, image): pieces.append(image.copy())
        def draw(self, handle, box):
            assert handle == 1 and box[3] < 1500 - 230

    monkeypatch.setattr(agent, '_require_windows', lambda: None)
    monkeypatch.setattr(agent, 'win32ui', SimpleNamespace(CreateDC=DC))
    monkeypatch.setattr(agent, '_mono_font', lambda *a: object())
    monkeypatch.setattr(agent.ImageWin, 'Dib', Dib)
    agent._windows_print(agent.PrintJob(printer='SIMULADA', layout=layout, paper=paper,
                                      text='FORMATO ANTIGO NAO DEVE APARECER', paper_width_mm=80))
    assert len(pieces) > 1
    rebuilt = Image.new('RGB', expected.size, 'white')
    y=0
    for piece in pieces:
        rebuilt.paste(piece, (0,y)); y+=piece.height
    assert y == expected.height and rebuilt.tobytes() == expected.tobytes()
    assert events.count('page') == events.count('end-page') == len(pieces)
    assert 'abort' not in events and 'end-doc' in events
    assert len(positions) == len(pieces)  # Feed margin on every driver page.


def test_receipt_page_boundaries_do_not_cut_ink():
    image=Image.new('L',(576,1200),255)
    for y in range(15,1200,40):
        image.paste(0,(10,y,500,y+25))
    slices=list(agent._receipt_page_slices(image,280))
    assert slices[0][0]==0 and slices[-1][1]==1200
    for (start,end), (next_start,_) in zip(slices,slices[1:]):
        assert end==next_start
        assert image.crop((0,end-1,576,end)).getextrema()==(255,255)


def test_offline_admin_and_delete_default(prepared):
    from app.db import SessionLocal
    from app.models import Election
    with SessionLocal() as db:
        assert db.scalar(select(Election)).keyboard_correct_key=='Delete'
    page=prepared.get('/admin').text
    assert '/admin/publication' not in page
    assert prepared.get('/admin/publication').status_code==404
    assert prepared.get('/api/local/publication').status_code==404


def test_delete_migration_runs_once_and_preserves_sealed_configuration(prepared):
    from app.db import engine, init_db
    with engine.begin() as c:
        c.exec_driver_sql("DELETE FROM app_migrations WHERE name='2.4.0-delete-key'")
        c.exec_driver_sql("UPDATE elections SET keyboard_correct_key='Backspace'")
    init_db()
    with engine.begin() as c:
        assert c.exec_driver_sql('SELECT keyboard_correct_key FROM elections').scalar()=='Delete'
        c.exec_driver_sql("UPDATE elections SET keyboard_correct_key='F8'")
    init_db()
    with engine.begin() as c:
        assert c.exec_driver_sql('SELECT keyboard_correct_key FROM elections').scalar()=='F8'
        c.exec_driver_sql("DELETE FROM app_migrations WHERE name='2.4.0-delete-key'")
        c.exec_driver_sql("UPDATE elections SET keyboard_correct_key='Backspace', state='SEALED'")
    init_db()
    with engine.begin() as c:
        assert c.exec_driver_sql('SELECT keyboard_correct_key FROM elections').scalar()=='Backspace'
