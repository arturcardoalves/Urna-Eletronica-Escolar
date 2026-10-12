"""Standalone fictitious voting demo. No server, database, or election credentials."""
from pathlib import Path
import sys
import os
import queue
import threading
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox

ROOT = Path(__file__).resolve().parents[1]
if not getattr(sys, 'frozen', False):
    sys.path.insert(0, str(ROOT / 'URNA_ESCOLAR_SOURCE/03_URNA'))

SLATES = {10: 'Chapa Horizonte', 20: 'Chapa Uniao', 30: 'Chapa Futuro'}
WARNING = 'TESTE FICTICIO - SEM VALIDADE ELEITORAL'


class Election:
    def __init__(self):
        self.votes = {number: 0 for number in SLATES}
        self.blank = 0

    @property
    def total(self):
        return sum(self.votes.values()) + self.blank

    def vote(self, choice):
        if choice is None:
            self.blank += 1
        elif choice in self.votes:
            self.votes[choice] += 1
        else:
            raise ValueError('Chapa invalida')

    def document(self, kind, choice=None):
        now = datetime.now()
        zero = kind == 'zero_receipt'
        paper = dict(institution=WARNING, election='Gremio - Escola Exemplo',
                     instruction='TESTE: DOBRE E DEPOSITE NA URNA DE DEMONSTRACAO',
                     station_label='URNA TESTE 01', urn_label='URNA TESTE 01', version='DEMO',
                     issued_at=now.strftime('%d/%m/%Y %H:%M'), date=now.strftime('%d/%m/%Y'),
                     opening='TESTE', closing='TESTE', election_uuid='DEMONSTRACAO',
                     config_hash='TESTE', zero_snapshot_hash='TESTE', ballot_head_hash='TESTE',
                     registered=100, registered_voters=100, total=0 if zero else self.total,
                     absent=max(0,100-self.total), allow_blank=True, blank_count=0 if zero else self.blank,
                     slates=[dict(number=n, name=name, votes=0 if zero else self.votes[n], members=[])
                             for n,name in SLATES.items()])
        if kind == 'ballot':
            if choice is not None and choice not in SLATES:
                raise ValueError('Chapa invalida')
            paper.update(number=choice, slate=SLATES.get(choice, 'BRANCO'))
            text=f'{WARNING}\nVOTO DE TESTE\n{choice or ""} {paper["slate"]}'
        else:
            if zero and self.total:
                raise ValueError('Zere os dados ficticios antes de emitir a zeresima.')
            title='ZERESIMA' if zero else 'BOLETIM'
            rows=[WARNING, title, paper['election'], paper['issued_at'], 'URNA TESTE 01', '']
            rows += [f'Chapa {s["number"]} - {s["name"]}: {s["votes"]}' for s in paper['slates']]
            rows += [f'Brancos: {paper["blank_count"]}', f'TOTAL: {paper["total"]}', '', WARNING]
            text='\n'.join(rows)
        return dict(layout=kind, paper=paper, text=text, title='URNA TESTE - '+kind,
                    copies=1, cut=True, paper_width_mm=80)


def renderer():
    from print_agent import agent
    # Only this demo process uses the Windows font fallback. No font is installed.
    if not agent._atkinson_installed():
        fonts=Path(os.environ.get('WINDIR', r'C:\Windows'))/'Fonts'
        agent._atkinson_font_paths=lambda: (str(fonts/'segoeui.ttf'), str(fonts/'segoeuib.ttf'))
    return agent


