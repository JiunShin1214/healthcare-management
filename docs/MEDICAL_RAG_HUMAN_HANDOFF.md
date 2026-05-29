# Medical RAG Human Handoff

## 한 줄 요약

이미 만들어진 의료 문서 ChromaDB를 FastAPI에 붙여서, 일반 건강 질문이나 건강검진 OCR 결과를 참고용 카드 JSON으로 바꿔주는 선택 기능입니다.

## 백엔드에서 하는 일

백엔드는 새 문서를 수집하지 않습니다.

백엔드가 하는 일은 다음뿐입니다.

```text
사용자 질문 또는 OCR 결과
→ OpenAI embedding 생성
→ 로컬 chroma_db에서 관련 의료 문서 검색
→ 검색 문서를 근거로 카드 JSON 생성
→ 프론트에 반환
```

## 백엔드에서 하지 않는 일

```text
크롤링 안 함
CSV 재생성 안 함
재임베딩 안 함
확정 진단 안 함
처방 안 함
증상체커 후보를 RAG로 새로 만들지 않음
```

## 넘겨받아야 하는 필수 산출물

```text
chroma_db/
```

이 폴더가 런타임 검색 DB입니다.

현재 DB 상태:

```text
collection: medical_docs
documents: 13643
embedding model: text-embedding-3-small
dimension: 1536
sources: KDCA, NHS, Mayo Clinic
```

## 백엔드 코드 구성

```text
app/routers/medical_rag.py
app/services/medical_rag_service.py
app/schemas/medical_rag.py
```

`main.py`에는 아래처럼 라우터가 등록되어야 합니다.

