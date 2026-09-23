import hmac
import json
import time
import threading
from collections import deque
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import set_key
from .config import ROOT, settings
from .models import DataInput, ConversationInput, ChatInput, LocalSetup
from .store import get_store
from . import services

security=HTTPBearer(auto_error=False)

def authorized(request:Request, credential:HTTPAuthorizationCredentials|None=Depends(security)):
    config=settings()
    if config.production and not config.access_token:
        raise HTTPException(503,'서비스 접근키 설정이 필요합니다.')
    if config.access_token and (not credential or not hmac.compare_digest(credential.credentials,config.access_token)):
        raise HTTPException(401,'서비스 접근키를 입력해 주세요.')

router=APIRouter(prefix='/api',dependencies=[Depends(authorized)])

@router.get('/data',tags=['데이터'])
def list_data(metric:str|None=None):
    if metric is not None and metric not in services.LABELS:
        raise HTTPException(422,'지표는 visits 또는 pageviews입니다.')
    return services.data_list(metric)

@router.get('/data/summary',tags=['데이터'])
def get_summary(): return services.summary()

@router.post('/data',status_code=201,tags=['데이터'])
def add_data(body:DataInput): return services.save_data(body)

@router.put('/data/{key}',tags=['데이터'])
def update_data(key:str,body:DataInput): return services.save_data(body,key)

@router.delete('/data/{key}',tags=['데이터'])
def delete_data(key:str):
    services.required('data',key)
    get_store().delete('data',key)
    return {'deleted':key}

@router.post('/data-import',tags=['데이터'])
def import_data(): return services.seed()

@router.get('/conversations',tags=['대화'])
def list_conversations(): return services.conversations()

@router.get('/conversations/{key}',tags=['대화'])
def read_conversation(key:str): return services.required('conversations',key)

@router.post('/conversations',status_code=201,tags=['대화'])
def create_conversation(body:ConversationInput):
    return services.save_conversation(body.title,[m.model_dump() for m in body.messages])

@router.delete('/conversations/{key}',tags=['대화'])
def delete_conversation(key:str):
    services.required('conversations',key)
    get_store().delete('conversations',key)
    return {'deleted':key}

chat_lock=threading.Lock()
requests=deque()

@router.post('/chat',tags=['AI'])
def create_chat(body:ChatInput):
    # A single personal user, one worker; protects conversation writes and spending.
    if not chat_lock.acquire(blocking=False):
        raise HTTPException(429,'이전 답변을 작성 중입니다. 완료 후 다시 요청해 주세요.')
    try:
        current=time.monotonic()
        while requests and current-requests[0]>3600: requests.popleft()
        if len(requests)>=30 or sum(current-t<60 for t in requests)>=5:
            raise HTTPException(429,'요청 횟수를 초과했습니다. 분당 5회, 시간당 30회까지 가능합니다.')
        if settings().api_key: requests.append(current)
        return services.chat(body)
    finally:
        chat_lock.release()

local=APIRouter(prefix='/local',include_in_schema=False)

def local_only(request:Request):
    if settings().production or request.client.host not in ('127.0.0.1','::1','testclient'):
        raise HTTPException(404)
    if request.url.hostname not in ('127.0.0.1','localhost','testserver'):
        raise HTTPException(403)
    origin=request.headers.get('origin')
    if origin and origin != str(request.base_url).rstrip('/'):
        raise HTTPException(403)
    if request.headers.get('x-local-setup')!='1':
        raise HTTPException(403)

@local.post('/setup',dependencies=[Depends(local_only)])
def setup(body:LocalSetup):
    if body.gemini_api_key and (len(body.gemini_api_key)<20 or any(c.isspace() for c in body.gemini_api_key)):
        raise HTTPException(422,'Gemini API 키 형식을 확인해 주세요.')
    if body.openai_api_key:
        if not body.openai_api_key.startswith('sk-') or any(c.isspace() for c in body.openai_api_key):
            raise HTTPException(422,'OpenAI API 키 형식을 확인해 주세요.')
    credential=None
    if body.firebase_service_account_json:
        try:
            credential=json.loads(body.firebase_service_account_json)
            if credential.get('type')!='service_account' or not all(credential.get(k) for k in ['project_id','private_key','client_email']):
                raise ValueError()
        except (ValueError,TypeError):
            raise HTTPException(422,'Firebase 서비스 계정 JSON 파일인지 확인해 주세요.')
    env=ROOT / '.env'
    set_key(str(env),'AI_PROVIDER',body.ai_provider)
    if body.gemini_api_key: set_key(str(env),'GEMINI_API_KEY',body.gemini_api_key)
    if body.openai_api_key: set_key(str(env),'OPENAI_API_KEY',body.openai_api_key)
    if credential:
        set_key(str(env),'FIREBASE_SERVICE_ACCOUNT_JSON',json.dumps(credential))
        set_key(str(env),'STORAGE_BACKEND','firestore')
    return {'saved':True,'message':'설정을 저장했습니다. Firestore를 연결했다면 샘플 데이터 가져오기를 눌러 주세요.'}
