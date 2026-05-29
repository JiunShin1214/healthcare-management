# Medical RAG Handoff

이 문서는 루트의 RAG 실험물을 `health-navigator-backend` FastAPI에 붙일 수 있도록 정리한 인계 기준입니다.

추가 인계 문서:

```text
docs/MEDICAL_RAG_CODEX_INTEGRATION_PROMPT.md
docs/MEDICAL_RAG_HUMAN_HANDOFF.md
```

`MEDICAL_RAG_CODEX_INTEGRATION_PROMPT.md`는 백엔드 개발자가 Codex에게 그대로 전달할 수 있는 반영 지시서입니다.
`MEDICAL_RAG_HUMAN_HANDOFF.md`는 사람이 읽기 좋은 요약 인계서입니다.

## 포함된 백엔드 모듈

```text
health-navigator-backend/app/routers/medical_rag.py
health-navigator-backend/app/schemas/medical_rag.py
health-navigator-backend/app/services/medical_rag_service.py
```

`app/main.py`에는 이미 아래 라우터가 등록되어 있습니다.

```python
app.include_router(medical_rag.router)
```

## 전달해야 하는 산출물

백엔드 파트에 최소로 넘길 것은 다음입니다.

```text
chroma_db/
```

백엔드에서는 추가 수집이나 재색인을 하지 않습니다. `chroma_db/`는 이미 수집, 정제, 임베딩이 끝난 런타임 검색용 산출물입니다.

아래 파일들은 백엔드 런타임 필수 산출물이 아니라 RAG 데이터 제작/검수 이력입니다.

```text
data/kdca_rag_documents.csv
data/mayo_rag_documents.csv
data/nhs_rag_documents.csv
ingest.py
crawl_to_rag_csv.py
extract_kdca_links.py
extract_mayo_links.py
refine_rag_documents.py
```

백엔드 파트에는 위 제작 스크립트를 붙이지 않아도 됩니다. 필요하면 데이터 출처/재현성 설명용으로만 별도 보관합니다.

현재 로컬 `chroma_db` 상태:

```text
collection: medical_docs
embedding dimension: 1536
embedding count: 13643
embedding model: text-embedding-3-small
```

## 환경 변수

```env
OPENAI_API_KEY=...
MEDICAL_RAG_ENABLED=true
MEDICAL_RAG_CHROMA_PATH=/absolute/path/to/chroma_db
MEDICAL_RAG_COLLECTION_NAME=medical_docs
MEDICAL_RAG_EMBEDDING_MODEL=text-embedding-3-small
MEDICAL_RAG_CHAT_MODEL=gpt-4o-mini
```

`MEDICAL_RAG_CHROMA_PATH`를 비워두면 기본값은 프로젝트 루트의 `chroma_db`입니다. 백엔드 폴더만 따로 배포한다면 이 값을 반드시 절대 경로로 지정하는 편이 안전합니다.

## API

### 상태 확인

```http
GET /medical-rag/health
```

예상 응답:

```json
{
  "enabled": true,
  "configured": true,
  "collection_name": "medical_docs",
  "chroma_path": "/path/to/chroma_db",
  "document_count": 13643,
  "error": null
}
```

### 문서 검색

```http
POST /medical-rag/search
Content-Type: application/json

{
  "query": "LDL이 높고 흡연을 하는데 가슴이 답답해요",
  "top_k": 5
}
```

선택 필터:

```json
{
  "source": "질병관리청 국가건강정보포털",
  "category": "응급"
}
```

### 답변 생성

```http
POST /medical-rag/answer
Content-Type: application/json

{
  "query": "LDL이 170이고 흡연을 하는데 가슴이 답답합니다.",
  "top_k": 5
}
```

응답에는 `answer`, `risk_level`, `emergency_keywords`, `sources`가 포함됩니다. 응급 키워드는 별도 rule로 먼저 확인하고, 답변 프롬프트는 진단 확정 금지와 출처 표기를 강제합니다.

### 카드 생성

프론트에서 진단카드처럼 보여줄 최종 가공 응답은 `/medical-rag/card`를 사용합니다. API 명칭과 문구는 확정 진단이 아니라 참고 카드로 유지합니다.

```http
POST /medical-rag/card
Content-Type: application/json

{
  "query": "LDL이 170이고 흡연을 하는데 가슴이 답답합니다.",
  "top_k": 5
}
```

### 건강검진 OCR 결과 카드 생성

이 endpoint는 선택 기능입니다. 백엔드가 건강검진 OCR/파싱 결과를 RAG 카드로 보여주고 싶을 때만 호출합니다. 추가 수집이나 재색인은 하지 않습니다.

