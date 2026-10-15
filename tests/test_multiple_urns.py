from fastapi.testclient import TestClient

def test_second_urn_without_votes_exports_zero_not_global_result(prepared):
    import secrets
    from test_integration import connect,ok,complete,authorize,vote
    from conftest import PASSWORD
    from app.security import sha256_text
    from app.db import SessionLocal
    from sqlalchemy import select
    c=prepared;first=connect(c)
    token=secrets.token_urlsafe(32)
    item=ok(c.post('/api/deployment/pair',data={'token_hash':sha256_text(token),'computer_name':'PC-URNA2'}))
    approved=ok(c.post(f"/api/deployment/pairing/{item['id']}/approve"))
    assert approved['urn_code']=='URNA02'
    second={'Authorization':'Bearer '+token}
    ok(c.post('/api/native/heartbeat',headers=second,data={'printer_name':'Simulada2','printer_mode':'windows','printer_ready':'true'}))
    assert c.post('/admin/seal',follow_redirects=False).status_code==303
    c.cookies.delete('session_id');c.post('/login',data={'username':'mesa','password':PASSWORD})
    opening=ok(c.post('/api/mesario/open/prepare',data={'password':PASSWORD}))
    complete(c,first);complete(c,second)
    ok(c.post('/api/mesario/open/commit',data={'ticket':opening['ticket']}))
    token=authorize(c);ok(vote(c,token));complete(c,first)
    closing=ok(c.post('/api/mesario/close',data={'password':PASSWORD,'confirm_close':'yes'}))
    assert closing['result']['total']==1
    bu1=complete(c,first);bu2=complete(c,second)
    assert bu1['payload']['paper']['total']==1
    assert bu2['payload']['paper']['total']==0
    assert all(s['votes']==0 for s in bu2['payload']['paper']['slates'])

def test_two_urns_vote_concurrently_without_crossing_totals(prepared):
    import secrets
    from concurrent.futures import ThreadPoolExecutor
    from test_integration import connect,ok,complete,authorize
    from conftest import PASSWORD
    from app.main import app
    from app.security import sha256_text
    c=prepared;first=connect(c)
    secret=secrets.token_urlsafe(32)
    item=ok(c.post('/api/deployment/pair',data={'token_hash':sha256_text(secret),'computer_name':'Segunda urna fictícia'}))
    assert ok(c.post(f"/api/deployment/pairing/{item['id']}/approve"))['urn_code']=='URNA02'
    second={'Authorization':'Bearer '+secret}
    ok(c.post('/api/native/heartbeat',headers=second,data={'printer_name':'Simulada2','printer_mode':'windows','printer_ready':'true'}))
    assert c.post('/admin/seal',follow_redirects=False).status_code==303
    c.cookies.delete('session_id');c.post('/login',data={'username':'mesa','password':PASSWORD})
    opening=ok(c.post('/api/mesario/open/prepare',data={'password':PASSWORD}))
    complete(c,first);complete(c,second)
    ok(c.post('/api/mesario/open/commit',data={'ticket':opening['ticket']}))
    with TestClient(app,base_url='https://testserver') as other:
        path=ok(c.post('/api/native/browser-ticket',headers=second))['path']
        assert other.get(path).status_code==200
        token1=authorize(c,'1000')
        ok(c.post('/api/mesario/authorize',data={'enrollment':'1001','urn_code':'URNA02'}))
        token2=ok(other.get('/api/urna/URNA02/authorization'))['token']
        requests=[(c,'URNA01',token1,'slate'),(other,'URNA02',token2,'blank')]
        def cast(args):
            client,code,token,choice=args
            return ok(client.post('/api/urna/'+code+'/vote',data={'token':token,'choice_type':choice,'slate_number':10}))
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(cast,requests))
        assert all(r['recorded'] for r in results)
        complete(c,first);complete(c,second)
    closing=ok(c.post('/api/mesario/close',data={'password':PASSWORD,'confirm_close':'yes'}))
    assert closing['result']['total']==2 and closing['result']['blank']==1
    assert closing['result']['per_urn']['URNA01']['slates'][0]['votes']==1
    assert closing['result']['per_urn']['URNA02']['blank']==1

