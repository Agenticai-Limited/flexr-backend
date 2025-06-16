from typing import Optional
from pydantic import BaseModel
from dataclasses import dataclass

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

@dataclass
class NoResultLog:
    query: str
    username: str
    task_id: str 