```python
from app.routers import medical_rag

app.include_router(medical_rag.router)
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

`MEDICAL_RAG_CHROMA_PATH`는 배포 서버의 실제 `chroma_db` 절대 경로로 지정하는 것이 안전합니다.

## Endpoint

### 1. 상태 확인

```text
GET /medical-rag/health
```

용도:

```text
RAG 설정 확인
OPENAI_API_KEY 확인
chroma_db 접근 확인
collection document count 확인
```

### 2. 문서 검색

```text
POST /medical-rag/search
```

입력:

```json
{
  "query": "어제부터 목이 아프고 열이 조금 나요.",
  "top_k": 5
}
```

출력:

```text
검색된 의료 문서 chunk 목록
```

이 endpoint는 답변을 만들지 않습니다.

### 3. 자유 텍스트 답변

```text
POST /medical-rag/answer
```

용도:

```text
검색된 문서를 근거로 일반 텍스트 답변 생성
```

프론트 카드 UI에는 `/medical-rag/card`가 더 적합합니다.

### 4. 카드 생성

```text
POST /medical-rag/card
```

입력:

```json
{
  "query": "어제부터 목이 아프고 열이 조금 나요. 감기인지 걱정돼요.",
  "top_k": 5
}
```

출력:

```json
{
  "question": "어제부터 목이 아프고 열이 조금 나요. 감기인지 걱정돼요.",
  "card_title": "목 아픔과 미열 참고 카드",
  "card_subtitle": "검색된 의료 문서 기반 건강 정보 요약",
  "risk_level": "일반",
  "emergency_keywords": [],
  "summary": "...",
  "possible_related_topics": ["감기", "인후염", "독감"],
  "key_points": ["..."],
  "red_flags": ["..."],
  "recommended_next_steps": ["..."],
  "self_care_notes": ["..."],
  "sections": [
    {
      "title": "의료진에게 말하면 좋은 정보",
      "items": ["..."]
    }
  ],
  "sources": [
    {
      "title": "Sore throat",
      "source": "NHS",
      "url": "https://www.nhs.uk/conditions/sore-throat/",
      "category": "질병",
      "topic": "Sore throat"
    }
  ],
  "disclaimer": "이 카드는 참고용 건강 정보이며 의학적 진단이나 처방을 대체하지 않습니다."
}
```

### 5. 건강검진 OCR 결과 카드

```text
POST /medical-rag/health-check-card
```

이 기능은 선택입니다. 건강검진 OCR 결과를 카드로 보여주고 싶을 때만 호출합니다.

입력:

```json
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
    }
  },
  "findings": [
    {
      "code": "blood_pressure",
      "label": "혈압",
      "value": "145/92 mmHg",
      "status": "주의",
      "reason": "수축기와 이완기 혈압이 기준보다 높게 확인되었습니다."
    }
  ],
  "top_k": 5
}
```

`findings`는 기존 rule-based 판정 결과를 넣는 필드입니다. 없으면 `parsed_result`만으로 query를 만들지만, 정확한 카드 생성을 위해 가능하면 넣는 것이 좋습니다.

## 응답 필드 해석

### 안정적으로 써도 되는 필드

```text
sources
sources.topic
sources 순서
risk_level
emergency_keywords
disclaimer
```

`sources`는 검색된 문서 metadata 기반입니다. 현재 구현에서는 검색 결과 순서를 유지합니다.

### 사용자 설명용 필드

```text
card_title
summary
possible_related_topics
key_points
red_flags
recommended_next_steps
self_care_notes
sections
```

이 필드들은 LLM이 검색 문서를 바탕으로 생성합니다.

### 질병 후보 랭킹에 쓰면 안 되는 필드

```text
possible_related_topics
summary 안의 질병명
red_flags
```

이 값들은 설명용입니다. 질병 후보 랭킹 근거로 쓰기에는 안정성이 부족합니다.

## risk_level 기준

`risk_level`은 검색 결과가 아니라 사용자 입력 문장에서 응급 키워드를 찾은 결과입니다.

예:

```text
흉통
가슴 통증
가슴이 답답
호흡곤란
숨이 차
식은땀
왼팔 통증
턱 통증
한쪽 마비
말이 어눌
의식 저하
극심한 두통
혈변
검은변
```

키워드가 있으면 `주의`, 없으면 `일반`입니다.

## 증상체커와의 관계

권장 사용 방식:

```text
증상체커 rule engine이 후보와 위험 신호를 만든다.
RAG는 그 결과를 설명할 근거 문서와 카드 문장을 붙인다.
```

비권장:

```text
RAG 결과로 증상체커 후보를 새로 만들기
RAG summary에서 질병명을 뽑아 후보 랭킹 바꾸기
possible_related_topics를 후보 랭킹으로 사용하기
```

## 건강검진 OCR과의 관계

권장 사용 방식:

```text
OCR이 수치를 추출한다.
기존 rule engine이 이상 여부를 판단한다.
RAG는 관련 검진 수치 문서를 찾아 설명 카드를 만든다.
```

비권장:

```text
RAG 단독으로 정상/이상 판정하기
RAG 단독으로 진단명 확정하기
RAG 단독으로 약물/치료 지시하기
```

## 검증 순서

```text
1. 서버 env 설정
2. chroma_db 경로 확인
3. pip install -r requirements.txt
4. 서버 실행
5. GET /medical-rag/health
6. POST /medical-rag/search
7. POST /medical-rag/card
8. 필요한 경우 POST /medical-rag/health-check-card
```

## 현재 한계

```text
검색 유사도 distance를 응답하지 않음
topic별 aggregate score 없음
possible_related_topics는 LLM 생성값
질병 후보 랭킹용 API는 아직 아님
OpenAI API 비용 발생
```

질병 후보 랭킹까지 쓰려면 다음 필드를 추가하는 것이 좋습니다.

```json
{
  "retrieval_results": [
    {
      "rank": 1,
      "document_id": "...",
      "topic": "Sore throat",
      "source": "NHS",
      "distance": 0.23,
      "score_direction": "lower_distance_is_more_similar"
    }
  ],
  "topic_matches": [
    {
      "topic": "Sore throat",
      "best_rank": 1,
      "matched_chunks": 2,
      "best_distance": 0.23
    }
  ]
}
```
