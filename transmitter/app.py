"""Windows GUI: detects media; transmission always requires operator confirmation."""
import json
import os
import queue
import sys
import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from transmitter.client import transmit, verify_package, Election
from publication_core.media import removable_drives, find_packages
from publication_core.protocol import MAX_PACKAGE

LABELS = {'configuration': 'Configuração', 'zero': 'Zerésima', 'result': 'Boletim'}


class Transmitter:
    def __init__(self, root):
        self.root = root
        self.root.title('Transmissor Eleitoral — Urna Escolar')
        self.root.geometry('980x720')
        self.folder = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'UrnaEscolarTransmissor'
        self.folder.mkdir(parents=True, exist_ok=True)
        self.events = queue.Queue()
        self.busy = False
        self.packages = {}
        self.seen_drives = None
        panel = ttk.Frame(root, padding=22)
        panel.pack(fill='both', expand=True)
        ttk.Label(panel, text='Transmissor Eleitoral', font=('Segoe UI', 22, 'bold')).pack(anchor='w')
        ttk.Label(panel, text='Confira os pacotes do pendrive. O envio só acontece após sua confirmação.').pack(anchor='w', pady=(0, 15))
        self.fields = {}
        for name, label in [('url', 'Endereço HTTPS do portal'), ('election', 'Identificador da eleição'), ('fingerprint', 'Impressão digital confiável da chave (SHA-256)'), ('token', 'Credencial de transmissão — fornecida pelo responsável pelo portal')]:
            ttk.Label(panel, text=label).pack(anchor='w')
            self.fields[name] = tk.StringVar()
            ttk.Entry(panel, textvariable=self.fields[name], show='●' if name == 'token' else '').pack(fill='x', pady=(2, 8))
        settings = self.folder / 'settings.json'
        if settings.exists():
            try:
                values = json.loads(settings.read_text('utf-8'))
                for name in ('url', 'election', 'fingerprint'):
                    self.fields[name].set(values.get(name, ''))
            except (ValueError, OSError):
                pass
        self.list = ttk.Treeview(panel, columns=('type', 'election', 'urn', 'revision'), show='headings', selectmode='extended', height=7)
        for key, text in [('type', 'Documento'), ('election', 'Eleição'), ('urn', 'Urna'), ('revision', 'Revisão')]:
            self.list.heading(key, text=text)
        self.list.pack(fill='both', expand=True, pady=10)
        buttons = ttk.Frame(panel)
        buttons.pack(fill='x')
        ttk.Button(buttons, text='Atualizar pendrives', command=self.scan).pack(side='left', padx=3)
        ttk.Button(buttons, text='Abrir pacote', command=self.choose).pack(side='left', padx=3)
        ttk.Button(buttons, text='Verificar selecionado', command=self.verify).pack(side='left', padx=3)
        self.send_button = ttk.Button(buttons, text='Transmitir selecionados', command=self.send)
        self.send_button.pack(side='right')
        self.status = tk.StringVar(value='Insira uma mídia USB ou abra um pacote para verificar sem internet.')
        ttk.Label(panel, textvariable=self.status, wraplength=900).pack(fill='x', pady=15)
        ttk.Button(panel, text='Abrir comprovantes', command=lambda: os.startfile(str(self.folder))).pack(anchor='w')
        self.root.after(300, self.poll)

    def add(self, paths):
        errors = 0
        for path in paths:
            try:
                if path.stat().st_size > MAX_PACKAGE:
                    raise ValueError('Pacote excessivo')
                raw = path.read_bytes()
                p = verify_package(raw)
                doc = p['document']
                # Distinct bytes with the same ID must not silently replace a selection.
                item = p['package_hash']
                if item in self.packages:
                    continue
                self.packages[item] = (raw, p)
                urn = next((u['code'] for u in doc['election']['urns'] if u['id'] == doc['urn_id']), 'Todas')
                self.list.insert('', 'end', iid=item, values=(LABELS[doc['kind']], doc['election']['name'], urn, doc['revision']))
            except (OSError, ValueError):
                errors += 1
        self.status.set(f'{len(self.packages)} pacote(s) com assinatura íntegra. {errors} arquivo(s) rejeitado(s). Confirme a chave com a comissão antes de transmitir.')

    def scan(self):
        if not self.busy:
            self.add(find_packages())

    def choose(self):
        if not self.busy:
            self.add([Path(p) for p in filedialog.askopenfilenames(filetypes=[('Pacote eleitoral', '*.uepkg')])])

    def verify(self):
        items = self.list.selection()
        if not items:
            return messagebox.showinfo('Verificação', 'Selecione um pacote.')
        try:
            fp = self.fields['fingerprint'].get().strip().lower()
            if not fp:
                raise ValueError('Informe a impressão digital obtida da comissão por outro meio.')
            raw, _ = self.packages[items[0]]
            p = verify_package(raw, fp, self.fields['election'].get().strip() or None)
            window = tk.Toplevel(self.root)
            window.title('Documento verificado — compare com o papel')
            text = tk.Text(window, width=95, height=30, wrap='word')
            text.pack(fill='both', expand=True)
            text.insert('end', 'Assinatura e arquivos conferidos com a chave informada.\n\n' + json.dumps(p['document'], ensure_ascii=False, indent=2))
            text.configure(state='disabled')
        except ValueError as exc:
            messagebox.showerror('Não verificado', str(exc))

    def send(self):
        if self.busy:
            return
        selected = [self.packages[i] for i in self.list.selection()]
        if not selected:
            return messagebox.showinfo('Transmissão', 'Selecione os pacotes a transmitir.')
        values = {name: field.get().strip() for name, field in self.fields.items()}
        values['fingerprint'] = values['fingerprint'].lower()
        try:
            if not all(values.values()):
                raise ValueError('Preencha todos os campos, usando as referências fornecidas pela comissão e pelo responsável pelo portal.')
            values['url']=Election.url(values['url'])
            for raw, _ in selected:
                p = verify_package(raw, values['fingerprint'], values['election'])
                if p['document']['election']['public_url'] != values['url'].rstrip('/'):
                    raise ValueError('Endereço informado diferente do portal lacrado.')
        except ValueError as exc:
            return messagebox.showerror('Transmissão bloqueada', str(exc))
        selected.sort(key=lambda pair: ({'configuration': 0, 'zero': 1, 'result': 2}[pair[1]['document']['kind']], pair[1]['document']['revision']))
        summary = '\n'.join(f"{LABELS[p['document']['kind']]} · {p['document']['id']} · revisão {p['document']['revision']}" for _, p in selected)
        if not messagebox.askyesno('Confirmar publicação', f"Enviar {len(selected)} pacote(s) para {values['url']}?\n\nEleição: {values['election']}\n\n{summary}\n\nOs documentos serão públicos. Confirmar?"):
            return
        (self.folder / 'settings.json').write_text(json.dumps({k: v for k, v in values.items() if k != 'token'}), 'utf-8')
        self.busy = True
        self.send_button.configure(state='disabled')
        self.status.set('Transmitindo. Mantenha esta janela aberta…')
        def worker():
            receipts = []
            try:
                for raw, p in selected:
                    receipt = transmit(raw, values['url'], values['token'], values['fingerprint'], values['election'])
                    # Same package receives the same receipt on retry, even after lost responses.
                    (self.folder / (p['package_hash'] + '.receipt.json')).write_text(json.dumps(receipt, ensure_ascii=False, indent=2), 'utf-8')
                    receipts.append(receipt)
                self.events.put(('done', receipts))
            except Exception as exc:
                self.events.put(('error', f'{len(receipts)} confirmado(s). Falha: {exc}. Os pacotes foram preservados. Se a conexão caiu após o envio, repita: o portal não duplica o documento.'))
        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        while not self.events.empty():
            kind, value = self.events.get_nowait()
            self.busy = False
            self.send_button.configure(state='normal')
            if kind == 'done':
                self.status.set(f'{len(value)} transmissão(ões) confirmada(s). Comprovantes salvos em {self.folder}.')
                messagebox.showinfo('Comprovante de transmissão', '\n\n'.join(f"Protocolo: {r['protocol']}\nRecebido (UTC): {r['received_at']}\nDocumento: {r['document_id']}" for r in value))
            else:
                self.status.set(value)
        if not self.busy:
            drives = tuple(str(p) for p in removable_drives())
            if drives != self.seen_drives:
                self.seen_drives = drives
                self.scan()
        self.root.after(2000, self.poll)


def main():
    root = tk.Tk()
    Transmitter(root)
    root.mainloop()


if __name__ == '__main__':
    if '--self-test' in sys.argv:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from publication_core.schema import Document
        from PIL import Image
        key = Ed25519PrivateKey.generate()
        key.public_key().verify(key.sign(b'urn-test'), b'urn-test')
        root = tk.Tk(); root.withdraw(); root.update(); root.destroy()
    else:
        main()
