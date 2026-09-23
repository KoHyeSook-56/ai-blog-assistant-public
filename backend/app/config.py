import os
from pathlib import Path
from dataclasses import dataclass
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]

@dataclass
class Settings:
    provider: str
    storage: str
    api_key: str
    model: str
    firebase_json: str
    access_token: str
    origins: list[str]
    production: bool
    max_tokens: int

def settings():
    values = {**dotenv_values(ROOT / '.env'), **os.environ}
    production = values.get('APP_ENV') == 'production'
    provider = values.get('AI_PROVIDER', 'gemini')
    if provider not in ('gemini', 'openai'):
        raise ValueError('AI_PROVIDER must be gemini or openai')
    return Settings(
        provider=provider,
        storage=values.get('STORAGE_BACKEND', 'firestore' if production else 'sqlite'),
        api_key=values.get('GEMINI_API_KEY' if provider == 'gemini' else 'OPENAI_API_KEY', ''),
        model=values.get('GEMINI_MODEL', 'gemini-3.5-flash-lite') if provider == 'gemini' else values.get('OPENAI_MODEL', 'gpt-4.1-mini'),
        firebase_json=values.get('FIREBASE_SERVICE_ACCOUNT_JSON', ''),
        access_token=values.get('APP_ACCESS_TOKEN', ''),
        origins=[s.strip() for s in values.get('ALLOWED_ORIGINS', 'http://127.0.0.1:8765,http://localhost:8765').split(',') if s.strip()],
        production=production,
        max_tokens=max(128, min(int(values.get('MAX_OUTPUT_TOKENS', '2200')), 4000)),
    )