class Demo:
    def __init__(self, root):
        self.root=root
        self.election=Election()
        self.choice=''
        self.busy=False
        self.last_job=None
        self.events=queue.Queue()
        root.title('Urna Escolar - TESTE FICTICIO')
        root.geometry('1050x760')
        root.minsize(840,680)
        self.mode=tk.StringVar(value='Mouse')
        self.printer=tk.StringVar()
        self.backend=tk.StringVar(value='windows')
        self.spacing=tk.StringVar(value='30')
        self.print_enabled=tk.BooleanVar(value=False)
        self.status=tk.StringVar(value='Escolha uma chapa ficticia para testar.')
        self.preview=tk.StringVar(value='Nenhum voto selecionado')
        self.counter=tk.StringVar(value='Votos ficticios: 0')
        self.buttons=[]
        ttk.Label(root,text=WARNING,foreground='#9a3412',font=('Segoe UI',16,'bold')).pack(pady=12)
        ttk.Label(root,text='Dados somente na memoria. Ao fechar, o teste e zerado.').pack()
        config=ttk.LabelFrame(root,text='Impressora de teste');config.pack(fill='x',padx=24,pady=12)
        ttk.Checkbutton(config,text='Imprimir cada voto',variable=self.print_enabled).grid(row=0,column=0,padx=8,pady=8)
        self.printers=ttk.Combobox(config,textvariable=self.printer,width=42,state='readonly')
        self.printers.grid(row=0,column=1,columnspan=2,padx=8)
        self.button(config,'Atualizar lista',self.refresh).grid(row=0,column=3,padx=8)
        ttk.Label(config,text='Modo').grid(row=1,column=0)
        ttk.Combobox(config,textvariable=self.backend,values=['windows','escpos'],state='readonly',width=15).grid(row=1,column=1)
        ttk.Label(config,text='Espaco antes do corte (10 a 80 mm)').grid(row=1,column=2)
        ttk.Spinbox(config,from_=10,to=80,textvariable=self.spacing,width=5).grid(row=1,column=3,pady=8)
        modes=ttk.Frame(root);modes.pack(pady=5)
        for mode in ['Mouse','Teclado']:
            ttk.Radiobutton(modes,text='Voto por '+mode.lower(),variable=self.mode,value=mode,command=self.clear).pack(side='left',padx=20)
        ttk.Label(root,text='Teclado: numero da chapa | Enter confirma | Backspace corrige | B branco',font=('Segoe UI',11)).pack(pady=5)
        self.cards=ttk.Frame(root);self.cards.pack(pady=10)
        for n,name in SLATES.items():
            self.button(self.cards,f'{n}\n{name}',lambda n=n:self.select(str(n))).pack(side='left',padx=8,ipadx=12,ipady=16)
        ttk.Label(root,textvariable=self.preview,font=('Segoe UI',23,'bold')).pack(pady=16)
        actions=ttk.Frame(root);actions.pack(pady=5)
        for label,func in [('BRANCO',lambda:self.select('BRANCO')),('CORRIGE',self.clear),('CONFIRMA',self.confirm)]:
            self.button(actions,label,func).pack(side='left',padx=10,ipady=12)
        ttk.Label(root,textvariable=self.status,wraplength=950,font=('Segoe UI',12),foreground='#166534').pack(pady=12)
        ttk.Label(root,textvariable=self.counter).pack()
        docs=ttk.Frame(root);docs.pack(pady=14)
        for label,func in [('Testar som',self.sound),('Imprimir zeresima',lambda:self.document('zero_receipt')),
                           ('Imprimir boletim',lambda:self.document('result_receipt')),
                           ('Reimprimir ultimo',self.reprint),('Zerar teste',self.reset)]:
            self.button(docs,label,func).pack(side='left',padx=4)
        ttk.Label(root,text='Windows: driver instalado (inclusive PDF). ESC/POS: termica compativel.\nSem Atkinson instalada, a demonstracao usa Segoe UI. Confira o papel antes de reimprimir.',justify='center').pack(pady=5)
        root.bind('<KeyPress>',self.key)
        root.protocol('WM_DELETE_WINDOW',self.close)
        self.refresh()
        root.after(100,self.drain)

    def button(self,parent,text,command):
        button=ttk.Button(parent,text=text,command=command)
        self.buttons.append(button)
        return button

    def refresh(self):
        try:
            names=renderer().printers()['printers']
            self.printers['values']=names
            if names and self.printer.get() not in names: self.printer.set(names[0])
        except Exception as exc: self.status.set('Impressoras indisponiveis: '+str(exc))

    def select(self,value):
        if self.busy:return
        self.choice=value
        self.preview.set('BRANCO' if value=='BRANCO' else f'{value} - {SLATES.get(int(value or 0), "Digite uma chapa valida")}')

    def clear(self):
        if self.busy:return
        self.choice='';self.preview.set('Nenhum voto selecionado')

    def key(self,event):
        if self.busy or self.mode.get()!='Teclado':return
        if isinstance(event.widget,(ttk.Entry,ttk.Spinbox,ttk.Combobox)):return
        if event.char.isdigit() and event.char:
            self.select((self.choice if self.choice.isdigit() else '')[-1:]+event.char)
        elif event.keysym in ('Return','KP_Enter'):self.confirm()
        elif event.keysym in ('BackSpace','Delete'):self.clear()
        elif event.char.lower()=='b':self.select('BRANCO')
        return 'break'

    def sound(self):
        def play():
            try:
                import ctypes
                asset=(Path(sys._MEIPASS)/'final.mp3' if getattr(sys,'frozen',False) else ROOT/'URNA_ESCOLAR_SOURCE/01_SERVIDOR_ADMIN/app/static/sounds/final.mp3')
                mci=ctypes.windll.winmm.mciSendStringW
                mci('close urna_demo_sound',None,0,None)
                if mci(f'open "{asset}" type mpegvideo alias urna_demo_sound',None,0,None):
                    import winsound
                    winsound.Beep(1040,180)
                else:mci('play urna_demo_sound from 0',None,0,None)
            except Exception as exc:self.events.put(('sound',str(exc)))
        threading.Thread(target=play,daemon=True).start()

    def settings(self):
        if not self.printer.get():raise ValueError('Selecione uma impressora.')
        spacing=int(self.spacing.get())
        if not 10<=spacing<=80:raise ValueError('Use entre 10 e 80 mm antes do corte.')
        return dict(printer=self.printer.get(),mode=self.backend.get(),cut_feed_mm=spacing)

    def confirm(self):
        if self.busy:return
        choice=None if self.choice=='BRANCO' else int(self.choice) if self.choice.isdigit() else -1
        if choice is not None and choice not in SLATES:
            self.status.set('Escolha uma chapa valida ou BRANCO.');return
        try: settings=self.settings() if self.print_enabled.get() else None
        except ValueError as exc:self.status.set(str(exc));return
        job=self.election.document('ballot',choice)
        self.election.vote(choice)
        self.counter.set(f'Votos ficticios: {self.election.total}')
        self.clear();self.preview.set('FIM / VOTOU');self.sound()
        if settings:self.send(job,settings)
        else:self.status.set('Voto ficticio registrado. Impressao desativada neste teste.')

    def document(self,kind):
        if self.busy:return
        try:job=self.election.document(kind);settings=self.settings()
        except ValueError as exc:self.status.set(str(exc));return
        self.send(job,settings)

    def send(self,job,settings):
        self.busy=True;self.last_job=job
        for button in self.buttons:button.state(['disabled'])
        self.status.set('Enviando para impressao…')
        def work():
            try:
                agent=renderer();agent._print(agent.PrintJob(**job,**settings))
                self.events.put(('print',None))
            except Exception as exc:self.events.put(('print',str(exc)))
        threading.Thread(target=work,daemon=True).start()

    def drain(self):
        while not self.events.empty():
            kind,error=self.events.get_nowait()
            if kind=='sound':self.status.set('Falha no som: '+error);continue
            self.busy=False
            for button in self.buttons:button.state(['!disabled'])
            self.status.set('Falha na impressao: '+error+' | O voto ficticio continua registrado.' if error else 'Enviado ao driver. Confira a impressao fisica. Pode testar outro voto.')
        self.root.after(100,self.drain)

    def reprint(self):
        if self.busy or not self.last_job:return
        if not messagebox.askyesno('Reimpressao de teste','Conferiu a fila e o papel? Reimprimir o ultimo documento sem adicionar voto?'):return
        try:self.send(self.last_job,self.settings())
        except ValueError as exc:self.status.set(str(exc))

    def reset(self):
        if self.busy:return
        if messagebox.askyesno('Zerar demonstracao','Apagar somente os votos ficticios desta janela?'):
            self.election=Election();self.last_job=None;self.clear();self.counter.set('Votos ficticios: 0');self.status.set('Teste zerado. Pode imprimir a zeresima.')

    def close(self):
        if self.busy:
            messagebox.showinfo('Impressao','Aguarde o envio ao driver terminar.');return
        self.root.destroy()


def self_test():
    e=Election()
    assert e.document('zero_receipt')['paper']['total']==0
    e.vote(10);e.vote(20);e.vote(None)
    assert e.total==3 and e.blank==1
    assert e.document('result_receipt')['paper']['total']==3
    assert e.document('ballot',10)['paper']['number']==10
    try:e.document('zero_receipt')
    except ValueError:pass
    else:raise AssertionError('Zeresima com votos')
    assert WARNING in e.document('ballot',10)['paper']['institution']
    # Exercise the bundled printer renderer without sending any physical job.
    agent=renderer()
    assert agent._escpos_ballot(agent.PrintJob(printer='TEST', **e.document('ballot',10)))
    for func,payload in [(agent._render_zero_receipt_image,Election().document('zero_receipt')), (agent._render_result_receipt_image,e.document('result_receipt'))]:
        image=func(payload['paper']);assert image.width>0 and image.height>0
    root=tk.Tk();root.withdraw();root.update();root.destroy()


if __name__=='__main__':
    if '--self-test' in sys.argv:
        self_test()
    else:
        window=tk.Tk();Demo(window);window.mainloop()
