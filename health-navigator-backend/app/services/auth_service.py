'''
구현 목록

1. 회원가입
UserCreate → hash_password → DB 저장

이메일 중복 체크
비밀번호 해싱
DB 저장

2. 로그인
email → DB 조회 → verify_password → create_access_token

사용자 조회
비밀번호 검증
JWT 발급
'''
from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.user import UserCreate
from app.core.security import hash_password, verify_password


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()


def create_user(db: Session, user_data: UserCreate) -> User | None:
    existing_user = get_user_by_email(db, user_data.email)
    if existing_user:
        return None

    hashed_password = hash_password(user_data.password)

    new_user = User(
        email=user_data.email,
        password_hash=hashed_password,
        name=user_data.name,
        birth_date=user_data.birth_date,
        gender=user_data.gender
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = get_user_by_email(db, email)

    if not user:
        return None

    if not verify_password(password, user.password_hash):
        return None

    return user
