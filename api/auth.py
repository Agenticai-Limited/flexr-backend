from fastapi import HTTPException
from pydantic import BaseModel
from .db_factory import DBFactory

class LoginRequest(BaseModel):
  username: str
  password: str

def authenticate_user(request: LoginRequest):
    return DBFactory.get_db_util().authenticate_user(request.username, request.password)
