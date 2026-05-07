# Health Navigator-Management

Health Navigator-Management는 건강검진 결과, 생활습관, 복용 의약품 정보를 기반으로 사용자의 건강 상태 이해를 돕는 건강관리 지원 서비스입니다. 본 저장소는 해당 서비스의 백엔드 API, 데이터 처리 로직, 의약품 DB 조회 구조, OCR 결과 처리, AWS 서버 운영 환경 구성을 중심으로 정리한 저장소입니다.

이 프로젝트는 현재 개발 중인 팀 프로젝트이며, 의료 진단이나 처방을 대체하지 않고 참고용 건강관리 정보를 제공하는 것을 목표로 합니다.

## 프로젝트 배경

해외에는 WebMD처럼 증상, 질병, 의약품 정보를 한곳에서 탐색할 수 있는 헬스케어 서비스 사례가 있습니다. 프로젝트 기획 과정에서 WebMD의 정보 통합 방식과 직관적인 탐색 구조를 참고했지만, 영어 기반 서비스이기 때문에 한국인 사용자가 국내 건강검진표, 국내 의약품 정보, 한국어 중심 사용 흐름에 맞춰 활용하기에는 한계가 있다고 보았습니다.

국내에도 건강관리, 질병 정보, 의약품 정보 제공을 목표로 하는 서비스들이 있지만, 일부 서비스는 유료 기능 중심이거나 인증 절차와 사용 흐름이 복잡해 사용자가 꾸준히 활용하기 어렵다는 문제의식이 있었습니다. 이에 Health Navigator-Management는 건강검진 결과 해석, 의약품 정보 조회, 복용 위험 확인 기능을 한 서비스 안에서 연결하고, 한국어 기반으로 더 쉽게 접근할 수 있는 구조를 목표로 설계되었습니다.

## 현재 구현 범위

| 구분 | 상태 | 내용 |
| --- | --- | --- |
| 사용자 인증 | 구현 | 회원가입, 로그인, JWT 발급, 현재 사용자 조회 |
| 건강검진 OCR 처리 | 구현 | 이미지/PDF 업로드, CLOVA OCR 호출, OCR 결과 텍스트 재구성 |
| 건강검진 수치 파싱 | 구현 | 건강검진 수치를 추출하여 JSON 형태로 반환 |
| 건강 상태 판정 | 구현 | 의학적 기준 범위와 실제 수치를 비교하는 rule-based 이상 여부 판정 |
| 의약품 조회 | 구현 | 의약품 목록, 검색, 상세 정보 조회 |
| 복용 의약품 관리 | 구현 | 사용자별 복용약 등록, 목록 조회, 삭제 |
| 병용금기 검사 | 구현 | DUR 데이터 기반 약물 간 병용금기 확인 |
| 중복 복용 검사 | 구현 | 동일 약, 성분 코드, ATC 코드, 효능군 기준 중복 확인 |
| 프론트엔드 연동 | 확인 | Flutter 앱과 REST API 연동 확인 |
| 서버 운영 환경 | 일부 구성 | AWS EC2, 탄력적 IP, SSH 접속, systemd 기반 서버 실행 설정 |

## 주요 기능

### 사용자 인증

- 이메일 기반 회원가입
- 비밀번호 해시 처리
- OAuth2 Password Form 기반 로그인
- JWT access token 발급
- 인증된 사용자 정보 조회

### 건강검진 OCR 및 파싱

- 건강검진표 이미지 또는 PDF 업로드
- CLOVA OCR API 호출
- OCR 응답의 좌표 정보를 기반으로 텍스트 재구성
- 이름, 주민등록번호 일부, 생년월일, 나이, 성별 추출
- 주요 건강검진 수치 추출 및 JSON 응답 반환
- 추출된 수치를 기준 범위와 비교하여 rule-based 건강 상태 판정

현재 OCR 파싱은 좌표 기반 재구성과 정규표현식에 의존하므로, 건강검진표 양식이 달라질 경우 일부 항목이 누락되거나 잘못 매칭될 수 있습니다.

### 의약품 관리 및 DUR 검사

- 의약품 목록 조회
- 의약품명 또는 품목기준코드 기반 검색
- 의약품 상세 정보 조회
- 사용자별 복용 의약품 등록, 조회, 삭제
- DUR 데이터 기반 병용금기 검사
- 동일 약, 성분 코드, ATC 코드, 효능군 기준 중복 복용 검사

초기에는 공공 의약품 데이터를 parquet 파일로 관리했지만, 반복 조회와 pandas 필터링으로 인한 응답 지연을 줄이기 위해 MySQL 테이블 기반 조회 구조로 전환했습니다.