```http
POST /medical-rag/health-check-card
Content-Type: application/json

{
  "parsed_result": {
    "gender": "male",
    "age": 42,
    "blood_pressure": {
      "systolic": 145,
      "diastolic": 92,
      "unit": "mmHg"
    },
    "fasting_glucose": {
      "value": 118,
      "unit": "mg/dL"
    },
    "ldl": {
      "value": 155,
      "unit": "mg/dL"
    },
    "gamma_gtp": {
      "value": 85,
      "unit": "U/L"
    }
  },
  "findings": [
    {
      "code": "blood_pressure",
      "label": "혈압",
      "value": "145/92 mmHg",
      "status": "주의",
      "reason": "수축기와 이완기 혈압이 기준보다 높게 확인되었습니다."
    },
    {
      "code": "fasting_glucose",
      "label": "공복혈당",
      "value": "118 mg/dL",
      "status": "주의",
      "reason": "공복혈당 관리가 필요할 수 있습니다."
    }
  ],
  "top_k": 5
}
```

응답은 `/medical-rag/card`와 같은 카드 구조에 `generated_query`와 `abnormal_findings`가 추가됩니다.

```json
{
  "question": "건강검진 결과 참고 카드",
  "generated_query": "건강검진 결과를 참고용으로 설명해주세요...",
  "abnormal_findings": [
    {
      "code": "blood_pressure",
      "label": "혈압",
      "value": "145/92 mmHg",
      "status": "주의",
      "reason": "수축기와 이완기 혈압이 기준보다 높게 확인되었습니다."
    }
  ],
  "card_title": "건강검진 수치 참고 카드",
  "summary": "혈압과 혈당 수치가 관리가 필요한 범위일 수 있습니다.",
  "recommended_next_steps": [
    "검진 결과지를 가지고 내과 또는 가정의학과 상담을 받으세요."
  ],
  "sources": [],
  "disclaimer": "이 카드는 참고용 건강 정보이며 의학적 진단이나 처방을 대체하지 않습니다."
}
```

백엔드 내부에서 endpoint를 거치지 않고 service 함수로 직접 호출할 수도 있습니다.

```python
from app.services.medical_rag_service import generate_health_check_rag_card

card = generate_health_check_rag_card(
    parsed_result=parsed,
    findings=findings,
    top_k=5,
)
```

응답 예시:

```json
{
  "question": "LDL이 170이고 흡연을 하는데 가슴이 답답합니다.",
  "card_title": "가슴 답답함과 LDL 상승 관련 참고 카드",
  "card_subtitle": "검색된 의료 문서 기반 요약",
  "risk_level": "주의",
  "emergency_keywords": ["가슴이 답답"],
  "summary": "가슴 답답함은 빠른 진료가 필요한 증상일 수 있으며, LDL 상승과 흡연은 심혈관 위험과 관련될 수 있습니다.",
  "possible_related_topics": ["흉통", "이상지질혈증", "심혈관 위험"],
  "key_points": [
    "LDL 수치가 높으면 심혈관 질환 위험 관리가 중요합니다.",
    "흡연은 심혈관 위험을 높이는 요인입니다."
  ],
  "red_flags": [
    "가슴 통증이나 답답함이 지속되거나 심해지는 경우",
    "호흡곤란, 식은땀, 왼팔이나 턱으로 퍼지는 통증이 동반되는 경우"
  ],
  "recommended_next_steps": [
    "현재 증상이 지속되면 즉시 의료기관 또는 응급 상담을 받으세요.",
    "LDL 수치와 흡연력은 의사와 상담해 심혈관 위험 평가를 받는 것이 좋습니다."
  ],
  "self_care_notes": [
    "증상이 있는 상태에서는 무리한 운동을 피하세요.",
    "금연과 식습관 조정은 장기적인 위험 관리에 도움이 될 수 있습니다."
  ],
  "sections": [
    {
      "title": "참고할 점",
      "items": ["검색된 문서는 진단 확정이 아니라 상담 전 참고 정보로 사용해야 합니다."]
    }
  ],
  "sources": [
    {
      "title": "흉통",
      "source": "질병관리청 국가건강정보포털",
      "url": "https://...",
      "category": "응급",
      "topic": "흉통"
    }
  ],
  "disclaimer": "이 카드는 참고용 건강 정보이며 의학적 진단이나 처방을 대체하지 않습니다."
}
```

## 의존성

`health-navigator-backend/requirements.txt`에 다음 패키지를 추가했습니다.

```text
chromadb
openai
```

## 운영 메모

- 이 RAG는 외부 웹 검색이 아니라 로컬 ChromaDB 검색입니다.
- 백엔드 런타임은 추가 크롤링, 추가 수집, CSV 재생성을 수행하지 않습니다.
- `/medical-rag/search`는 답변 생성 없이 근거 문서만 반환합니다.
- `/medical-rag/answer`는 OpenAI embedding과 chat completion을 모두 사용합니다.
- 의료 판단을 확정하지 않도록 프롬프트에 안전 규칙을 넣었지만, 서비스 화면에서도 “참고용 정보이며 진단/처방이 아니다”라는 문구를 유지해야 합니다.
- 기존 `/symptom-checker`의 reviewed-card RAG 정책과 섞이지 않도록 별도 라우터로 분리했습니다.
