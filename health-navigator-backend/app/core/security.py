from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from pwdlib import PasswordHash
from fastapi.security import OAuth2PasswordBearer

#비밀번호를 해싱
password_hash = PasswordHash.recommended()

#jwt 서명용 비밀키. 바꿔야 한다
SECRET_KEY = "your-secret-key-change-this"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


#회원가입 시 사용. 
def hash_password(password: str) -> str:
    return password_hash.hash(password)

#로그인 시 사용자가 입력한 원문 비밀번호와 db에 저장된 해시값이 같은 비밀번호에서 나온 것인지 비교
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)

#로그인 성공 시  jwt 발급
def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta if expires_delta else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    #토큰 만료 시간
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

#토큰을 해석해 payload를 꺼냄
def decode_access_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None