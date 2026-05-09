from pydantic import BaseModel, EmailStr, field_validator
from datetime import date, datetime
from typing import Literal


##schema는 api 입출력 데이터 형식이다.

# 회원가입
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    birth_date: date
    gender: Literal["male", "female"]

    @field_validator("birth_date")
    @classmethod
    def birth_date_cannot_be_future(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("생년월일은 오늘 이후 날짜일 수 없습니다.")
        return value

#로그인
class UserLogin(BaseModel):
    email: EmailStr
    password: str

#사용자 정보 반환
class UserResponse(BaseModel):
    id: int
    email: EmailStr
    name: str
    birth_date: date
    gender: Literal["male", "female"]
    created_at: datetime

    class Config:
        from_attributes = True

#로그인 성공 시 토큰 반환
class Token(BaseModel):
    access_token: str
    token_type: str
