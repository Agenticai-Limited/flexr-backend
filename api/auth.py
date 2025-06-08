from fastapi import HTTPException
from pydantic import BaseModel
from .pg_dbutil import PGDBUtil

class LoginRequest(BaseModel):
  username: str
  password: str

def authenticate_user(request: LoginRequest):
    return PGDBUtil.authenticate_user(request.username, request.password)
