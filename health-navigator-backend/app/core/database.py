from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# MySQL 연결 URL
SQLALCHEMY_DATABASE_URL = "mysql+pymysql://root:jiun7925!@localhost:3306/health_navigator"

# 엔진 생성
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    echo=True  # SQL 로그 확인용 (나중에 False로 변경 가능)
)

# 세션 생성
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Base 클래스 (모델에서 상속)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()