import logging
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from app.config import settings
from app.api import router, local

config=settings()
app=FastAPI(title='나의 블로그 비서 API',version='1.0.0',description='미용·생활정보·요리 글 작성과 블로그 시계열 분석')
app.add_middleware(CORSMiddleware,allow_origins=config.origins,allow_credentials=False,allow_methods=['GET','POST','PUT','DELETE'],allow_headers=['Authorization','Content-Type'])
if not config.production:
    app.add_middleware(TrustedHostMiddleware,allowed_hosts=['localhost','127.0.0.1','testserver'])
app.include_router(router)
app.include_router(local)

@app.exception_handler(Exception)
async def failure(request:Request, exc:Exception):
    logging.getLogger('blog').error('Request failed: %s',type(exc).__name__)
    return JSONResponse(status_code=503,content={'detail':'저장소 연결 또는 서버 설정을 확인해 주세요. 잠시 후 다시 시도할 수 있습니다.'})

@app.get('/health',tags=['상태'])
def health():
    s=settings()
    return {'status':'ok','storage':s.storage,'ai_configured':bool(s.api_key),'firebase_configured':bool(s.firebase_json),'local_setup':not s.production,'auth_required':bool(s.access_token),'model':s.model,'provider':s.provider}

frontend=Path(__file__).resolve().parents[1] / 'frontend'
@app.get('/',include_in_schema=False)
def home(): return FileResponse(frontend/'index.html')
app.mount('/static',StaticFiles(directory=frontend),name='static')
