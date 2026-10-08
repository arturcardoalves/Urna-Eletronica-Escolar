"""One visible application, two installation roles. No manual background tools."""
from __future__ import annotations

import hashlib
import json
import os
import queue
import secrets
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import lan_runtime
from native_runtime import (APP_HOME, MACHINE_HOME, VERSION, CREATE_FLAGS, Api, PrintJournal,
    acquire_instance, certificate_id, font_ready, install_certificate, list_printers,
    load_token, open_browser, printer_available, read_config, save_config, send_print,
    store_token, verification_code)

ROOT = Path(sys.executable).resolve().parent.parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent


class Desktop:
    def __init__(self, root, role):
        self.root, self.role = root, role
        self.config = read_config()
        # A saved choice is retained, but the physical test must be repeated
        # after restarting the application or changing its print settings.
        self.config.pop("tested", None)
        self.events = queue.Queue()
        self.stop = threading.Event()
        self.api = None
        self.server_proc = None
        self.start_lock = threading.Lock()
        self.pending = None
        self.browser = None
        self.ready = False
        self.busy = False
        self.journal = PrintJournal(APP_HOME / "print_journal.db") if role == "urna" else None
        self.root.title("Central da Eleição" if role == "central" else "Urna de Votação")
        self.root.geometry("900x720")
        self.root.minsize(790, 660)
        self.root.configure(bg="#f2f5f9")
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#f2f5f9")
        style.configure("TLabel", background="#f2f5f9", font=("Segoe UI", 11))
        style.configure("TButton", padding=(14, 10), font=("Segoe UI", 11))
        style.configure("Title.TLabel", font=("Segoe UI", 23, "bold"), foreground="#143355")
        style.configure("Subtitle.TLabel", foreground="#52657a")
        frame = ttk.Frame(root, padding=28); frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=self.root.title(), style="Title.TLabel").pack(anchor="w")
        ttk.Label(frame, text=f"URNA ELETRÔNICA ESCOLAR  •  {VERSION}", style="Subtitle.TLabel").pack(anchor="w", pady=(5, 22))
        self.rows = {}
        for key, initial in [("server", "Verificando servidor…"), ("network", "Verificando rede local…"), ("detail", "Preparando o sistema…"), ("font", "Verificando fonte…")]:
            var = tk.StringVar(value=initial)
            label = ttk.Label(frame, textvariable=var, wraplength=810)
            label.pack(anchor="w", pady=6)
            self.rows[key] = (var, label)
        self.devices = tk.StringVar()
        ttk.Label(frame, textvariable=self.devices, wraplength=810).pack(anchor="w", pady=8)
        buttons = ttk.Frame(frame); buttons.pack(fill="x", pady=(15, 10))
        if role == "central":
            ttk.Button(buttons, text="Abrir administração", command=lambda:self.browse("/admin", surface="admin")).pack(side="left", padx=(0,8))
            mesa_launch = ttk.LabelFrame(frame, text="Abrir Mesa Eleitoral", padding=10)
            mesa_launch.pack(fill="x", pady=(4, 8))
            ttk.Button(mesa_launch, text="Normal", command=lambda:self.browse("/mesario", "normal", "mesario")).pack(side="left", padx=(0,8))
            ttk.Button(mesa_launch, text="Tela cheia", command=lambda:self.browse("/mesario", "fullscreen", "mesario")).pack(side="left", padx=(0,8))
            ttk.Button(mesa_launch, text="Modo quiosque", command=lambda:self.browse("/mesario", "kiosk", "mesario")).pack(side="left")
            ttk.Button(frame, text="Conectar computador da urna", command=lambda:self.browse("/admin/pairing")).pack(anchor="w", pady=8)
            ttk.Button(frame, text="Iniciar servidor novamente", command=lambda:self.background(self.start_server)).pack(anchor="w", pady=8)
            ttk.Label(frame, text="A impressora fica no computador da urna.\nMantenha esta Central aberta durante a eleição; você pode minimizá-la.", wraplength=800).pack(anchor="w", pady=12)
            self.background(self.start_server)
        else:
            self.search_button = ttk.Button(buttons, text="Procurar Central", command=lambda:self.background(self.find_central))
            self.search_button.pack(side="left", padx=(0,8))
            self.confirm_button = ttk.Button(frame, text="Códigos iguais — concluir conexão", command=lambda:self.background(self.finish_pairing), state="disabled")
            self.confirm_button.pack(anchor="w", pady=6)
            urn_launch = ttk.LabelFrame(frame, text="Abrir Urna de Votação", padding=10)
            urn_launch.pack(fill="x", pady=(4, 8))
            self.start_buttons = []
            for label, mode in (("Normal", "normal"), ("Tela cheia", "fullscreen"), ("Modo quiosque", "kiosk")):
                button = ttk.Button(urn_launch, text=label, command=lambda selected=mode:self.background(lambda:self.start_urn(selected)), state="disabled")
                button.pack(side="left", padx=(0,8))
                self.start_buttons.append(button)
            printers = ttk.Frame(frame); printers.pack(fill="x", pady=(14, 5))
            ttk.Label(printers, text="Impressora USB deste computador").grid(row=0,column=0,columnspan=3,sticky="w",pady=5)
            self.printer_var = tk.StringVar(value=self.config.get("printer", ""))
            self.printer_box = ttk.Combobox(printers, textvariable=self.printer_var, state="readonly", width=42)
            self.printer_box.grid(row=1,column=0,sticky="w")
            self.printer_box.bind("<<ComboboxSelected>>", self.printer_changed)
            self.mode_var = tk.StringVar(value="Térmica ESC/POS" if self.config.get("mode") == "escpos" else "Driver Windows")
            mode_box = ttk.Combobox(printers, textvariable=self.mode_var, values=["Driver Windows", "Térmica ESC/POS"], state="readonly",width=22)
            mode_box.grid(row=1,column=1,padx=8)
            mode_box.bind("<<ComboboxSelected>>", self.printer_changed)
            ttk.Button(printers,text="Atualizar",command=lambda:self.background(self.refresh_printers)).grid(row=1,column=2)
            ttk.Button(frame,text="Imprimir teste e conferir",command=lambda:self.background(self.test_printer)).pack(anchor="w",pady=10)
            ttk.Label(frame,text="Instale o driver da impressora e a fonte Atkinson Hyperlegible (Regular e Bold).\nNo dia da eleição, confira o papel antes de abrir a votação.",wraplength=800).pack(anchor="w",pady=5)
            self.background(self.refresh_printers)
            if self.config.get("server_id"):
                self.background(self.connect_saved)
        self.notice = tk.StringVar(value="")
        ttk.Label(frame,textvariable=self.notice,wraplength=810,foreground="#934500").pack(anchor="w",pady=12)
        footer = ttk.Frame(frame); footer.pack(side="bottom",fill="x",pady=(10,0))
        ttk.Button(footer,text="Diagnóstico",command=self.diagnostics).pack(side="left")
        ttk.Button(footer,text="Minimizar",command=root.iconify).pack(side="right")
        root.protocol("WM_DELETE_WINDOW",self.close)
        self.root.after(100,self.pump)
        self.background(self.monitor)

    def emit(self, event, *args):
        self.events.put((event,args))

    def background(self, operation):
        def wrapped():
            try:
                operation()
            except Exception as exc:
                self.emit("notice",str(exc))
        threading.Thread(target=wrapped,daemon=True).start()

    def pump(self):
        try:
            while True:
                event,args=self.events.get_nowait()
                if event=="row":
                    key,text,ok=args
                    self.rows[key][0].set(("✓ " if ok else "● ")+text)
                    self.rows[key][1].configure(foreground="#176b46" if ok else "#9d4517")
                elif event=="notice": self.notice.set(args[0])
                elif event=="devices": self.devices.set(args[0])
                elif event=="ready":
                    self.ready=args[0]
                    if self.role=="urna":
                        for button in self.start_buttons:
                            button.configure(state="normal" if self.ready else "disabled")
                elif event=="pair":
                    self.devices.set(args[0]);self.confirm_button.configure(state="normal")
                elif event=="paired":
                    self.devices.set("Computador vinculado: "+self.config["urn_code"])
                    self.confirm_button.configure(state="disabled")
                elif event=="printers":
                    self.printer_box["values"]=args[0]
                    if not self.printer_var.get() and len(args[0])==1:
                        self.printer_var.set(args[0][0]);self.printer_changed()
                elif event=="test_confirm":
                    if messagebox.askyesno("Conferir o papel","O teste saiu completo e legível, com acentos e corte corretos?",parent=self.root):
                        self.config["tested"]=args[0]; save_config(self.config)
                        self.notice.set("Teste confirmado. A disponibilidade será verificada automaticamente.")
                    else:
                        self.config.pop("tested",None);save_config(self.config)
                        self.notice.set("Confira papel, driver e modo de impressão e repita o teste.")
                elif event=="closed": self.root.destroy();return
        except queue.Empty:
            pass
        self.root.after(100,self.pump)

    def start_server(self):
        with self.start_lock:
            self._start_server()

    def _start_server(self):
        ca_path=MACHINE_HOME/"Servidor/tls/urna_escolar_ca.crt"
        control_path=MACHINE_HOME/"Servidor/control.key"
        try:
            api=Api("https://127.0.0.1:8443",ca=ca_path.read_text("ascii"),control=control_path.read_text("ascii"))
            api.request("/api/local/status")
            self.api=api
            install_certificate(ca_path.read_text("ascii"))
            return
        except Exception:
            pass
        if self.server_proc and self.server_proc.poll() is None:
            self.emit("notice","O servidor está iniciando. Aguarde alguns segundos.");return
        exe=ROOT/"Servidor/UrnaEscolarServidor.exe"
        if not exe.exists():
            raise RuntimeError("Servidor não encontrado. Execute o instalador e escolha Central + Mesa.")
        self.emit("row","server","Iniciando servidor…",False)
        env=os.environ.copy();env["URNA_PARENT_PID"]=str(os.getpid())
        self.server_proc=subprocess.Popen([str(exe)],creationflags=CREATE_FLAGS,env=env)
        for _ in range(40):
            if self.stop.wait(0.5): return
            if self.server_proc.poll() is not None:
                raise RuntimeError("O servidor não iniciou. Abra Diagnóstico para consultar o registro; verifique se uma versão antiga está aberta.")
            try:
                api=Api("https://127.0.0.1:8443",ca=ca_path.read_text("ascii"),control=control_path.read_text("ascii"))
                api.request("/api/local/status")
                install_certificate(ca_path.read_text("ascii"))
                self.api=api
                self.emit("notice","Servidor iniciado. Abra a administração para preparar a eleição.")
                return
            except Exception:
                continue
        raise RuntimeError("Servidor ainda indisponível. Verifique data/hora e consulte Diagnóstico.")

    def browse(self, path, mode="normal", surface=None):
        def task():
            if not self.api:
                raise RuntimeError("Aguarde o servidor ficar ativo.")
            self.api.request("/api/local/status")
            self.browser = open_browser(self.api.url+path, mode=mode, surface=surface)
            mode_name = {"normal":"normal", "fullscreen":"em tela cheia", "kiosk":"em modo quiosque"}[mode]
            self.emit("notice", f"{('Mesa Eleitoral' if surface == 'mesario' else 'Administração')} aberta {mode_name}.")
        self.background(task)

    def refresh_printers(self):
        self.emit("printers",list_printers())

    def printer_changed(self,event=None):
        self.config.pop("tested", None)
        self.config["printer"]=self.printer_var.get()
        self.config["mode"]="escpos" if self.mode_var.get()=="Térmica ESC/POS" else "windows"
        save_config(self.config)
        self.ready=False
        for button in self.start_buttons:
            button.configure(state="disabled")

    def test_printer(self):
        if not font_ready(): raise RuntimeError("Instale Atkinson Hyperlegible Regular e Bold e tente novamente.")
        printer,mode=self.config.get("printer",""),self.config.get("mode","windows")
        if not printer: raise RuntimeError("Selecione a impressora deste computador.")
        if not printer_available(printer): raise RuntimeError("O Windows informa que a impressora está indisponível. Confira cabo, papel e driver.")
        payload={"text":"TESTE DE IMPRESSÃO", "title":"Teste Urna Escolar", "layout":"ballot", "paper":{"institution":"ESCOLA — TESTE", "election":"TESTE · NÃO É UM VOTO", "number":10, "slate":"CHAPA DE TESTE", "members":[], "instruction":"CONFIRA ACENTOS, LEGIBILIDADE E CORTE"}, "cut":True,"copies":1,"paper_width_mm":80}
        send_print(payload,printer,mode)
        self.emit("test_confirm",printer+"|"+mode)

    def connect_saved(self):
        token=load_token()
        self.api=Api(self.config["server_url"],self.config["ca_pem"],token)
        install_certificate(self.config["ca_pem"])

    def find_central(self):
        if self.config.get("server_id"):
            raise RuntimeError("Este computador já está vinculado. A reconexão é automática; confira se a mesma Central está aberta.")
        if self.busy:return
        self.busy=True
        try:
            self.emit("notice","Procurando a Central na rede local…")
            candidates=lan_runtime.discover()
            if not candidates: raise RuntimeError("Central não encontrada. Abra a Central, conecte os cabos ao mesmo roteador e confira o firewall em Diagnóstico.")
            if len({c["id"] for c in candidates}) != 1:
                raise RuntimeError("Há mais de uma Central na rede. Feche a Central que não será usada e procure novamente.")
            item=candidates[0]
            data=Api(item["url"],bootstrap=True).request("/api/deployment/identity")
            server_id=certificate_id(data["ca_pem"])
            if data.get("id")!=server_id: raise RuntimeError("Identidade da Central inválida.")
            if data.get("version")!=VERSION: raise RuntimeError("Instale a mesma versão 2.3.0 nos dois computadores.")
            api=Api(item["url"],data["ca_pem"])
            token=secrets.token_urlsafe(32)
            request=api.request("/api/deployment/pair",{"token_hash":hashlib.sha256(token.encode()).hexdigest(),"computer_name":socket.gethostname()})
            self.pending={"api":api,"token":token,"pair_id":request["id"],"identity":data}
            code=verification_code(server_id,token)
            self.emit("pair",f"Confira este código na Central: {code}\nNa Central, aprove somente se os códigos forem iguais.")
            self.emit("notice","Depois da aprovação na Central, clique Códigos iguais — concluir conexão.")
        finally:
            self.busy=False

    def finish_pairing(self):
        pending=self.pending
        if not pending:return
        data=pending["api"].request("/api/deployment/pair/"+pending["pair_id"])
        if not data["approved"]: raise RuntimeError("Aguarde a aprovação na tela Conectar computador da urna, na Central.")
        install_certificate(pending["identity"]["ca_pem"])
        store_token(pending["token"])
        self.config.update(server_url=pending["api"].url,server_id=pending["identity"]["id"],ca_pem=pending["identity"]["ca_pem"],urn_code=data["urn_code"])
        save_config(self.config)
        self.api=Api(self.config["server_url"],self.config["ca_pem"],pending["token"])
        self.pending=None
        self.emit("paired")
        self.emit("notice","Conexão concluída. Selecione a impressora e confira a impressão de teste.")

    def reconnect(self):
        for item in lan_runtime.discover():
            if item["id"]==self.config.get("server_id"):
                candidate=Api(item["url"],self.config["ca_pem"],load_token())
                # TLS validation with the ORIGINAL pinned CA occurs before any credential is sent.
                data=candidate.request("/api/deployment/identity")
                if data["id"]!=self.config["server_id"]: continue
                self.config["server_url"]=item["url"];save_config(self.config)
                changed=self.api is not None and self.api.url!=candidate.url
                self.api=candidate
                if changed:
                    self.emit("notice","O endereço da Central mudou. Feche a janela de votação com Alt+F4 e clique Iniciar urna novamente para retomar.")
                return

    def start_urn(self, mode="kiosk"):
        if not self.ready or not self.api: raise RuntimeError("Conclua a conexão e o teste da impressora antes de iniciar.")
        ticket=self.api.request("/api/native/browser-ticket",{})
        self.browser=open_browser(self.api.url+ticket["path"],mode=mode,surface="urna")
        mode_name={"normal":"normal", "fullscreen":"em tela cheia", "kiosk":"em modo quiosque"}[mode]
        exit_hint="F11 alterna a tela cheia; Alt+F4 fecha a votação." if mode=="fullscreen" else "Alt+F4 fecha a tela de votação e retorna a este aplicativo."
        self.emit("notice",f"Urna aberta {mode_name}. {exit_hint}")

    def monitor(self):
        failures=0
        while not self.stop.is_set():
            try:
                network=lan_runtime.interfaces()
                self.emit("row","network","Rede local: "+", ".join(i["ip"] for i in network) if network else "Sem rede local por cabo. Confira o roteador.",bool(network))
                fonts=font_ready()
                self.emit("row","font","Fonte Atkinson Hyperlegible instalada" if fonts else "Instale a fonte Atkinson Hyperlegible Regular e Bold",fonts)
                api=self.api
                if not api:
                    self.emit("row","server","Aguardando a Central" if self.role=="urna" else "Servidor ainda não está ativo",False)
                    self.emit("ready",False)
                elif self.role=="central":
                    status=api.request("/api/local/status")
                    self.emit("row","server","Servidor ativo — HTTPS verificado",True)
                    self.emit("row","detail","Banco de dados disponível • Eleição: "+{"CONFIG":"em preparação","SEALED":"lacrada","OPEN":"aberta","CLOSED":"encerrada"}.get(status["state"],status["state"]),True)
                    lines=[]
                    for urn in status["urns"]:
                        lines.append(urn["code"]+": "+("conectada" if urn["connected"] else "desconectada")+" • Impressora: "+("configurada e disponível no Windows" if urn["printer_ready"] else "verificar no computador da urna")+" • "+{"PRINTING":"imprimindo","PRINT_ERROR":"impressão requer mesário","IN_USE":"em votação","AVAILABLE":"livre"}.get(urn["status"],urn["status"]))
                    self.emit("devices","\n".join(lines) if lines else "Nenhuma urna conectada. Use Conectar computador da urna.")
                else:
                    cfg=dict(self.config)
                    printer=cfg.get("printer","");mode=cfg.get("mode","windows")
                    ready=fonts and cfg.get("tested")==printer+"|"+mode and printer_available(printer)
                    status=api.request("/api/native/heartbeat",{"printer_name":printer,"printer_mode":mode,"printer_ready":"true" if ready else "false"})
                    compatible=status.get("version")==VERSION
                    self.emit("row","server","Servidor conectado — HTTPS verificado" if compatible else "Versões diferentes. Atualize os dois computadores.",compatible)
                    self.emit("row","detail","Impressora configurada • Teste confirmado" if ready else "Impressora: selecione, instale o driver e confira o teste",ready)
                    operational=compatible and (ready or not status["print_required"]) and fonts
                    self.emit("ready",operational)
                    self.emit("devices",cfg.get("urn_code","Urna")+" • "+{"PRINTING":"Imprimindo…","PRINT_ERROR":"Impressão requer intervenção do mesário.","IN_USE":"Votação em andamento","AVAILABLE":"Aguardando liberação da Mesa"}.get(status["status"],status["status"]))
                    if operational:
                        job=api.request("/api/native/print-job")
                        if job["pending"]:
                            success=self.journal.perform(job["id"],lambda:send_print(job["payload"],printer,mode))
                            api.request("/api/native/print-job/"+job["id"]+"/complete",{"success":"true" if success else "false"})
                            if not success:self.emit("notice","Não foi possível confirmar a impressão. Confira a impressora e peça ao mesário para autorizar a reimpressão.")
                failures=0
            except Exception as exc:
                failures+=1
                self.emit("row","server",str(exc),False)
                self.emit("ready",False)
                if self.role=="central":
                    self.emit("devices","Estado das urnas indisponível enquanto o servidor estiver desconectado.")
                elif failures>=3 and self.config.get("server_id"):
                    try:self.reconnect()
                    except Exception:pass
                    failures=0
            self.stop.wait(2)

    def diagnostics(self):
        report="\n".join(var.get() for var,label in self.rows.values())+"\n\n"+self.devices.get()
        report+="\n\nUse os dois computadores no mesmo roteador, por cabo.\nRedes de convidados podem impedir a conexão.\nMantenha a data e a hora corretas nos dois computadores."
        if self.role=="central":
            logfile=MACHINE_HOME/"logs/server.log"
            if logfile.exists(): report+="\n\nÚltimos registros do servidor:\n"+"\n".join(logfile.read_text("utf-8",errors="replace").splitlines()[-8:])
        messagebox.showinfo("Diagnóstico",report,parent=self.root)

    def close(self):
        text="Fechar a Central também desligará o servidor. Para mantê-lo ativo, use Minimizar. Deseja fechar?" if self.role=="central" else "Fechar este aplicativo interrompe a conexão e a impressão da urna. Deseja fechar?"
        if not messagebox.askyesno("Fechar",text,parent=self.root):return
        def shutdown():
            if self.role=="central" and self.api:
                try:
                    self.api.request("/api/local/stop",{})
                except Exception:
                    if self.server_proc and self.server_proc.poll() is not None:
                        pass
                    else:
                        raise
            self.stop.set()
            self.emit("closed")
        self.background(shutdown)


