from pydantic import BaseModel, EmailStr
from datetime import datetime


##schema는 api 입출력 데이터 형식이다.

# 회원가입
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str

#로그인
class UserLogin(BaseModel):
    email: EmailStr
    password: str

#사용자 정보 반환
class UserResponse(BaseModel):
    id: int
    email: EmailStr
    name: str
    created_at: datetime

    class Config:
        from_attributes = True

#로그인 성공 시 토큰 반환
class Token(BaseModel):
    access_token: str
    token_type: str