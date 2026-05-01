# Health Navigator Backend

## 1. 프로젝트 개요
건강검진 결과(OCR 기반)와 의약품 정보를 활용하여  
사용자의 건강 상태 분석 및 복용약 관리 기능을 제공하는 백엔드 시스템.

---

## 2. 주요 기능

### 2.1 사용자 인증 (Auth)
- 회원가입
- 로그인
- JWT 기반 인증

### 2.2 건강검진 OCR / 파싱
- 건강검진표 OCR 결과 처리
- 텍스트 재구성 및 데이터 구조화
- 건강 상태 판정 로직

### 2.3 의약품 조회
- 약 이름 검색
- 약 상세 정보 조회

### 2.4 복용약 관리
- 사용자 복용약 추가 / 삭제
- 복용약 목록 조회
- 중복 등록 방지

### 2.5 병용금기 / 중복 복용 검사
- DUR 기반 병용금기 검사
- 효능군 중복 검사
- ATC 코드 기반 중복 검사

---

## 3. 기술 스택

- Backend: FastAPI
- Language: Python
- Database: MySQL
- Data Processing: Pandas
- OCR: CLOVA OCR API

---

## 4. 프로젝트 구조

app/
 ├── core/        # 설정, DB, 보안
 ├── models/      # DB 모델
 ├── schemas/     # 요청/응답 스키마
 ├── routers/     # API 라우터
 ├── services/    # 비즈니스 로직
 └── main.py      # 엔트리 포인트

---

## 5. 실행 방법

### 1) 설치
pip install -r requirements.txt

### 2) 환경 변수 설정 및 실행

# 환경 변수 설정 (.env 또는 직접 설정)
CLOVA_OCR_INVOKE_URL=your_url
CLOVA_OCR_SECRET_KEY=your_key

# 서버 실행
uvicorn app.main:app --reload

---

## 6. API 문서

서버 실행 후:
http://localhost:8000/docs

---

## 7. 주의사항

- .env 파일은 GitHub에 업로드하지 않음
- 대용량 데이터(parquet)는 포함하지 않음

---

## 8. 향후 계획

- ML 기반 질병 예측 기능 추가
- 사용자 건강 리포트 자동 생성
- Flutter 앱과 연동
- parquet 파일 db와 연동하여 코드 수정