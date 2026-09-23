"""Firestore for production; explicit SQLite preview for local development only."""
import json
import hashlib
import sqlite3
from functools import lru_cache
from fastapi import HTTPException
from .config import ROOT, settings

class SQLiteStore:
    def __init__(self):
        self.path = ROOT / '.local' / 'preview.sqlite3'
        self.path.parent.mkdir(exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS records (collection TEXT, id TEXT, payload TEXT, PRIMARY KEY(collection,id))')

    def connect(self):
        return sqlite3.connect(self.path, timeout=20)

    def list(self, collection):
        with self.connect() as db:
            return [{'id': key, **json.loads(payload)} for key, payload in db.execute('SELECT id,payload FROM records WHERE collection=?', (collection,))]

    def get(self, collection, key):
        with self.connect() as db:
            row = db.execute('SELECT payload FROM records WHERE collection=? AND id=?', (collection, key)).fetchone()
        return {'id': key, **json.loads(row[0])} if row else None

    def put(self, collection, key, data):
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO records VALUES (?,?,?)', (collection, key, json.dumps(data, ensure_ascii=False)))
        return {'id': key, **data}

    def delete(self, collection, key):
        with self.connect() as db:
            db.execute('DELETE FROM records WHERE collection=? AND id=?', (collection, key))

class FirestoreStore:
    def __init__(self, credential_json):
        import firebase_admin
        from firebase_admin import credentials, firestore
        try:
            credential = json.loads(credential_json)
            app_name = 'blog-' + hashlib.sha256(credential_json.encode()).hexdigest()[:16]
            try:
                app = firebase_admin.get_app(app_name)
            except ValueError:
                app = firebase_admin.initialize_app(credentials.Certificate(credential), name=app_name)
            self.db = firestore.client(app=app)
            # The REST transport also works on networks that block gRPC.
            from google.cloud.firestore_v1.services.firestore import FirestoreClient
            self.db._firestore_api_internal = FirestoreClient(
                credentials=self.db._credentials, transport='rest'
            )
        except Exception as exc:
            raise HTTPException(503, 'Firestore 설정을 확인해 주세요. 서비스 계정 JSON과 데이터베이스가 필요합니다.') from exc

    def list(self, collection):
        return [{'id': doc.id, **doc.to_dict()} for doc in self.db.collection(collection).stream()]

    def get(self, collection, key):
        doc = self.db.collection(collection).document(key).get()
        return {'id': doc.id, **doc.to_dict()} if doc.exists else None

    def put(self, collection, key, data):
        self.db.collection(collection).document(key).set(data)
        return {'id': key, **data}

    def delete(self, collection, key):
        self.db.collection(collection).document(key).delete()

@lru_cache(maxsize=4)
def _store(backend, credential):
    if backend == 'firestore':
        return FirestoreStore(credential)
    if backend == 'sqlite':
        return SQLiteStore()
    raise HTTPException(503, '지원하지 않는 저장소 설정입니다.')

def get_store():
    config = settings()
    if config.production and (config.storage != 'firestore' or not config.access_token):
        raise HTTPException(503, '배포 환경에는 Firestore와 APP_ACCESS_TOKEN 설정이 필요합니다.')
    return _store(config.storage, config.firebase_json)