## 기술 스택

| 영역 | 기술 |
| --- | --- |
| Backend Framework | FastAPI |
| Language | Python |
| Database | MySQL |
| ORM | SQLAlchemy |
| Authentication | JWT, OAuth2 Password Bearer |
| Password Hashing | pwdlib[argon2] |
| OCR | CLOVA OCR API |
| Data Processing | Pandas, Parquet |
| API Docs | Swagger UI, ReDoc |
| Infrastructure | AWS EC2, Elastic IP, Ubuntu, systemd |
| Remote Access | SSH, MobaXterm |

## 프로젝트 구조

```text
healthcare management/
├─ README.md
├─ docs/
│  ├─ DATABASE.md
│  ├─ API.md
│  ├─ DEPLOYMENT.md
│  └─ ROADMAP.md
└─ health-navigator-backend/
   ├─ app/
   │  ├─ core/        # 환경 변수, DB 연결, 보안 설정
   │  ├─ data/        # 의약품 및 DUR parquet 데이터
   │  ├─ models/      # SQLAlchemy 모델
   │  ├─ routers/     # FastAPI 라우터
   │  ├─ schemas/     # Pydantic 요청/응답 스키마
   │  ├─ services/    # 인증, OCR, 파싱, 의약품 비즈니스 로직
   │  ├─ utils/
   │  └─ main.py      # FastAPI 앱 진입점
   ├─ scripts/
   ├─ tools/
   └─ requirements.txt
```

## 실행 방법

### 1. 가상환경 생성 및 패키지 설치

```bash
cd health-navigator-backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 환경 변수 설정

`health-navigator-backend/.env` 파일을 생성하고 CLOVA OCR 설정값을 입력합니다.

```env
CLOVA_OCR_INVOKE_URL=your_clova_ocr_invoke_url
CLOVA_OCR_SECRET_KEY=your_clova_ocr_secret_key
```

현재 DB 연결 정보는 `health-navigator-backend/app/core/database.py`에 MySQL 연결 문자열로 작성되어 있습니다.

### 3. 서버 실행

```bash
uvicorn app.main:app --reload
```

### 4. API 문서 확인

서버 실행 후 아래 주소에서 API 문서를 확인할 수 있습니다.

```text
http://localhost:8000/docs
```

## 상세 문서

| 문서 | 내용 |
| --- | --- |
| [DATABASE.md](docs/DATABASE.md) | DB 구조, parquet 원본 데이터 적재 방식, 의약품 조회/검사 기준 |
| [API.md](docs/API.md) | 주요 API 목록, OCR 응답 구조, 의약품 응답 구조 |
| [DEPLOYMENT.md](docs/DEPLOYMENT.md) | AWS EC2, Elastic IP, SSH, MobaXterm, systemd 서버 운영 환경 |
| [ROADMAP.md](docs/ROADMAP.md) | OCR 결과 저장, 자동완성, 인체 UI, ML/XAI, LLM 확장 계획 |

## 현재 한계 및 개선 계획

- 건강검진표 양식에 따라 OCR 파싱 정확도가 달라질 수 있음
- rule-based 판정은 기준 범위 기반 이상 여부 확인에는 적합하지만 사용자 생활 컨텍스트 반영은 제한적임
- DB 연결 정보와 보안 키를 환경 변수 기반으로 분리할 필요가 있음
- 테스트 코드와 API 검증 시나리오가 추가로 필요함
- Flutter 프론트엔드와 연동은 확인했으며, 화면 흐름 전체에 대한 추가 검증이 필요함
- systemd 서비스 설정, 서버 실행 명령, 배포 절차 문서화가 필요함
- AWS 인스턴스 사양은 기능 확장에 따라 상향 조정 가능성이 있음
- 캡스톤 조직 환경 종료 이후에는 AWS 운영 비용과 배포 지속 여부를 재검토해야 함

## 구현 예정

- OCR 결과 DB 저장
- 로그인 사용자 기준 건강검진 결과 저장
- OCR 결과 수정 및 재판정
- 의약품 검색 자동완성
- 인체 UI 기반 증상/질병 확인
- ML/XAI 기반 건강 분석 확장
- LLM 기반 자연어 증상 입력 보조

상세 계획은 [ROADMAP.md](docs/ROADMAP.md)에서 확인할 수 있습니다.

## 상태

이 저장소는 포트폴리오 정리를 위한 중간 개발 단계의 백엔드 프로젝트입니다. 구현 완료 기능과 구현 중인 기능을 구분하여 관리하고 있으며, 추후 테스트, 배포 절차 문서화, 운영 설정 정리를 추가할 예정입니다.