def self_test():
    from native_runtime import renderer, edge_path
    import tempfile
    with tempfile.TemporaryDirectory() as temp:
        journal=PrintJournal(Path(temp)/"test.db")
        count=[]
        assert journal.perform("one",lambda:count.append(1))
        assert journal.perform("one",lambda:count.append(1))
        assert len(count)==1
    root=tk.Tk();root.withdraw();ttk.Label(root,text="Urna Escolar").pack();root.update();root.destroy()
    renderer().printers()
    edge_path()


def main():
    if "--self-test" in sys.argv:
        self_test();return
    role="central" if "--central" in sys.argv else "urna" if "--urna" in sys.argv else None
    if not role:
        try:role=json.loads((MACHINE_HOME/"role.json").read_text("utf-8-sig"))["role"]
        except Exception:role=None
    root=tk.Tk()
    if role not in ("central","urna"):
        messagebox.showerror("Configuração ausente","Execute o instalador e escolha Central + Mesa ou Urna de votação.",parent=root);root.destroy();return
    try:
        instance=acquire_instance(role)
    except OSError:
        messagebox.showinfo("Já está aberto","Este aplicativo já está aberto. Procure-o na barra de tarefas do Windows.",parent=root);root.destroy();return
    app=Desktop(root,role)
    root.mainloop()
    instance.close()


if __name__=="__main__":
    try:main()
    except Exception as exc:
        try:
            if "--self-test" in sys.argv:
                import traceback
                APP_HOME.mkdir(parents=True, exist_ok=True)
                (APP_HOME/"self-test-error.txt").write_text(traceback.format_exc(),"utf-8")
            else:
                messagebox.showerror("Urna Escolar",str(exc))
        except Exception:pass
        sys.exit(1)
