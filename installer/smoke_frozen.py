"""Exercise newly compiled Windows EXEs with disposable data and no Python in PATH.

This does not install anything or use the school's database/printer/USB.
Run on the build machine after BUILD_WINDOWS.ps1.
"""
import http.cookiejar
import json
import os
from pathlib import Path
import secrets
import socket
import ssl
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://127.0.0.1:8443'


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def run():
    if os.name != 'nt':
        raise RuntimeError('Este ensaio exige Windows e os EXEs compilados.')
    with socket.socket() as check:
        check.bind(('127.0.0.1', 8443))  # Refuse to probe another live Central.
    tests = ROOT / 'test-results'
    tests.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='frozen-completo-', dir=tests) as folder:
        data = Path(folder)
        env = dict(os.environ)
        env.update(URNA_BUILD_DATA_DIR=str(data / 'UrnaEscolar'),
                   LOCALAPPDATA=str(data / 'perfil'), PROGRAMDATA=str(data / 'maquina'),
                   PATH=os.environ['SystemRoot'] + '\\System32;' + os.environ['SystemRoot'])
        for name in ('PYTHONHOME', 'PYTHONPATH', 'URNA_PARENT_PID', 'URNA_DATA_DIR', 'URNA_DB_PATH'):
            env.pop(name, None)
        for relative in ('dist/UrnaEscolar/UrnaEscolar.exe',):
            subprocess.run([str(ROOT / relative), '--self-test'], env=env,
                           creationflags=subprocess.CREATE_NO_WINDOW, timeout=90, check=True)
        server = subprocess.Popen([str(ROOT / 'dist/UrnaEscolarServidor/UrnaEscolarServidor.exe')],
                                  env=env, creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            ca = data / 'UrnaEscolar/Servidor/tls/urna_escolar_ca.crt'
            opener = None
            for _ in range(150):
                if server.poll() is not None:
                    raise RuntimeError('O EXE do servidor encerrou antes do primeiro acesso.')
                try:
                    context = ssl.create_default_context(cafile=str(ca))
                    opener = urllib.request.build_opener(
                        urllib.request.ProxyHandler({}), NoRedirect,
                        urllib.request.HTTPSHandler(context=context),
                        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
                    with opener.open(URL + '/health', timeout=2) as response:
                        assert json.load(response)['ok']
                    break
                except (OSError, urllib.error.URLError):
                    time.sleep(.2)
            else:
                raise RuntimeError('Servidor não respondeu com CA e hostname válidos.')

            def request(path, fields=None, expected=200):
                body = urllib.parse.urlencode(fields).encode() if fields is not None else None
                req = urllib.request.Request(URL + path, data=body, headers={'Origin': URL})
                try:
                    response = opener.open(req, timeout=20)
                except urllib.error.HTTPError as error:
                    response = error
                with response:
                    content = response.read()
                    assert response.code == expected, f'{path}: HTTP {response.code}: {content[:300]!r}'
                    return content

            request('/setup')
            password = secrets.token_urlsafe(24)
            fields = {'username': 'admin-ensaio', 'display_name': 'Administrador de ensaio isolado',
                      'password': password}
            request('/setup', fields, 303)
            request('/setup', fields, 409)
            request('/login', {'username': fields['username'], 'password': password}, 303)
            request('/admin')
            request('/admin/voters/manual', {'name': 'Aluno fictício do ensaio', 'class_code': 'Turma teste'}, 303)
            request('/admin/slates', {'number': 10, 'name': 'Chapa fictícia do ensaio'}, 303)
            request('/admin/users', {'username': 'mesa-ensaio', 'display_name': 'Mesário fictício',
                                     'password': secrets.token_urlsafe(24), 'role': 'MESARIO'}, 303)
            request('/admin/urns', {'code': 'TESTE01', 'name': 'Urna do ensaio isolado',
                                    'device_secret': secrets.token_urlsafe(24)}, 303)
            request('/admin/seal', {}, 303)
            request('/admin')
            request('/admin/publication', expected=404)
            request('/api/local/publication', expected=404)
            request('/admin/voters/manual', {'name': 'Outro aluno', 'class_code': 'Turma teste'}, 409)
            print('EXEs: autotestes, HTTPS com CA/hostname, primeiro ADMIN, aluno sem matrícula/turno,')
            print('chapa, lacração, ausência de publicação e bloqueios pós-lacração: OK.')
        finally:
            if server.poll() is None:
                server.terminate()
            server.wait(timeout=20)
    print('Ensaio concluído; dados descartáveis removidos. Impressora e USB físicos não utilizados.')


if __name__ == '__main__':
    run()
