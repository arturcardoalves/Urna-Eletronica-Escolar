"""Fictional demo only: simulated input and print driver, no election data."""
from types import SimpleNamespace
import tkinter as tk
import time
import pytest
import zxingcpp
from demo import urna_demo as demo
from publication_core.protocol import verify_qr


@pytest.fixture(autouse=True)
def isolate_demo_font_fallback(monkeypatch):
    # The standalone demo may use Segoe UI. Restore the shared module after
    # each test so that this does not alter official-system tests in pytest.
    from print_agent import agent
    monkeypatch.setattr(agent, '_atkinson_font_paths', agent._atkinson_font_paths)


def test_demo_thermal_qrs_and_blank_slate_ballots():
    election=demo.Election()
    zero=election.document('zero_receipt')
    election.vote(10);election.vote(None)
    result=election.document('result_receipt')
    assert result['paper']['total']==2 and result['paper']['blank_count']==1
    agent=demo.renderer()
    for render,job in [(agent._render_zero_receipt_image,zero),(agent._render_result_receipt_image,result)]:
        image=render(job['paper'])
        decoded={r.text for r in zxingcpp.read_barcodes(image)}
        q=job['paper']['publication']
        assert q['consultation'] in decoded and q['verification'] in decoded
        assert demo.WARNING in q['consultation']
        assert verify_qr(q['verification'],q['fingerprint'])['trusted']
        assert 'workers.dev' not in q['verification']
    for choice in (None,10):
        job=election.document('ballot',choice)
        assert job['paper']['number']==choice
        assert demo.WARNING in job['paper']['institution']
        assert agent._escpos_ballot(agent.PrintJob(printer='SIMULADA',**job))
    with pytest.raises(ValueError):election.document('zero_receipt')


def test_demo_visual_keyboard_and_simulated_mouse_are_distinct():
    root=tk.Tk();root.withdraw()
    try:
        window=tk.Toplevel(root);window.withdraw()
        panel=demo.KeyboardTest(window)
        panel.press(SimpleNamespace(keysym='b',char='b'))
        assert 'BRANCO' in panel.last.get()
        panel.release(SimpleNamespace(keysym='b',char=''))
        rect=panel.keys['B'][0][0]
        assert panel.canvas.itemcget(rect,'fill')=='#9adeb4'
        panel.clicked('Return')
        assert panel.physical=={'B'} and panel.mouse=={'Return'}
        assert 'simulado' in panel.last.get()
        panel.press(SimpleNamespace(keysym='BackSpace',char=''))
        assert 'CORRIGE' in panel.last.get()
        panel.press(SimpleNamespace(keysym='KP_Enter',char=''))
        assert 'CONFIRMA' in panel.last.get()
        assert demo.keyboard_key('KP_End')=='KP_1'
        panel.clear();assert not panel.physical and not panel.mouse
    finally:root.destroy()


def test_demo_print_samples_never_increment_votes_and_keyboard_voting_works(monkeypatch):
    jobs=[]
    agent=demo.renderer()
    fake=SimpleNamespace(printers=lambda:{'printers':['SIMULADA']},PrintJob=agent.PrintJob,
                         _print=lambda job:jobs.append(job))
    monkeypatch.setattr(demo,'renderer',lambda:fake)
    monkeypatch.setattr(demo.Demo,'sound',lambda self:None)
    root=tk.Tk();root.withdraw()
    try:
        ui=demo.Demo(root);ui.mode.set('Teclado')
        for char in '10':ui.key(SimpleNamespace(char=char,keysym=char,widget=root))
        ui.key(SimpleNamespace(char='',keysym='Return',widget=root))
        ui.key(SimpleNamespace(char='b',keysym='b',widget=root))
        ui.key(SimpleNamespace(char='',keysym='Return',widget=root))
        assert ui.election.total==2 and ui.election.blank==1
        for choice in (None,10):
            ui.print_sample(choice)
            for _ in range(100):
                if not ui.events.empty():break
                time.sleep(.01)
            ui.drain()
            assert not ui.busy
        assert [job.paper['number'] for job in jobs]==[None,10]
        assert ui.election.total==2
    finally:root.destroy()
