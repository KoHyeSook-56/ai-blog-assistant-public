"""Run after installing requirements plus httpx and pytest. No external API calls."""
import pytest
from fastapi.testclient import TestClient
from app import services
from app.store import SQLiteStore
from app.config import settings
from main import app

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('APP_ENV','development')
    monkeypatch.setenv('APP_ACCESS_TOKEN','')
    monkeypatch.setenv('OPENAI_API_KEY','')
    monkeypatch.setenv('GEMINI_API_KEY','')
    monkeypatch.setenv('AI_PROVIDER','openai')
    monkeypatch.setenv('STORAGE_BACKEND','sqlite')
    import app.store as storage
    import app.api as api
    monkeypatch.setattr(storage,'ROOT',tmp_path)
    store=SQLiteStore()
    monkeypatch.setattr(services,'get_store',lambda:store)
    monkeypatch.setattr(api,'get_store',lambda:store)
    return TestClient(app)

def test_crud_duplicate_and_summary(client):
    body={'date':'2020-01-01','value':4,'memo':'검증','metric':'visits'}
    created=client.post('/api/data',json=body)
    assert created.status_code==201
    key=created.json()['id']
    assert client.post('/api/data',json=body).status_code==409
    assert client.post('/api/data',json={**body,'value':-1}).status_code==422
    assert client.put('/api/data/'+key,json={**body,'value':8}).status_code==200
    assert client.get('/api/data/summary').json()['series'][0]['total']==8
    assert client.delete('/api/data/'+key).status_code==200
    assert client.get('/api/data').json()==[]

def test_conversation_roundtrip_and_no_fake_ai(client):
    messages=[{'role':'user','content':'질문'},{'role':'assistant','content':'보관할 초안'}]
    created=client.post('/api/conversations',json={'title':'요리 초안','messages':messages}).json()
    assert client.get('/api/conversations/'+created['id']).json()['messages']==messages
    assert 'messages' not in client.get('/api/conversations').json()[0]
    assert client.post('/api/chat',json={'message':'글 써줘'}).status_code==503
    assert client.delete('/api/conversations/'+created['id']).status_code==200

def test_import_is_idempotent_and_preserves_edits(client):
    assert client.post('/api/data-import').json()['added']==180
    row=client.get('/api/data').json()[0]
    client.put('/api/data/'+row['id'],json={k:row[k] for k in ['date','value','metric']}|{'memo':'내 수정'})
    assert client.post('/api/data-import').json()['added']==0
    assert any(r['memo']=='내 수정' for r in client.get('/api/data').json())

def test_auth_and_local_setup_protection(client,monkeypatch):
    monkeypatch.setenv('APP_ACCESS_TOKEN','test-private-token')
    assert client.get('/api/data').status_code==401
    assert client.get('/api/data',headers={'Authorization':'Bearer test-private-token'}).status_code==200
    assert client.post('/local/setup',json={}).status_code==403
    assert client.post('/local/setup',json={},headers={'X-Local-Setup':'1','Origin':'https://other.example'}).status_code==403

def test_chat_injects_summary_and_autosaves(client,monkeypatch):
    import openai
    monkeypatch.setenv('OPENAI_API_KEY','sk-unit-test-only')
    captured={}
    class Stub:
        def __init__(self,**kwargs): self.responses=self
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def create(self,**kwargs):
            captured.update(kwargs)
            return type('Response',(),{'output_text':'테스트용 응답','status':'completed'})()
    monkeypatch.setattr(openai,'OpenAI',Stub)
    client.post('/api/data-import')
    res=client.post('/api/chat',json={'message':'방문 흐름 알려줘'})
    assert res.status_code==200
    assert '<data_summary>' in captured['instructions'] and '493' in captured['instructions']
    assert captured['store'] is False
    conversation=client.get('/api/conversations/'+res.json()['conversation_id']).json()
    assert conversation['messages'][-1]['content']=='테스트용 응답'

@pytest.mark.parametrize('empty', [False, True])
def test_gemini_google_endpoint_context_and_storage(client,monkeypatch,empty):
    import openai
    from types import SimpleNamespace as NS
    monkeypatch.setenv('AI_PROVIDER','gemini')
    monkeypatch.setenv('GEMINI_API_KEY','unit-test-gemini-not-a-real-key')
    captured={}
    class Stub:
        def __init__(self,**kwargs):
            captured['client']=kwargs
            self.chat=NS(completions=self)
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def create(self,**kwargs):
            captured['request']=kwargs
            return NS(choices=[] if empty else [NS(message=NS(content='Gemini 테스트 초안'),finish_reason='stop')])
    monkeypatch.setattr(openai,'OpenAI',Stub)
    client.post('/api/data-import')
    result=client.post('/api/chat',json={'message':'두부 요리 글 써줘','category':'요리'})
    assert captured['client']['base_url']=='https://generativelanguage.googleapis.com/v1beta/openai/'
    assert captured['client']['api_key']=='unit-test-gemini-not-a-real-key'
    assert '<data_summary>' in captured['request']['messages'][0]['content']
    assert result.status_code==(502 if empty else 200)
    assert len(client.get('/api/conversations').json())==(0 if empty else 1)

def test_gemini_setup_secret_not_returned(client,monkeypatch,tmp_path):
    import app.api as api
    from dotenv import dotenv_values
    monkeypatch.setattr(api,'ROOT',tmp_path)
    secret='unit-test-gemini-not-a-real-key'
    res=client.post('/local/setup',json={'ai_provider':'gemini','gemini_api_key':secret},headers={'X-Local-Setup':'1'})
    assert res.status_code==200 and secret not in res.text
    saved=dotenv_values(tmp_path/'.env')
    assert saved['AI_PROVIDER']=='gemini' and saved['GEMINI_API_KEY']==secret
