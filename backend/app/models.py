from datetime import date
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator

class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

class DataInput(StrictModel):
    date: date
    value: int = Field(ge=0, le=100000000)
    memo: str = Field(default='', max_length=1000)
    metric: Literal['visits', 'pageviews'] = 'visits'

    @field_validator('date')
    @classmethod
    def no_future(cls, value):
        if value > date.today():
            raise ValueError('미래 날짜의 실적은 입력할 수 없습니다.')
        return value

class Message(StrictModel):
    role: Literal['user', 'assistant']
    content: str = Field(min_length=1, max_length=20000)

class ConversationInput(StrictModel):
    title: str = Field(min_length=1, max_length=120)
    messages: list[Message] = Field(min_length=1, max_length=40)

class ChatInput(StrictModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = Field(default=None, pattern=r'^[a-zA-Z0-9_-]{1,100}$')
    category: Literal['미용', '생활정보', '요리'] = '미용'
    tone: Literal['친근한 존댓말', '차분한 설명체'] = '친근한 존댓말'
    length: int = Field(default=1500, ge=500, le=2500)

class LocalSetup(StrictModel):
    ai_provider: Literal['gemini', 'openai'] = 'gemini'
    gemini_api_key: str = Field(default='', max_length=500)
    openai_api_key: str = Field(default='', max_length=500)
    firebase_service_account_json: str = Field(default='', max_length=12000)
